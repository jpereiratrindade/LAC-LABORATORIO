#!/usr/bin/env python3
"""Local provider contracts with synthetic content; never contacts a real model."""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
from lac_local_llm import InferenceError, OllamaLocal, validate_context, validate_summary

CONTEXT = json.loads((Path(__file__).parent / 'fixtures' / 'assistant-context.json').read_text())
RESULT = {'schema_version': '1', 'summary': 'Foi proposta uma revisão; validação em campo pendente.',
          'source_refs': ['event:101'], 'gaps': ['Conteúdo do arquivo não recuperado.']}


class ProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = {}
        state = cls.state

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                self.respond(self.path, None)

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                state.setdefault('payloads', []).append((self.path, payload))
                self.respond(self.path, payload)

            def respond(self, path, _):
                state.setdefault('paths', []).append(path)
                if state.get('redirect'):
                    self.send_response(307)
                    self.send_header('Location', 'https://example.invalid/api/chat')
                    self.end_headers()
                    return
                if state.get('oversized'):
                    data = b' ' * (1024 * 1024 + 1)
                else:
                    if path == '/api/tags':
                        state['tag_reads'] = state.get('tag_reads', 0) + 1
                        digest = ('b' if state.get('changed') and state['tag_reads'] > 1 else 'a') * 64
                        content = {'models': [] if state.get('missing') else [
                            {'name': 'fixture:7b', 'digest': digest, 'size': 100}]}
                    elif path == '/api/show':
                        content = {'capabilities': ['completion']}
                        if state.get('remote'):
                            content['remote_host'] = 'https://example.invalid'
                    elif path == '/api/chat':
                        if state.get('stall'):
                            state['chat_started'].set()
                            state['release'].wait(3)
                        content = {'model': state.get('response_model', 'fixture:7b'), 'done': True, 'done_reason': state.get('done_reason', 'stop'),
                                   'message': {'content': state.get('raw_result', json.dumps(state.get('result', RESULT)))}}
                    else:
                        content = {}
                    data = json.dumps(content).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.server.daemon_threads = True
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = 'http://127.0.0.1:' + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.state.clear()
        self.state.update(chat_started=threading.Event(), release=threading.Event())

    def tearDown(self):
        self.state['release'].set()

    def expect_error(self, code, callback):
        with self.assertRaises(InferenceError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def test_summary_has_provenance_and_direct_connection_despite_proxy(self):
        with patch.dict(os.environ, {'HTTP_PROXY': 'http://127.0.0.1:1', 'http_proxy': 'http://127.0.0.1:1'}):
            output = OllamaLocal(self.url).summarize('fixture:7b', CONTEXT)
        self.assertEqual(output['result'], RESULT)
        self.assertEqual(output['project_ref'], CONTEXT['project_ref'])
        self.assertEqual(len(output['context_hash']), 64)
        self.assertEqual(output['model_digest'], 'a' * 64)
        chat = next(p for path, p in self.state['payloads'] if path == '/api/chat')
        self.assertIs(chat['stream'], False)
        self.assertNotIn('tools', chat)

    def test_forbids_remote_endpoints_and_credentials(self):
        for url in ('https://127.0.0.1:11434', 'http://10.0.0.1:11434', 'http://example.com',
                    'http://user:pass@127.0.0.1', 'http://127.0.0.1/api', 'http://127.0.0.1?x=1'):
            with self.subTest(url=url):
                self.expect_error('invalid_context', lambda: OllamaLocal(url))

    def test_refuses_cloud_models_before_generation(self):
        self.state['remote'] = True
        self.expect_error('remote_model', lambda: OllamaLocal(self.url).summarize('fixture:7b', CONTEXT))
        self.assertNotIn('/api/chat', self.state['paths'])

    def test_missing_model_does_not_download(self):
        self.state['missing'] = True
        self.expect_error('model_missing', lambda: OllamaLocal(self.url).summarize('fixture:7b', CONTEXT))
        self.assertEqual(self.state['paths'], ['/api/tags'])

    def test_redirect_is_not_followed(self):
        self.state['redirect'] = True
        self.expect_error('remote_model', lambda: OllamaLocal(self.url).inspect('fixture:7b'))

    def test_rejects_invented_references(self):
        self.state['result'] = {**RESULT, 'source_refs': ['event:999']}
        self.expect_error('invalid_output', lambda: OllamaLocal(self.url).summarize('fixture:7b', CONTEXT))

    def test_rejects_truncated_generation(self):
        self.state['done_reason'] = 'length'
        self.expect_error('invalid_output', lambda: OllamaLocal(self.url).summarize('fixture:7b', CONTEXT))

    def test_rejects_response_from_different_model(self):
        self.state['response_model'] = 'different:7b'
        self.expect_error('invalid_output', lambda: OllamaLocal(self.url).summarize('fixture:7b', CONTEXT))

    def test_rejects_model_change_during_inference(self):
        self.state['changed'] = True
        self.expect_error('model_changed', lambda: OllamaLocal(self.url).summarize('fixture:7b', CONTEXT))

    def test_rejects_duplicate_json_keys(self):
        self.state['raw_result'] = '{"summary":"a","summary":"b"}'
        self.expect_error('invalid_output', lambda: OllamaLocal(self.url).summarize('fixture:7b', CONTEXT))

    def test_response_size_is_bounded(self):
        self.state['oversized'] = True
        self.expect_error('invalid_response', lambda: OllamaLocal(self.url).inspect('fixture:7b'))

    def test_no_context_means_no_request(self):
        self.expect_error('invalid_context', lambda: OllamaLocal(self.url).summarize('fixture:7b', {'project_ref': 'project:1', 'sources': []}))
        self.assertNotIn('paths', self.state)

    def test_cancel_before_request(self):
        cancel = threading.Event()
        cancel.set()
        self.expect_error('cancelled', lambda: OllamaLocal(self.url).summarize('fixture:7b', CONTEXT, cancel))
        self.assertNotIn('paths', self.state)

    def test_cancel_in_flight(self):
        self.state['stall'] = True
        cancel = threading.Event()
        def stop():
            self.state['chat_started'].wait(2)
            cancel.set()
        stopper = threading.Thread(target=stop)
        stopper.start()
        started = time.monotonic()
        self.expect_error('cancelled', lambda: OllamaLocal(self.url, timeout=2).summarize('fixture:7b', CONTEXT, cancel))
        stopper.join()
        self.assertLess(time.monotonic() - started, 1.5)

    def test_timeout_in_flight(self):
        self.state['stall'] = True
        self.expect_error('timeout', lambda: OllamaLocal(self.url, timeout=0.1).summarize('fixture:7b', CONTEXT))

    def test_context_and_output_constraints(self):
        invalid = deepcopy(CONTEXT)
        invalid['sources'][0]['text'] = 'x' * 7000
        self.expect_error('invalid_context', lambda: validate_context(invalid))
        invalid = deepcopy(CONTEXT)
        invalid['sources'].append(invalid['sources'][0])
        self.expect_error('invalid_context', lambda: validate_context(invalid))
        for changed in ({'extra': True}, {'gaps': ['x' * 201]}, {'source_refs': ['event:101', 'event:101']}, {'summary': ''}):
            self.expect_error('invalid_output', lambda: validate_summary({**RESULT, **changed}, {'event:101'}))


if __name__ == '__main__':
    unittest.main()
