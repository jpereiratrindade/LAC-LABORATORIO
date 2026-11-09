#!/usr/bin/env python3
"""Authentication policy tests. SMTP is replaced in-process; no real e-mail is sent."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('lac_auth', Path(__file__).resolve().parents[1]/'scripts/lac_auth.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='lac-auth-test-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'auth.sqlite3'
        self.env = patch.dict(os.environ, {'LAC_SMTP_HOST':'mail.example.invalid','LAC_SMTP_USER':'sender',
                     'LAC_SMTP_PASS':'secret','LAC_SMTP_FROM':'sender@example.invalid',
                     'LAC_AUTH_ALLOWED_EMAILS':'','LAC_SERVICE_TOKEN':''})
        self.env.start();self.addCleanup(self.env.stop)
        self.sent = []
        self.sender = patch.object(module.EmailAuth, 'send_code', lambda _auth, email, code: self.sent.append((email, code)))
        self.sender.start();self.addCleanup(self.sender.stop)
        self.random = patch.object(module.secrets, 'randbelow', return_value=123456)
        self.random.start();self.addCleanup(self.random.stop)
        self.auth = module.EmailAuth(self.path)
        self.addCleanup(lambda: self.auth.close())
        self.email='pesquisador@embrapa.br'

    def request(self, email=None):
        return self.auth.request_code({'email':email or self.email,'ip':'192.0.2.1'})

    def verify(self, code='123456'):
        return self.auth.verify_code({'email':self.email,'code':code,'ip':'192.0.2.1'})

    def test_exact_domain_and_normalization(self):
        for email in ('nome@gmail.com','nome@embrapa.br.evil','nome@fooembrapa.br','nome@sub.embrapa.br',
                      'nome@@embrapa.br','nome\r\nBcc:x@embrapa.br','nomé@embrapa.br','nome..x@embrapa.br'):
            self.assertEqual(403,self.request(email)['status'],email)
        self.assertEqual([],self.sent)
        self.assertEqual(200,self.request(' Pesquisador@EMBRAPA.BR ')['status'])
        self.assertEqual(self.email,self.sent[0][0])

    def test_one_time_code_hashed_sessions_and_http_only_cookie(self):
        self.assertEqual(200,self.request()['status'])
        result=self.verify()
        self.assertEqual(200,result['status'])
        self.assertIn('HttpOnly; SameSite=Strict;',result['cookie'])
        token=result['body']['session_token']
        self.assertGreaterEqual(len(token),40)
        self.assertEqual(self.email,self.auth.identity(token)['email'])
        digest=self.auth.db.execute('SELECT digest FROM sessions').fetchone()[0]
        self.assertEqual(hashlib.sha256(token.encode()).hexdigest(),digest)
        self.assertNotEqual('123456',self.auth.db.execute('SELECT digest FROM challenges').fetchone()[0])
        self.assertEqual(401,self.verify()['status'])
        self.assertEqual(0o600,self.path.stat().st_mode&0o777)

    def test_five_attempts_lock_out_even_correct_code(self):
        self.request()
        for _ in range(5):self.assertEqual(401,self.verify('000000')['status'])
        self.assertEqual(401,self.verify()['status'])
        self.assertEqual(0,self.auth.db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0])

    def test_expiration_and_logout_revoke_access(self):
        self.request()
        self.auth.db.execute('UPDATE challenges SET expires=?',(int(time.time())-1,))
        self.assertEqual(401,self.verify()['status'])
        self.auth.db.execute('UPDATE challenges SET expires=?',(int(time.time())+600,))
        token=self.verify()['body']['session_token']
        self.auth.db.execute('UPDATE sessions SET expires=?',(int(time.time())-1,))
        self.assertIsNone(self.auth.identity(token))
        self.auth.db.execute('UPDATE sessions SET expires=?',(int(time.time())+600,))
        result=self.auth.dispatch('logout',{'token':token})
        self.assertIn('Max-Age=0',result['cookie'])
        self.assertIsNone(self.auth.identity(token))

    def test_cooldown_survives_reopening_and_resend_invalidates_old_code(self):
        self.request()
        self.auth.close();self.auth=module.EmailAuth(self.path)
        self.assertEqual(429,self.request()['status'])
        self.auth.db.execute('UPDATE requests SET at=at-61')
        self.random.stop()
        with patch.object(module.secrets,'randbelow',return_value=654321):self.assertEqual(200,self.request()['status'])
        self.assertEqual(401,self.verify()['status'])
        self.assertEqual(200,self.verify('654321')['status'])

    def test_smtp_failure_and_missing_settings_never_open_access(self):
        with patch.object(module.EmailAuth,'send_code',side_effect=OSError('smtp failed')):
            self.assertEqual(503,self.request()['status'])
        self.assertEqual(401,self.verify()['status'])
        os.environ['LAC_SMTP_PASS']=''
        os.environ['LAC_DEV_AUTH']='1'
        os.environ['MORFO_DEV_AUTH']='1'
        self.addCleanup(os.environ.pop,'LAC_DEV_AUTH',None)
        self.addCleanup(os.environ.pop,'MORFO_DEV_AUTH',None)
        self.auth.db.execute('DELETE FROM requests')
        result=self.request()
        self.assertEqual(503,result['status'])
        self.assertNotIn('dev_code',result['body'])
        self.assertIsNone(self.auth.identity('123456'))

    def test_optional_allowlist_and_no_legacy_shared_token(self):
        self.assertIsNone(self.auth.identity('é'*43))
        os.environ['LAC_AUTH_ALLOWED_EMAILS']='outro@embrapa.br'
        self.assertEqual(200,self.request()['status'])
        self.assertEqual([],self.sent)
        self.assertEqual(401,self.verify()['status'])
        with patch.dict(os.environ,{'LAC_API_TOKEN':'old-shared-token-'+'x'*40}):
            self.assertIsNone(self.auth.identity(os.environ['LAC_API_TOKEN']))

    def test_concurrent_verification_consumes_code_once(self):
        self.request()
        barrier=threading.Barrier(2)
        def attempt(_):
            other=module.EmailAuth(self.path)
            try:
                barrier.wait(timeout=3)
                return other.verify_code({'email':self.email,'code':'123456','ip':'192.0.2.1'})['status']
            finally:other.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual([200,401],sorted(pool.map(attempt,range(2))))

    def test_bootstrap_imports_only_smtp_without_executing_environment(self):
        root=Path(self.temp.name)/'bootstrap';root.mkdir()
        checkout=root/'lac';checkout.mkdir()
        morfo=root/'MORFO';morfo.mkdir()
        home=root/'home';home.mkdir()
        marker=root/'must-not-exist'
        password='$(touch '+str(marker)+')'
        (morfo/'.env').write_text("MORFO_SMTP_HOST=mail.example.invalid\nMORFO_SMTP_USER=sender@example.invalid\n"
                                 +"MORFO_SMTP_PASS='"+password+"'\nMORFO_SMTP_FROM=sender@example.invalid\nUNRELATED_SECRET=do-not-copy\n")
        target=home/'.config/lac/server.env';target.parent.mkdir(parents=True)
        target.write_text('LAC_API_TOKEN=legacy-credential\n')
        result=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'scripts/configure_auth.py')],
                              cwd=checkout,env={**os.environ,'HOME':str(home)},capture_output=True,text=True,check=True)
        saved=target.read_text()
        self.assertFalse(marker.exists())
        self.assertNotIn('LAC_API_TOKEN',saved)
        self.assertNotIn('LAC_SERVICE_TOKEN',saved)
        self.assertNotIn('UNRELATED_SECRET',saved)
        self.assertIn('LAC_SMTP_PASS=',saved)
        self.assertIn(password,saved)
        self.assertNotIn(password,result.stdout+result.stderr)
        self.assertEqual(0o600,target.stat().st_mode&0o777)

    def test_sessions_survive_restart_but_can_be_removed_from_allowlist(self):
        self.request();token=self.verify()['body']['session_token']
        self.auth.close();self.auth=module.EmailAuth(self.path)
        self.assertEqual(self.email,self.auth.identity(token)['email'])
        os.environ['LAC_AUTH_ALLOWED_EMAILS']='outro@embrapa.br'
        self.assertIsNone(self.auth.identity(token))


if __name__=='__main__':unittest.main()
