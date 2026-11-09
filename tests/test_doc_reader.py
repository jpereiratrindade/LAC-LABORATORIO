#!/usr/bin/env python3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'scripts'))

from lac_doc_reader import read_document, ALLOWED_EXTENSIONS


class DocReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='lac-doc-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_allowed_extensions_whitelist(self):
        self.assertEqual({'.pdf', '.md', '.txt', '.tex'}, ALLOWED_EXTENSIONS)

    def test_reject_unauthorized_extension(self):
        bad_file = self.root / 'script.sh'
        bad_file.write_text('#!/bin/bash\necho test\n')
        res = read_document(bad_file)
        self.assertFalse(res['ok'])
        self.assertIn('não autorizada', res['error'])

    def test_read_markdown(self):
        md = self.root / 'decisao.md'
        md.write_text('# Decisão Metodológica\nRIT e REA aplicados.\n', encoding='utf-8')
        res = read_document(md)
        self.assertTrue(res['ok'])
        self.assertEqual('.md', res['ext'])
        self.assertIn('RIT e REA aplicados.', res['text'])
        self.assertTrue(len(res['sha256']) == 64)

    def test_read_plain_text(self):
        txt = self.root / 'anotacao.txt'
        txt.write_text('Observação de campo 2026-11-09.\n', encoding='utf-8')
        res = read_document(txt)
        self.assertTrue(res['ok'])
        self.assertEqual('.txt', res['ext'])
        self.assertIn('Observação de campo', res['text'])

    def test_enforce_authorized_roots(self):
        outside = self.root / 'outside.md'
        outside.write_text('segredo fora da raiz', encoding='utf-8')
        safe_dir = self.root / 'safe'
        safe_dir.mkdir()
        
        # When safe_dir is the authorized root, outside.md must be rejected
        res = read_document(outside, authorized_roots=[safe_dir])
        self.assertFalse(res['ok'])
        self.assertIn('fora das fontes autorizadas', res['error'])

    def test_nonexistent_file(self):
        res = read_document(self.root / 'nao_existe.md')
        self.assertFalse(res['ok'])
        self.assertIn('não encontrado', res['error'])

    def test_integration_adapter_read_document(self):
        from lac_integrations import Adapters
        sample = self.root / 'artigo.tex'
        sample.write_text('\\section{Introducao}\nTexto cientifico.\n', encoding='utf-8')
        config_file = self.root / 'integrations.json'
        adapter = Adapters(config_file)
        res = adapter.dispatch('read_document', {'path': str(sample), 'roots': str(self.root)})
        self.assertTrue(res['ok'])
        self.assertEqual('artigo.tex', res['filename'])
        self.assertIn('Texto cientifico', res['text'])


if __name__ == '__main__':
    unittest.main()
