#!/usr/bin/env python3
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'scripts'))

from lac_continuity_worker import ContinuityWorker


class ContinuityWorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='lac-worker-test-')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.db_path = self.home / 'test.db'
        
        # Initialize schema
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.executescript("""
            CREATE TABLE projects(id INTEGER PRIMARY KEY, name TEXT UNIQUE, created_at TEXT);
            CREATE TABLE roots(id INTEGER PRIMARY KEY, project_id INTEGER, kind TEXT, path TEXT, scan_counter INTEGER DEFAULT 0);
            CREATE TABLE events(
                id INTEGER PRIMARY KEY, project_id INTEGER, kind TEXT, title TEXT, body TEXT,
                source_type TEXT, source_ref TEXT, occurred_at TEXT, recorded_at TEXT,
                evidence_state TEXT, dedupe_key TEXT UNIQUE, prev_hash TEXT, event_hash TEXT
            );
            CREATE TABLE continuity_jobs(
                id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER, root_id INTEGER,
                path TEXT, kind TEXT, state TEXT CHECK(state IN ('pending','processing','completed','failed')),
                attempts INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT, error_message TEXT
            );
            CREATE TABLE continuity_insights(
                id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER, event_id INTEGER,
                project_id INTEGER, document_path TEXT, summary TEXT, gaps_json TEXT,
                model TEXT, created_at TEXT, event_hash TEXT, relations_json TEXT DEFAULT '[]'
            );
            INSERT INTO projects VALUES(1, 'TESSITURA', '2026-11-09T00:00:00Z');
            INSERT INTO projects VALUES(2, 'EVIDA', '2026-11-09T00:00:00Z');
        """)
        
        # Create an authorized doc root
        self.doc_dir = self.home / 'docs'
        self.doc_dir.mkdir()
        cur.execute("INSERT INTO roots VALUES(1, 1, 'docs', ?, 1)", (str(self.doc_dir),))
        
        # Create a document
        self.doc_file = self.doc_dir / 'ADR-004.md'
        self.doc_file.write_text('# Grafo Argumentativo\nO TESSITURA investiga situações socioecológicas.\n', encoding='utf-8')
        
        # Create event and job
        cur.execute("""
            INSERT INTO events VALUES(
                10, 1, 'file_added', 'ADR-004.md', 'SHA-256: dummy',
                'file', ?, '2026-11-09T16:00:00Z', '2026-11-09T16:00:00Z',
                'observed', 'file:1:ADR-004.md:1', 'GENESIS', 'hash12345'
            )
        """, (str(self.doc_file),))
        cur.execute("""
            INSERT INTO continuity_jobs(event_id, root_id, path, kind, state, created_at, updated_at)
            VALUES(10, 1, 'ADR-004.md', 'file_added', 'pending', '2026-11-09T16:00:00Z', '2026-11-09T16:00:00Z')
        """)
        conn.commit()
        conn.close()

    @patch('subprocess.run')
    def test_worker_processes_job_and_persists_insight(self, mock_subproc):
        mock_subproc.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                'result': {
                    'summary': 'O TESSITURA estabelece o grafo argumentativo para investigar situações socioecológicas.',
                    'gaps': ['Faltam evidências de campo na primeira fase.']
                }
            })
        )
        
        worker = ContinuityWorker(db_path=self.db_path, model='test-model')
        results = worker.run_all_pending()
        
        self.assertEqual(1, len(results))
        self.assertTrue(results[0]['ok'])
        self.assertEqual('TESSITURA', results[0]['project'])
        self.assertEqual('ADR-004.md', results[0]['document'])
        self.assertIn('grafo argumentativo', results[0]['summary'])
        self.assertEqual(['Faltam evidências de campo na primeira fase.'], results[0]['gaps'])
        
        # Verify in DB
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        job = cur.execute("SELECT state, attempts FROM continuity_jobs WHERE id = 1").fetchone()
        self.assertEqual('completed', job[0])
        self.assertEqual(1, job[1])
        
        insight = cur.execute("SELECT summary, gaps_json, model, event_hash, relations_json FROM continuity_insights WHERE job_id = 1").fetchone()
        self.assertIn('grafo argumentativo', insight[0])
        self.assertIn('Faltam evidências', insight[1])
        self.assertEqual('test-model', insight[2])
        self.assertEqual('hash12345', insight[3])
        self.assertIsNotNone(insight[4])
        conn.close()

    @patch('subprocess.run')
    def test_worker_idempotency_when_empty(self, mock_subproc):
        # When no pending jobs exist, worker returns empty list
        worker = ContinuityWorker(db_path=self.db_path)
        # Clear jobs
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM continuity_jobs")
        conn.commit()
        conn.close()

        results = worker.run_all_pending()
        self.assertEqual(0, len(results))
        mock_subproc.assert_not_called()

    @patch('subprocess.run')
    def test_worker_respects_dismissed_feedback_rea(self, mock_subproc):
        mock_subproc.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                'result': {
                    'summary': 'O TESSITURA dialoga sobre o grafo argumentativo.',
                    'gaps': []
                }
            })
        )
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS continuity_feedback(
                id INTEGER PRIMARY KEY AUTOINCREMENT, insight_id INTEGER,
                project_id INTEGER, target_type TEXT, target_ref TEXT,
                decision TEXT, reason TEXT, actor TEXT, created_at TEXT
            );
            INSERT INTO continuity_feedback(insight_id, project_id, target_type, target_ref, decision, reason, actor, created_at)
            VALUES(NULL, 1, 'relation', 'EVIDA', 'dismissed', 'Fora do escopo', 'user', '2026-11-09T16:00:00Z');
            UPDATE continuity_jobs SET state = 'pending', attempts = 0 WHERE id = 1;
        """)
        conn.commit()
        conn.close()

        worker = ContinuityWorker(db_path=self.db_path, model='test-model')
        results = worker.run_all_pending()
        self.assertEqual(1, len(results))

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        insight = cur.execute("SELECT relations_json FROM continuity_insights ORDER BY id DESC LIMIT 1").fetchone()
        relations = json.loads(insight[0])
        targets = [r['target_project'] for r in relations]
        self.assertNotIn('EVIDA', targets)
        conn.close()


if __name__ == '__main__':
    unittest.main()
