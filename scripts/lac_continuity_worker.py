#!/usr/bin/env python3
"""Autonomous continuity worker for LAC.

Consumes durable jobs, extracts text with lac_doc_reader, fetches historical
context, and synthesizes conceptual changes and gaps via lac_local_llm (Qwen 2.5).
Preserves provenance and idempotency without human intervention.
"""
from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lac_doc_reader import read_document


def utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class ContinuityWorker:
    def __init__(self, db_path: str | Path, model: str = 'qwen2.5:7b'):
        self.db_path = Path(db_path).resolve()
        self.model = model
        if not self.db_path.is_file():
            raise FileNotFoundError(f"Banco SQLite não encontrado: {self.db_path}")

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def process_next_job(self) -> dict | None:
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT j.id, j.event_id, j.root_id, j.path, j.kind,
                       r.path as root_path, e.project_id, p.name as project_name,
                       e.occurred_at, e.event_hash
                FROM continuity_jobs j
                JOIN roots r ON r.id = j.root_id
                JOIN events e ON e.id = j.event_id
                JOIN projects p ON p.id = e.project_id
                WHERE j.state = 'pending'
                ORDER BY j.id ASC
                LIMIT 1
            """)
            job = cur.fetchone()
            if not job:
                return None

            job_id = job['id']
            now = utc_now_iso()
            cur.execute(
                "UPDATE continuity_jobs SET state = 'processing', attempts = attempts + 1, updated_at = ? WHERE id = ?",
                (now, job_id)
            )
            conn.commit()

            # Execute analysis
            full_path = Path(job['root_path']) / job['path']
            doc_res = read_document(full_path, authorized_roots=[job['root_path']], max_chars=4096)

            if not doc_res.get('ok'):
                err = doc_res.get('error', 'Falha ao ler documento')
                cur.execute(
                    "UPDATE continuity_jobs SET state = 'failed', error_message = ?, updated_at = ? WHERE id = ?",
                    (err, utc_now_iso(), job_id)
                )
                conn.commit()
                return {'job_id': job_id, 'ok': False, 'error': err}

            # Fetch recent decisions/notes for this project to provide historical continuity
            cur.execute("""
                SELECT id, title, body FROM events
                WHERE project_id = ? AND kind IN ('decision', 'note') AND id != ?
                ORDER BY id DESC LIMIT 2
            """, (job['project_id'], job['event_id']))
            previous_events = cur.fetchall()

            sources = [
                {
                    'ref': f"event:{job['event_id']}",
                    'title': f"{job['path']} ({job['kind']})",
                    'text': doc_res['text'],
                    'nature': 'observed'
                }
            ]
            for prev in previous_events:
                sources.append({
                    'ref': f"event:{prev['id']}",
                    'title': prev['title'],
                    'text': prev['body'],
                    'nature': 'declared'
                })

            context_payload = {
                'project_ref': f"project:{job['project_id']}",
                'sources': sources
            }

            # Invoke local LLM adapter
            llm_script = SCRIPT_DIR / 'lac_local_llm.py'
            proc = subprocess.run(
                [sys.executable, str(llm_script), '--model', self.model],
                input=json.dumps(context_payload),
                text=True,
                capture_output=True,
                timeout=45
            )

            if proc.returncode != 0:
                err = f"Falha na inferência local (código {proc.returncode}): {proc.stderr.strip()}"
                cur.execute("""
                    UPDATE continuity_jobs
                    SET state = CASE WHEN attempts >= 3 THEN 'failed' ELSE 'pending' END,
                        error_message = ?, updated_at = ?
                    WHERE id = ?
                """, (err, utc_now_iso(), job_id))
                conn.commit()
                return {'job_id': job_id, 'ok': False, 'error': err}

            llm_output = json.loads(proc.stdout)
            result = llm_output.get('result', {})
            summary = result.get('summary', 'Síntese não gerada.')
            gaps_json = json.dumps(result.get('gaps', []), ensure_ascii=False)

            # Persist derived insight
            cur.execute("""
                INSERT INTO continuity_insights(
                    job_id, event_id, project_id, document_path,
                    summary, gaps_json, model, created_at, event_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id, job['event_id'], job['project_id'], job['path'],
                summary, gaps_json, self.model, utc_now_iso(), job['event_hash']
            ))

            cur.execute(
                "UPDATE continuity_jobs SET state = 'completed', updated_at = ? WHERE id = ?",
                (utc_now_iso(), job_id)
            )
            conn.commit()

            return {
                'job_id': job_id,
                'ok': True,
                'project': job['project_name'],
                'document': job['path'],
                'summary': summary,
                'gaps': result.get('gaps', [])
            }

        finally:
            conn.close()

    def run_all_pending(self) -> list[dict]:
        results = []
        while True:
            res = self.process_next_job()
            if res is None:
                break
            results.append(res)
        return results

    def loop(self, interval_seconds: int = 5):
        print(f"[LAC Continuity Worker] Iniciado com modelo {self.model}. Observando fila em {self.db_path}...")
        while True:
            try:
                res = self.process_next_job()
                if res:
                    if res.get('ok'):
                        print(f"[{utc_now_iso()}] Job #{res['job_id']} concluído com sucesso: {res['project']} · {res['document']}")
                        print(f"  Síntese: {res['summary']}")
                    else:
                        print(f"[{utc_now_iso()}] Job #{res['job_id']} falhou: {res.get('error')}")
                else:
                    time.sleep(interval_seconds)
            except KeyboardInterrupt:
                print("\n[LAC Continuity Worker] Encerrado pelo usuário.")
                break
            except Exception as e:
                print(f"[LAC Continuity Worker] Erro inesperado: {e}")
                time.sleep(interval_seconds)


def main():
    parser = argparse.ArgumentParser(description='Worker autônomo de continuidade do LAC')
    parser.add_argument('--db', default=str(Path.home() / '.local/share/lac/lac.db'), help='Caminho do banco SQLite')
    parser.add_argument('--model', default='qwen2.5:7b', help='Modelo local Ollama')
    parser.add_argument('--daemon', action='store_true', help='Executar continuamente em loop')
    parser.add_argument('--interval', type=int, default=5, help='Intervalo de checagem em segundos (modo daemon)')
    args = parser.parse_args()

    worker = ContinuityWorker(db_path=args.db, model=args.model)
    if args.daemon:
        worker.loop(interval_seconds=args.interval)
    else:
        results = worker.run_all_pending()
        print(json.dumps({'processed_jobs': len(results), 'results': results}, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
