#!/usr/bin/env python3
"""LAC Executive Briefing Generator.
Generates an automated, decision-oriented summary of recent work from the LAC HTTP API.
No external packages required.
"""
import argparse
import http.client
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from lac_integrations import local_endpoint


def get_token(host, port):
    token = os.environ.get('LAC_SESSION_TOKEN') or os.environ.get('LAC_SERVICE_TOKEN') or os.environ.get('LAC_API_TOKEN', '')
    if token:
        return token
    session_file = Path.home() / '.config/lac/mcp-sessions.json'
    if session_file.exists():
        try:
            data = json.loads(session_file.read_text())
            key = f'http://{host}:{port}'
            session = data.get(key, {})
            if session.get('expires_at', 0) > time.time():
                return session.get('token', '')
        except Exception:
            pass
    return ''


def fetch_events(host, port, token, project=None, days=1):
    conn = http.client.HTTPConnection(host, port, timeout=15)
    headers = {'X-LAC-Agent': 'briefing'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    
    params = {'limit': '300'}
    if project:
        params['project'] = project
    
    path = f'/api/events?{urlencode(params)}'
    try:
        conn.request('GET', path, headers=headers)
        resp = conn.getresponse()
        data = resp.read().decode('utf-8')
        if resp.status != 200:
            raise RuntimeError(f'HTTP {resp.status}: {data}')
        events = json.loads(data)
    finally:
        conn.close()

    if days and days > 0:
        cutoff = time.time() - (days * 86400)
        filtered = []
        for e in events:
            # parse occurred_at or recorded_at
            t_str = e.get('occurred_at') or e.get('recorded_at')
            try:
                dt = datetime.fromisoformat(t_str.replace('Z', '+00:00'))
                if dt.timestamp() >= cutoff:
                    filtered.append(e)
            except Exception:
                filtered.append(e)
        return filtered
    return events


def fetch_todos(host, port, token):
    conn = http.client.HTTPConnection(host, port, timeout=15)
    headers = {'X-LAC-Agent': 'briefing'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    try:
        conn.request('GET', '/api/todos', headers=headers)
        resp = conn.getresponse()
        data = resp.read().decode('utf-8')
        if resp.status != 200:
            return []
        return json.loads(data)
    finally:
        conn.close()


def generate_briefing(events, todos, project=None, days=1):
    # Categorize events
    commits = []
    files_changed = []
    decisions = []
    notes = []
    corrections = []
    closed_todos = []

    for e in events:
        k = e.get('kind', '')
        if k == 'git_commit':
            commits.append(e)
        elif k in ('file_added', 'file_changed', 'file_missing'):
            files_changed.append(e)
        elif k == 'decision':
            decisions.append(e)
        elif k == 'correction':
            corrections.append(e)
        elif k == 'todo_closed':
            closed_todos.append(e)
        elif k == 'note':
            notes.append(e)

    period_desc = 'Hoje / Últimas 24 horas' if days == 1 else f'Últimos {days} dias'
    proj_desc = f'Projeto: {project}' if project else 'Todos os projetos'

    lines = []
    lines.append(f"# LAC — Síntese Executiva Automatizada")
    lines.append(f"*{period_desc} · {proj_desc} · Gerado em: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*\n")

    # 1. Avanços Observados
    lines.append("## 1. 🚀 Avanços Observados (Código e Documentos)")
    if commits or files_changed:
        for c in commits:
            title = c.get('title', '').strip()
            author = ' (Git)' if c.get('actor') == 'observer' else ''
            lines.append(f"- **Commit:** {title}{author}")
        for f in files_changed:
            lines.append(f"- **Arquivo:** {f.get('title', '')} ({f.get('kind', '')})")
    else:
        lines.append("- *Nenhum commit ou alteração de documento observada no intervalo.*")
    lines.append("")

    # 2. Decisões Arquiteturais e Metodológicas
    lines.append("## 2. 💡 Decisões & Hipóteses Firmadas")
    if decisions:
        for d in decisions:
            actor = ' [LLM]' if d.get('actor') == 'llm' else ' [Pessoa]'
            lines.append(f"- **{d.get('title', '')}**{actor}: {d.get('body', '')}")
    else:
        lines.append("- *Nenhuma nova decisão declarada no período.*")
    lines.append("")

    # 3. Gestão Adaptativa: Ajustes de Rota e Correções
    lines.append("## 3. 🔄 Gestão Adaptativa (Correções & Aprendizados)")
    if corrections:
        for corr in corrections:
            lines.append(f"- ⚠️ **{corr.get('title', '')}**: {corr.get('body', '')}")
    else:
        lines.append("- *Nenhum desvio ou refutação de hipótese registrado. Trajetória mantida.*")
    lines.append("")

    # 4. Contexto Adicional & Notas de Trabalho
    if notes:
        lines.append("## 4. 📝 Notas e Contexto")
        for n in notes:
            lines.append(f"- **{n.get('title', '')}**: {n.get('body', '')}")
        lines.append("")

    # 5. Pendências e Próximos Passos
    lines.append("## 5. 📌 Foco para o Próximo Ciclo (O que falta)")
    if closed_todos:
        lines.append("**Concluído recentemente:**")
        for ct in closed_todos:
            lines.append(f"-  {ct.get('title', '')}")
    
    if todos:
        lines.append("**Pendências abertas para continuidade:**")
        for t in todos:
            lines.append(f"- ⏳ **#{t.get('id')} [{t.get('project')}]** {t.get('title')}: {t.get('body', '')}")
    else:
        lines.append("-  *Nenhuma pendência aberta no momento. Tudo em dia!*")
    
    lines.append("\n---\n*Critério: Observações são registros passivos de arquivos; declarações indicam autoria humana ou de IA.*")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8765')
    parser.add_argument('--project', help='Filtrar por projeto')
    parser.add_argument('--days', type=int, default=1, help='Dias retroativos (padrão: 1 = hoje/24h)')
    args = parser.parse_args()

    host, port = local_endpoint(args.url, allow_lan=True)
    token = get_token(host, port)
    if not token:
        print("Erro: Sessão não encontrada ou expirada. Autentique antes com lac_mcp.py --login", file=sys.stderr)
        sys.exit(1)

    try:
        events = fetch_events(host, port, token, args.project, args.days)
        todos = fetch_todos(host, port, token)
        report = generate_briefing(events, todos, args.project, args.days)
        print(report)
    except Exception as exc:
        print(f"Erro ao gerar síntese: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
