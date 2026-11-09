#!/usr/bin/env python3
"""Testes reais de CLI, Git, arquivos, SQLite e HTTP local (sem deps Python externas)."""
import http.client
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.parse import urlencode

BINARY = str(Path(sys.argv[1]).resolve()) if len(sys.argv) > 1 else 'lac'
WEBROOT = Path(__file__).resolve().parent.parent / 'web'
sys.argv = [sys.argv[0]]

class LabTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='lac-test-')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.db = self.home / 'memory.sqlite3'
        self.docs = self.home / 'docs'
        self.docs.mkdir()
        self.git = self.home / 'repo'
        self.git.mkdir()
        self.cli('init')

    def cli(self, *args, check=True):
        cmd = [BINARY, args[0], '--db', str(self.db), *args[1:]]
        return subprocess.run(cmd, text=True, capture_output=True, check=check, timeout=20)

    def register(self, project, path, kind):
        return self.cli('register', '--project', project, '--path', str(path), '--kind', kind)

    def start_server(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        self.port = port
        self.proc = subprocess.Popen([BINARY, 'serve', '--db', str(self.db),
                                      '--port', str(port), '--scan-every', '0',
                                      '--webroot', str(WEBROOT)],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(self.stop_server)
        for _ in range(100):
            if self.proc.poll() is not None:
                raise AssertionError('Server exited before startup: ' + self.proc.stderr.read().decode())
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.25):
                    return
            except OSError:
                time.sleep(.025)
        raise AssertionError('Server did not become reachable')

    def stop_server(self):
        if hasattr(self, 'proc') and self.proc.poll() is None:
            self.proc.terminate()
            try: self.proc.communicate(timeout=2)
            except subprocess.TimeoutExpired: self.proc.kill(); self.proc.communicate(timeout=2)

    def req(self, path, data=None, extra=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=4)
        headers = extra if extra is not None else {}
        if data is None:
            conn.request('GET', path, headers=headers)
        else:
            headers = {'Content-Type': 'application/x-www-form-urlencoded', 'X-LAC-Local': '1', **headers}
            conn.request('POST', path, body=urlencode(data), headers=headers)
        res = conn.getresponse()
        raw = res.read()
        status = res.status
        ctype = res.getheader('Content-Type', '')
        conn.close()
        return status, json.loads(raw) if 'json' in ctype else raw.decode()

    def test_documents_repeated_scan_history_search_and_missing(self):
        (self.docs / 'fundamentos.md').write_text('# Sempre pronto\nREA / RIT / MPRR\n')
        self.register('TESSITURA', self.docs, 'docs')
        self.assertIn('new events: 1', self.cli('scan').stdout)
        self.assertIn('new events: 0', self.cli('scan').stdout)
        (self.docs / 'fundamentos.md').write_text('# Sempre incompleto\nREA / RIT\n')
        self.assertIn('new events: 1', self.cli('scan').stdout)
        (self.docs / 'fundamentos.md').unlink()
        self.assertIn('new events: 1', self.cli('scan').stdout)
        self.assertIn('new events: 0', self.cli('scan').stdout)
        self.assertEqual(3, json.loads(self.cli('stats').stdout)['events'])
        self.assertIn('cadeia SHA-256 consistente', self.cli('verify').stdout)
        anchor=self.home/'anchor.sha256'
        self.cli('anchor','--out',str(anchor))
        self.assertIn('external anchor verified', self.cli('verify','--anchor',str(anchor)).stdout)
        report=self.home/'diario.md'
        self.cli('report','--from','2000-01-01','--to','2100-01-01','--out',str(report))
        self.assertIn('fundamentos.md',report.read_text())
        self.start_server()
        status, data = self.req('/api/events?q=fundamentos')
        self.assertEqual(200, status)
        self.assertEqual(3, len(data))
        self.assertEqual({'file_added', 'file_changed', 'file_missing'}, {x['kind'] for x in data})
        self.assertEqual('observed', data[0]['evidence_state'])
        self.assertEqual(200, self.req('/api/health')[0])
        self.assertIn('fundamentos.md',self.req('/api/report?from=2000-01-01&to=2100-01-01')[1])
        self.assertIn('Continu', self.req('/')[1])
        self.assertIn('const api', self.req('/app.js')[1])

    def test_git_commits_replay_and_history(self):
        subprocess.run(['git','init', '-q', str(self.git)],check=True)
        subprocess.run(['git','-C',str(self.git),'config','user.email','tester@example.com'],check=True)
        subprocess.run(['git','-C',str(self.git),'config','user.name','Tester'],check=True)
        (self.git/'readme.md').write_text('laboratorio\n')
        subprocess.run(['git','-C',str(self.git),'add','readme.md'],check=True)
        subprocess.run(['git','-C',str(self.git),'commit','-qm','Implementar observer inicial'],check=True)
        self.register('ELO OS',self.git,'git')
        self.assertIn('new events: 1',self.cli('scan').stdout)
        self.assertIn('new events: 0',self.cli('scan').stdout)
        self.start_server()
        status, data=self.req('/api/events?kind=git_commit&q=observer')
        self.assertEqual(200,status)
        self.assertEqual(1,len(data))
        self.assertEqual('git',data[0]['source_type'])
        self.assertIn('#',data[0]['source_ref'])

    def test_manual_decisions_todos_and_links(self):
        self.start_server()
        status, note=self.req('/api/notes',{'project':'MPRR','kind':'decision',
                  'title':'Separação metodológica','body':'Não inferir causalidade'})
        self.assertEqual(201,status)
        status, todo=self.req('/api/notes',{'project':'MPRR','kind':'todo',
                  'title':'Validar piloto','body':'Planejar protocolo'})
        self.assertEqual(201,status)
        self.assertEqual(1,len(self.req('/api/todos')[1]))
        status, rel=self.req('/api/relations',{'from':'MPRR','to':'EVIDA',
            'label':'Integração candidata','state':'candidate'})
        self.assertEqual(201,status)
        self.assertEqual('candidate',self.req('/api/relations')[1][0]['state'])
        status, closed=self.req('/api/todos/close',{'id':str(todo['id'])})
        self.assertEqual(201,status)
        self.assertEqual([],self.req('/api/todos')[1])
        self.assertNotEqual(note['id'],closed['id'])
        self.assertEqual(4,self.req('/api/stats')[1]['events'])
        self.assertEqual(True,self.req('/api/verify')[1]['ok'])
        self.assertEqual(4,len(self.req('/api/events?project=MPRR')[1]))
        self.assertEqual('declared',self.req('/api/events?kind=decision')[1][0]['evidence_state'])
        self.assertEqual(400,self.req('/api/notes',{'project':'MPRR','kind':'invalid','title':'x'})[0])

    def test_visual_identity_assets(self):
        self.start_server()
        page_status, page = self.req('/')
        self.assertEqual(200, page_status)
        self.assertIn('LAC', page)
        self.assertIn('v0.1.2', page)
        self.assertIn('data-view="overview"',page)
        self.assertIn('id="quickRail"',page)
        self.assertIn('id="view-integrity"',page)
        self.assertIn('id="view-reports"',page)
        self.assertIn('id="reportForm"',page)
        self.assertIn('/assets/lac-symbol.svg', page)
        for route in ['/favicon.svg', '/assets/lac-symbol.svg']:
            status, body = self.req(route)
            self.assertEqual(200, status)
            self.assertIn('<svg', body)
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=4)
        conn.request('GET', '/assets/lac-icon-512.png')
        png_res = conn.getresponse()
        self.assertEqual(200, png_res.status)
        self.assertEqual('image/png', png_res.getheader('Content-Type'))
        self.assertTrue(png_res.read().startswith(b'\x89PNG'))
        conn.close()
        status, css = self.req('/style.css')
        self.assertEqual(200, status)
        self.assertIn('--navy:', css)
        self.assertIn('.dashboard-body',css)
        self.assertIn('.masthead',css)
        script=self.req('/app.js')[1]
        self.assertIn('btnScanFull',script)
        self.assertIn('btnReportQuick',script)
        self.assertIn('preferCompact',script)
        self.assertEqual(404, self.req('/assets/unknown.svg')[0])

    def test_http_restrictions(self):
        self.start_server()
        self.assertEqual(403,self.req('/api/notes',{}, {'X-LAC-Local':'0'})[0])
        self.assertEqual(403,self.req('/api/notes',{}, {'Origin':'https://evil.example'})[0])
        self.assertEqual(404,self.req('/..%2Fetc%2Fpasswd')[0])
        self.assertEqual(403,self.req('/api/stats',None,{'Host':'attacker.invalid'})[0])
        self.assertEqual(200,self.req('/api/events?q=%22%20OR%201%3D1%20--')[0])

    def test_database_appendonly_and_tamper_detection(self):
        self.register('Projeto',self.docs,'docs')
        (self.docs/'a.md').write_text('teste')
        self.cli('scan')
        with sqlite3.connect(self.db) as con:
            with self.assertRaises(sqlite3.DatabaseError):
                con.execute('UPDATE events SET title="falso" WHERE id=1')
            # Adversarial DB modification requires bypassing the append-only trigger;
            # the stored SHA-256 chain must then catch content tampering.
            con.execute('DROP TRIGGER events_no_update')
            con.execute('UPDATE events SET title="falso" WHERE id=1')
        self.assertEqual(2,self.cli('verify',check=False).returncode)

if __name__=='__main__': unittest.main(verbosity=2)
