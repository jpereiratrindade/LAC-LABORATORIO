#!/usr/bin/env python3
"""Prepare private LAC SMTP settings, optionally reusing the local MORFO sender."""
import os
from pathlib import Path
import shlex
import tempfile


def read_env(path):
    values = {}
    if not path.is_file():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        if key.startswith('export '):
            key = key[7:]
        parts = shlex.split(value, comments=True)
        values[key.strip()] = ' '.join(parts)
    return values


def main():
    os.umask(0o077)
    target = Path.home()/'.config/lac/server.env'
    target.parent.mkdir(parents=True, exist_ok=True)
    config = read_env(target)
    # Retire the old shared browser token. Service credentials are never generated implicitly.
    config.pop('LAC_API_TOKEN', None)
    source = Path(os.environ.get('LAC_SMTP_SOURCE', str(Path.cwd().parent/'MORFO/.env')))
    original = read_env(source)
    for field in ('HOST','PORT','USER','PASS','FROM','SECURITY','CA_FILE'):
        if not config.get('LAC_SMTP_'+field) and original.get('MORFO_SMTP_'+field):
            config['LAC_SMTP_'+field] = original['MORFO_SMTP_'+field]
    if config.get('LAC_SMTP_HOST') == 'smtp.gmail.com' and config.get('LAC_SMTP_PASS'):
        config['LAC_SMTP_PASS'] = ''.join(config['LAC_SMTP_PASS'].split())
    if not config.get('LAC_SMTP_FROM') and config.get('LAC_SMTP_USER'):
        config['LAC_SMTP_FROM'] = config['LAC_SMTP_USER']
    config.setdefault('LAC_SMTP_PORT', '587')
    fd, name = tempfile.mkstemp(prefix='.server-env-', dir=target.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            for key, value in sorted(config.items()):
                if not key.replace('_','').isalnum() or any(c in value for c in '\r\n\0'):
                    raise ValueError('Invalid environment setting')
                quoted = value.replace('\\','\\\\').replace('"','\\"')
                stream.write(key+'="'+quoted+'"\n')
        os.replace(name, target)
    finally:
        if os.path.exists(name): os.unlink(name)
    (Path.home()/'.local/share/lac').mkdir(parents=True,exist_ok=True)
    ready = all(config.get('LAC_SMTP_'+key) for key in ('HOST','USER','PASS','FROM'))
    print('SMTP configurado; login exclusivo por código enviado ao e-mail @embrapa.br.' if ready else
          'SMTP pendente: configure ~/.config/lac/server.env. O acesso permanecerá restrito.')


if __name__ == '__main__':
    main()
