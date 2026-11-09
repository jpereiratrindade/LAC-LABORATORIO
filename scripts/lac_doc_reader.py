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


def clean_latex(s: str) -> str:
    import re
    s = re.sub(r'\\[a-zA-Z]+\*?(?:\[.*?\])?\{(.*?)\}', r'\1', s)
    s = re.sub(r'\\[a-zA-Z]+', ' ', s)
    s = re.sub(r'[\{\}\$]', '', s)
    s = re.sub(r'\\\\', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def extract_metadata(text: str, ext: str, filename: str) -> dict:
    import re
    title = ''
    author = ''
    date = ''

    if ext == '.tex':
        m = re.search(r'\\title(?:\[.*?\])?\{((?:[^{}]|\{[^{}]*\})*)\}', text, re.DOTALL)
        if m:
            title = clean_latex(m.group(1))

        if not title:
            m = re.search(r'\\begin\{center\}(.*?)\\end\{center\}', text, re.DOTALL)
            if m:
                bolds = re.findall(r'\\(?:Large|large|textbf|huge|Huge)\s*\{?([^\\\}]+)\}?', m.group(1))
                if bolds:
                    title = ' '.join(clean_latex(b) for b in bolds if len(b.strip()) > 3)

        if not title:
            m = re.search(r'\\section\*?\{((?:[^{}]|\{[^{}]*\})*)\}', text)
            if m:
                cand = clean_latex(m.group(1))
                if not any(cand.lower().startswith(x) for x in ['introdu', 'resumo', 'sumário', 'apresenta']):
                    title = cand

        m_team = re.search(r'Equipe:\s*([^\n\\]+)', text, re.IGNORECASE)
        if m_team:
            author = m_team.group(1).strip()
        elif not author:
            m_auth = re.search(r'\\author(?:\[.*?\])?\{((?:[^{}]|\{[^{}]*\})*)\}', text, re.DOTALL)
            if m_auth:
                author = clean_latex(m_auth.group(1))

    elif ext == '.md':
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        for line in lines:
            if line.startswith('# '):
                title = line[2:].strip()
                break
        if text.startswith('---'):
            m_fm_title = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', text, re.MULTILINE)
            if m_fm_title:
                title = m_fm_title.group(1).strip()

    elif ext == '.pdf':
        lines = [line.strip() for line in text.split('\n') if len(line.strip()) > 3]
        if lines:
            if len(lines) > 1 and len(lines[0]) < 60 and len(lines[1]) > 10:
                title = f"{lines[0]} {lines[1]}".strip()
            else:
                title = lines[0]

    if not title or len(title) < 4:
        clean_name = Path(filename).stem
        clean_name = re.sub(r'[-_]+', ' ', clean_name)
        title = clean_name.strip().capitalize()

    thematic_keywords = []
    text_lower = text.lower()
    known_themes = [
        'NDVI', 'Sentinel-2', 'Sensoriamento Remoto', 'Solo', 'Pastagens',
        'Pampa', 'Campanha Gaúcha', 'Agricultura Familiar', 'Pecuária', 'Leite',
        'TED', 'RestauraBio', 'Epagri', 'Embrapa', 'Sistemas Socioecológicos',
        'Inteligência Agropecuária', 'Grafo Argumentativo', 'Metodologia REA'
    ]
    for kt in known_themes:
        if kt.lower() in text_lower:
            thematic_keywords.append(kt)

    return {
        'title': title,
        'author': author if author else None,
        'date': date if date else None,
        'themes': thematic_keywords[:6],
    }


def read_document(
    file_path: str | Path,
    authorized_roots: list[str | Path] | None = None,
    max_chars: int = DEFAULT_MAX_TEXT_CHARS,
) -> dict:
    target = Path(file_path)
    if not target.is_file() and authorized_roots:
        for r in authorized_roots:
            candidate = (Path(r) / target).resolve()
            if candidate.is_file():
                target = candidate
                break
    target = target.resolve()

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

    meta = extract_metadata(text, ext, target.name)

    return {
        'ok': True,
        'path': str(target),
        'filename': target.name,
        'title': meta['title'],
        'author': meta['author'],
        'date': meta['date'],
        'themes': meta['themes'],
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
