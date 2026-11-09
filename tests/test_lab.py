#!/usr/bin/env python3
"""Testes reais de CLI, Git, arquivos, SQLite e HTTP local (sem deps Python externas)."""
import http.client
import http.server
import base64
import threading
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
from smtp_fixture import MailSink
from urllib.parse import quote, urlencode

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

    def start_server(self, bind="127.0.0.1", token=None, extra_env=None):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        self.port = port
        self.token = token if token is not None else 'test-service-' + 'x' * 40
        env = dict(os.environ)
        for key in list(env):
            if key.startswith('LAC_SMTP_') or key in ('LAC_API_TOKEN','LAC_SERVICE_TOKEN','LAC_AUTH_ALLOWED_EMAILS'):
                env.pop(key, None)
        if self.token:
            env['LAC_SERVICE_TOKEN'] = self.token
        env.update(extra_env or {})
        self.proc = subprocess.Popen([BINARY, 'serve', '--db', str(self.db),
                                      '--port', str(port), '--scan-every', '0',
                                      '--webroot', str(WEBROOT), '--bind', bind], env=env,
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
        headers = ({'Authorization': 'Bearer ' + self.token} if getattr(self, 'token', '') else {})
        headers.update(extra or {})
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
        # Test /api/documents/read
        active_doc = self.docs / 'ativo.md'
        active_doc.write_text('# Documento ativo\nConteudo restrito e delimitado.\n', encoding='utf-8')
        doc_status, doc_data = self.req('/api/documents/read?path=' + quote(str(active_doc)))
        self.assertEqual(200, doc_status)
        self.assertTrue(doc_data['ok'])
        self.assertEqual('ativo.md', doc_data['filename'])
        self.assertIn('Conteudo restrito e delimitado', doc_data['text'])
        # Reject unauthorized path outside registered roots
        outside_status, outside_data = self.req('/api/documents/read?path=/tmp/outside.md')
        self.assertFalse(outside_data.get('ok', False))

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
        self.assertIn('v0.1.4', page)
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


    def test_network_binding_requires_token_and_protects_all_api_routes(self):
        self.start_server(bind='0.0.0.0', token='test-token-' + 'a' * 40)
        self.assertEqual(200, self.req('/api/stats')[0])
        self.assertEqual(401, self.req('/api/stats', extra={'Authorization': ''})[0])
        self.assertEqual(401, self.req('/api/notes', {'project': 'P', 'kind': 'note', 'title': 'x'},
                                      {'Authorization': 'Bearer wrong'})[0])
        self.assertEqual(403, self.req('/api/stats', extra={'Host': 'evil.invalid'})[0])
        lan_host = f'192.168.1.10:{self.port}'
        self.assertEqual(200, self.req('/api/stats', extra={'Host': lan_host, 'Origin': 'http://' + lan_host})[0])
        self.assertEqual(403, self.req('/api/stats', extra={'Host': lan_host, 'Origin': 'http://evil.invalid'})[0])
        self.assertEqual(200, self.req('/', extra={'Authorization': ''})[0])

    def mcp_exchange(self, requests, write=False, token=None):
        script = WEBROOT.parent / 'scripts' / 'lac_mcp.py'
        command = [sys.executable, str(script), '--url', f'http://127.0.0.1:{self.port}']
        if write:
            command.append('--allow-write')
        env = dict(os.environ)
        env.pop('LAC_API_TOKEN', None)
        env.pop('LAC_SESSION_TOKEN', None)
        env.pop('LAC_SERVICE_TOKEN', None)
        env['HOME'] = str(self.home)
        if token:
            env['LAC_SESSION_TOKEN'] = token
        init = {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
                'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'test', 'version': '1'}}}
        messages = [init, {'jsonrpc': '2.0', 'method': 'notifications/initialized'}, *requests]
        proc = subprocess.run(command, input=''.join(json.dumps(m) + '\n' for m in messages),
                              text=True, capture_output=True, env=env, timeout=12, check=True)
        self.assertEqual('', proc.stderr)
        return [json.loads(line) for line in proc.stdout.splitlines()]

    def test_mcp_readonly_protocol_authentication_and_validation(self):
        self.start_server(token='mcp-token-' + 'b' * 40)
        call = lambda name, args={}: {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
                                      'params': {'name': name, 'arguments': args}}
        listed = self.mcp_exchange([{'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}])[1]
        names = {t['name'] for t in listed['result']['tools']}
        self.assertIn('lac_events', names)
        self.assertNotIn('lac_record', names)
        self.assertEqual(-32602, self.mcp_exchange([call('lac_record')])[1]['error']['code'])
        self.assertTrue(self.mcp_exchange([call('lac_stats')])[1]['result']['isError'])
        data = self.mcp_exchange([call('lac_stats')], token=self.token)[1]['result']
        self.assertFalse(data['isError'])
        self.assertEqual(0, json.loads(data['content'][0]['text'])['events'])
        self.assertEqual(-32602, self.mcp_exchange([call('lac_events', {'limit': True})])[1]['error']['code'])
        self.assertEqual(-32602, self.mcp_exchange([call('lac_events', {'limit': 201})])[1]['error']['code'])
        self.assertEqual(-32601, self.mcp_exchange([{'jsonrpc': '2.0', 'id': 2, 'method': 'unknown'}])[1]['error']['code'])
        self.assertEqual(0, self.req('/api/stats')[1]['events'])

    def test_mcp_writes_provenance_todo_closure_and_candidate_relations(self):
        self.start_server()
        call = lambda name, args={}: {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
                                      'params': {'name': name, 'arguments': args}}
        result = self.mcp_exchange([call('lac_record', {'project': 'P', 'kind': 'todo',
                          'title': 'Validar integração', 'reference': 'docs/test.md'})], write=True, token=self.token)[1]['result']
        self.assertFalse(result['isError'])
        todo_id = json.loads(result['content'][0]['text'])['id']
        event = self.req('/api/events')[1][0]
        self.assertEqual('llm', event['actor'])
        self.assertEqual('llm:mcp:docs/test.md', event['source_ref'])
        self.assertEqual('declared', event['evidence_state'])
        result = self.mcp_exchange([call('lac_close_todo', {'id': todo_id}),
            call('lac_propose_relation', {'from': 'P', 'to': 'Q', 'label': 'Integração possível'})], write=True, token=self.token)
        self.assertTrue(all(not r['result']['isError'] for r in result[1:]))
        self.assertEqual([], self.req('/api/todos')[1])
        self.assertEqual(0, self.req('/api/stats')[1]['open_todos'])
        self.assertEqual('candidate', self.req('/api/relations')[1][0]['state'])
        self.assertEqual(400, self.req('/api/relations', {'from': 'P', 'to': 'Q', 'label': 'x',
                        'state': 'user_confirmed'}, {'X-LAC-Agent': 'mcp'})[0])
        self.assertEqual(400, self.req('/api/todos/close', {'id': str(todo_id)})[0])
        self.assertTrue(self.req('/api/verify')[1]['ok'])
        # Existing events remain intact when reopened by the new binary.
        self.assertIn('cadeia SHA-256 consistente', self.cli('verify').stdout)

    def test_optional_integrations_disabled_without_dependencies(self):
        self.start_server()
        status, data = self.req('/api/integrations')
        self.assertEqual(200, status)
        self.assertEqual('disabled', data['recoll']['state'])
        self.assertEqual('disabled', data['activitywatch']['state'])
        self.assertEqual(400, self.req('/api/integrations/recoll/search?q=teste')[0])
        self.assertEqual(400, self.req('/api/integrations/activitywatch/activity?bucket=test')[0])
        self.assertEqual(400, self.req('/api/integrations/configure', {'integration': 'activitywatch',
                         'enabled': 'true', 'url': 'http://example.com:5600'})[0])
        self.assertEqual(400, self.req('/api/integrations/configure', {'integration': 'recoll',
                         'enabled': 'true', 'config_dir': '/missing', 'roots': str(self.docs)})[0])
        self.assertEqual(0, self.req('/api/stats')[1]['events'])


    def test_recoll_queries_filter_paths_and_never_import_automatically(self):
        conf = self.home / 'recoll'
        conf.mkdir()
        (conf / 'recoll.conf').write_text('topdirs = ' + str(self.docs))
        good = self.docs / 'authorized.pdf'
        outside = self.home / 'private.pdf'
        # A symlink inside the authorized directory must not grant access outside it.
        (self.docs / 'escape.pdf').symlink_to(outside)
        records = [
            [outside.as_uri(), 'Private', 'application/pdf', '100', 'secret'],
            [(self.docs / 'escape.pdf').as_uri(), 'Symlink', 'application/pdf', '100', 'secret'],
            [good.as_uri(), 'Documento público', 'application/pdf', '100', 'Um trecho local'],
        ]
        output = '\n'.join(' '.join(base64.b64encode(cell.encode()).decode() for cell in row) for row in records)
        fakebin = self.home / 'bin'
        fakebin.mkdir()
        argvfile = self.home / 'recoll-argv.json'
        fake = fakebin / 'recollq'
        fake.write_text('#!' + sys.executable + '\nimport sys,json\nfrom pathlib import Path\n'
                        + 'Path(' + repr(str(argvfile)) + ').write_text(json.dumps(sys.argv))\n'
                        + 'print(' + repr(output) + ')\n')
        fake.chmod(0o700)
        self.start_server(extra_env={'PATH': str(fakebin) + os.pathsep + os.environ['PATH']})
        status, _ = self.req('/api/integrations/configure', {'integration': 'recoll', 'enabled': 'true',
                              'config_dir': str(conf), 'roots': str(self.docs)})
        self.assertEqual(200, status)
        query = 'termo; $(touch /tmp/lac-must-not-execute)'
        status, data = self.req('/api/integrations/recoll/search?' + urlencode({'q': query}))
        self.assertEqual(200, status)
        self.assertEqual([str(good)], [r['path'] for r in data['results']])
        self.assertEqual('Um trecho local', data['results'][0]['abstract'])
        self.assertFalse(data['recorded_in_lac'])
        self.assertEqual(query, json.loads(argvfile.read_text())[-1])
        self.assertEqual('--', json.loads(argvfile.read_text())[-2])
        self.assertEqual(0, self.req('/api/stats')[1]['events'])
        settings = Path(str(self.db) + '.integrations.json')
        self.assertEqual(0o600, settings.stat().st_mode & 0o777)
        self.assertIn('last_query_at', self.req('/api/integrations')[1]['recoll'])
        self.assertEqual(200, self.req('/api/integrations/configure', {'integration': 'recoll', 'enabled': 'false'})[0])
        self.assertEqual(400, self.req('/api/integrations/recoll/search?q=teste')[0])

    def test_activitywatch_bounded_aggregates_authorization_and_unavailability(self):
        requests = []
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                requests.append(self.path)
                if self.path == '/api/0/buckets/':
                    data = {'window-test': {'type': 'currentwindow'}, 'private': {'type': 'web.tab.current'}}
                else:
                    data = [{'id': 1, 'timestamp': '2026-11-09T12:00:00Z', 'duration': 60,
                             'data': {'app': 'editor', 'title': 'SECRET', 'url': 'private://data'}},
                            {'id': 2, 'timestamp': '2026-11-09T12:01:00Z', 'duration': 30,
                             'data': {'app': 'reader'}}]
                body = json.dumps(data).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        aw = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=aw.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(aw.server_close)
        self.addCleanup(aw.shutdown)
        self.start_server()
        self.assertEqual(200, self.req('/api/integrations/configure', {'integration': 'activitywatch', 'enabled': 'true',
                       'url': f'http://127.0.0.1:{aw.server_port}', 'buckets': 'window-test'})[0])
        self.assertEqual('reachable', self.req('/api/integrations')[1]['activitywatch']['state'])
        self.assertEqual(['/api/0/buckets/'], requests)
        self.assertEqual(400, self.req('/api/integrations/activitywatch/activity?bucket=private')[0])
        self.assertEqual(['/api/0/buckets/'], requests)
        query = urlencode({'bucket': 'window-test', 'start': '2026-11-09T12:00:30Z',
                           'end': '2026-11-09T13:00:00Z', 'limit': '2'})
        status, data = self.req('/api/integrations/activitywatch/activity?' + query)
        self.assertEqual(200, status)
        self.assertEqual({'editor': 30.0, 'reader': 30.0}, {r['app']: r['seconds'] for r in data['applications']})
        self.assertTrue(data['possibly_truncated'])
        self.assertNotIn('SECRET', json.dumps(data))
        self.assertNotIn('private://data', json.dumps(data))
        self.assertFalse(data['recorded_in_lac'])
        self.assertEqual(0, self.req('/api/stats')[1]['events'])
        for args in [{'start': '2026-11-09T12:00:00'}, {'start': '2026-01-01T00:00:00Z'}]:
            self.assertEqual(400, self.req('/api/integrations/activitywatch/activity?' +
                             urlencode({'bucket': 'window-test', **args}))[0])
        aw.shutdown()
        aw.server_close()
        self.assertEqual('unavailable', self.req('/api/integrations')[1]['activitywatch']['state'])
        self.assertEqual(200, self.req('/api/stats')[0])


    def test_default_restriction_on_loopback_and_lan_without_smtp_or_legacy_bypass(self):
        for index,bind in enumerate(('127.0.0.1','0.0.0.0')):
            self.start_server(bind=bind,token='',extra_env={'LAC_API_TOKEN':'legacy-token-'+'z'*40})
            self.assertEqual(401,self.req('/api/stats')[0])
            self.assertEqual(401,self.req('/api/events')[0])
            self.assertEqual(401,self.req('/api/stats',extra={'Authorization':'Bearer legacy-token-'+'z'*40})[0])
            status,data=self.req('/api/auth/status')
            self.assertEqual(200,status)
            self.assertFalse(data['authenticated'])
            self.assertFalse(data['smtp_configured'])
            self.assertEqual(503,self.req('/api/auth/request-code',{'email':f'pesquisador{index}@embrapa.br'})[0])
            self.assertEqual(403,self.req('/api/auth/request-code',{'email':'x@embrapa.br.evil'})[0])
            self.assertEqual(200,self.req('/api/health')[0])
            self.stop_server()

    def test_email_otp_over_tls_cookie_mcp_session_and_logout(self):
        mail=MailSink(self.home)
        self.addCleanup(mail.close)
        self.start_server(token='',extra_env=mail.environment)
        email='pesquisador@embrapa.br'
        status,data=self.req('/api/auth/request-code',{'email':email})
        self.assertEqual(200,status)
        self.assertNotIn('dev_code',data)
        code=mail.code()
        self.assertEqual(429,self.req('/api/auth/request-code',{'email':email})[0])
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=4)
        conn.request('POST','/api/auth/verify-code',body=urlencode({'email':email,'code':code}),
                     headers={'Content-Type':'application/x-www-form-urlencoded','X-LAC-Local':'1'})
        response=conn.getresponse();identity=json.loads(response.read());cookie=response.getheader('Set-Cookie')
        self.assertEqual(200,response.status);conn.close()
        self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Strict',cookie)
        self.assertTrue(identity['authenticated'])
        self.assertEqual(email,identity['email'])
        session=identity['session_token']
        cookie=cookie.split(';',1)[0]
        self.assertEqual(200,self.req('/api/stats',extra={'Cookie':cookie})[0])
        self.assertEqual(200,self.req('/api/stats',extra={'Authorization':'Bearer '+session})[0])
        self.assertEqual(401,self.req('/api/auth/verify-code',{'email':email,'code':code})[0])
        call={'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'lac_stats'}}
        self.assertFalse(self.mcp_exchange([call],token=session)[1]['result']['isError'])
        self.assertEqual(200,self.req('/api/auth/logout',{},extra={'Cookie':cookie})[0])
        self.assertEqual(401,self.req('/api/stats',extra={'Cookie':cookie})[0])
        self.assertFalse(self.req('/api/auth/status',extra={'Cookie':cookie})[1]['authenticated'])
        with sqlite3.connect(str(self.db)+'.auth.sqlite3') as auth:
            self.assertEqual(0,auth.execute('SELECT COUNT(*) FROM sessions').fetchone()[0])
        self.assertTrue(self.req('/api/health')[1]['auth_required'])

if __name__=='__main__': unittest.main(verbosity=2)
