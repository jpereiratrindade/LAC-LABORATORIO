#!/usr/bin/env python3
"""Bounded document text reader for LAC.

Restricted to substantive text/research documents: .pdf, .md, .txt, .tex.
Never executes code, follows directives inside documents, or reads outside authorized roots.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ALLOWED_EXTENSIONS = {'.pdf', '.md', '.txt', '.tex'}
MAX_RAW_BYTES = 32 * 1024 * 1024  # 32 MiB
DEFAULT_MAX_TEXT_CHARS = 16384     # Safe context boundary for LLM/summaries


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def extract_pdf_text(path: Path, max_chars: int) -> tuple[str, str | None]:
    try:
        proc = subprocess.run(
            ['pdftotext', '-layout', '-enc', 'UTF-8', str(path), '-'],
            capture_output=True,
            timeout=10,
            check=False,
        )
        if proc.returncode != 0:
            return '', f"pdftotext falhou com código {proc.returncode}"
        text = proc.stdout.decode('utf-8', errors='replace').strip()
        if not text:
            return '', 'Documento sem camada de texto legível (possível digitalização/imagem sem OCR)'
        truncated = len(text) > max_chars
        return text[:max_chars], ('Texto truncado no limite seguro' if truncated else None)
    except FileNotFoundError:
        return '', 'Utilitário pdftotext não encontrado no sistema'
    except subprocess.TimeoutExpired:
        return '', 'Tempo limite excedido na extração de texto do PDF'


def extract_plain_text(path: Path, max_chars: int) -> tuple[str, str | None]:
    try:
        raw = path.read_bytes()
        text = raw.decode('utf-8', errors='replace').strip()
        truncated = len(text) > max_chars
        return text[:max_chars], ('Texto truncado no limite seguro' if truncated else None)
    except Exception as e:
        return '', f'Falha ao ler arquivo de texto: {e}'


def read_document(
    file_path: str | Path,
    authorized_roots: list[str | Path] | None = None,
    max_chars: int = DEFAULT_MAX_TEXT_CHARS,
) -> dict:
    target = Path(file_path).resolve()

    if not target.is_file():
        return {'ok': False, 'error': f'Arquivo não encontrado: {target}', 'path': str(target)}

    ext = target.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return {
            'ok': False,
            'error': f'Extensão {ext} não autorizada para interpretação documental (permitidas: {sorted(ALLOWED_EXTENSIONS)})',
            'path': str(target),
            'ext': ext,
        }

    # If roots are provided, enforce boundary
    if authorized_roots:
        is_inside = False
        for r in authorized_roots:
            root_path = Path(r).resolve()
            try:
                target.relative_to(root_path)
                is_inside = True
                break
            except ValueError:
                continue
        if not is_inside:
            return {
                'ok': False,
                'error': f'Arquivo fora das fontes autorizadas: {target}',
                'path': str(target),
            }

    raw_size = target.stat().st_size
    if raw_size > MAX_RAW_BYTES:
        return {
            'ok': False,
            'error': f'Arquivo excede o limite máximo suportado ({raw_size} > {MAX_RAW_BYTES} bytes)',
            'path': str(target),
            'bytes': raw_size,
        }

    file_hash = sha256_file(target)

    if ext == '.pdf':
        text, warning = extract_pdf_text(target, max_chars)
    else:
        text, warning = extract_plain_text(target, max_chars)

    return {
        'ok': True,
        'path': str(target),
        'filename': target.name,
        'ext': ext,
        'bytes': raw_size,
        'sha256': file_hash,
        'chars': len(text),
        'text': text,
        'warning': warning,
    }


def main():
    parser = argparse.ArgumentParser(description='Leitor delimitado de documentos para o LAC (.pdf, .md, .txt, .tex)')
    parser.add_argument('path', help='Caminho do documento a ser lido')
    parser.add_argument('--root', action='append', dest='roots', help='Diretório raiz autorizado')
    parser.add_argument('--max-chars', type=int, default=DEFAULT_MAX_TEXT_CHARS, help='Limite máximo de caracteres')
    parser.add_argument('--json', action='store_true', default=True, help='Saída em formato JSON')
    args = parser.parse_args()

    res = read_document(args.path, authorized_roots=args.roots, max_chars=args.max_chars)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if not res.get('ok'):
        sys.exit(1)


if __name__ == '__main__':
    main()
