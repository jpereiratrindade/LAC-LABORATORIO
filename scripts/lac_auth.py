#!/usr/bin/env python3
"""Institutional e-mail authentication. No anonymous fallback or development OTP mode."""
import argparse
from email.message import EmailMessage
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import smtplib
import sqlite3
import ssl
import sys
import time
from urllib.parse import parse_qsl

DOMAIN = 'embrapa.br'
TTL = 600
SESSION_TTL = 43200
EMAIL = re.compile(r"[a-z0-9](?:[a-z0-9.!#$%&'*+/=?^_`{|}~-]{0,62}[a-z0-9])?@embrapa\.br", re.ASCII)


def normalize_email(value):
    value = value.strip().lower()
    if not EMAIL.fullmatch(value) or '..' in value or '.@' in value:
        raise ValueError('Use um endereço institucional @embrapa.br válido.')
    return value


class EmailAuth:
    def __init__(self, path):
        os.umask(0o077)
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=3, isolation_level=None)
        self.path.chmod(0o600)
        self.db.executescript('''
          PRAGMA journal_mode=WAL;
          CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS challenges(email TEXT PRIMARY KEY, digest TEXT NOT NULL,
            expires INTEGER NOT NULL, attempts INTEGER NOT NULL, used INTEGER NOT NULL);
          CREATE TABLE IF NOT EXISTS sessions(digest TEXT PRIMARY KEY, email TEXT NOT NULL,
            expires INTEGER NOT NULL);
          CREATE TABLE IF NOT EXISTS requests(subject TEXT NOT NULL, action TEXT NOT NULL, at INTEGER NOT NULL);
          CREATE INDEX IF NOT EXISTS request_subject ON requests(subject,action,at);
          CREATE TABLE IF NOT EXISTS audit(at INTEGER NOT NULL, email TEXT NOT NULL,
            ip TEXT NOT NULL, action TEXT NOT NULL, decision TEXT NOT NULL);
        ''')
        self.db.execute('INSERT OR IGNORE INTO metadata VALUES(?,?)', ('secret', secrets.token_hex(32)))
        self.secret = self.db.execute('SELECT value FROM metadata WHERE key=?', ('secret',)).fetchone()[0].encode()
        self.db.execute('DELETE FROM requests WHERE at < ?', (int(time.time()) - 900,))
        self.db.execute('DELETE FROM sessions WHERE expires <= ?', (int(time.time()),))
        self.db.execute('DELETE FROM challenges WHERE expires < ?', (int(time.time()) - 900,))
        self.db.execute('DELETE FROM audit WHERE at < ?', (int(time.time()) - 30 * 86400,))

    def close(self):
        self.db.close()

    def audit(self, email, ip, action, decision):
        self.db.execute('INSERT INTO audit VALUES(?,?,?,?,?)', (int(time.time()), email, ip, action, decision))

    def reply(self, status, body, cookie=''):
        return {'status': status, 'body': body, 'cookie': cookie}

    def error(self, status, message):
        return self.reply(status, {'error': message})

    def rate(self, email, ip, action):
        now = int(time.time())
        self.db.execute('BEGIN IMMEDIATE')
        try:
            subjects = [('ip:' + ip, 15 if action == 'request' else 40),
                        ('email:' + email, 5 if action == 'request' else 20), ('global', 100 if action == 'request' else 300)]
            for subject, limit in subjects:
                count, recent = self.db.execute('SELECT COUNT(*), MAX(at) FROM requests WHERE subject=? AND action=? AND at>?',
                                               (subject, action, now - 900)).fetchone()
                if count >= limit or (action == 'request' and subject.startswith('email:') and recent is not None and now - recent < 60):
                    self.db.execute('ROLLBACK')
                    return False
            for subject, _ in subjects:
                self.db.execute('INSERT INTO requests VALUES(?,?,?)', (subject, action, now))
            self.db.execute('COMMIT')
            return True
        except Exception:
            self.db.execute('ROLLBACK')
            raise

    def smtp_config(self):
        return {key: os.environ.get('LAC_SMTP_' + key, '') for key in
                ('HOST', 'PORT', 'USER', 'PASS', 'FROM', 'SECURITY', 'CA_FILE')}

    def configured(self):
        return all(self.smtp_config()[key] for key in ('HOST', 'USER', 'PASS', 'FROM'))

    def send_code(self, email, code):
        conf = self.smtp_config()
        if not self.configured():
            raise ValueError('SMTP indisponível')
        port = int(conf['PORT'] or '587')
        security = conf['SECURITY'] or ('ssl' if port == 465 else 'starttls')
        if security not in ('ssl', 'starttls'):
            raise ValueError('SMTP exige TLS')
        context = ssl.create_default_context(cafile=conf['CA_FILE'] or None)
        message = EmailMessage()
        message['From'] = conf['FROM']
        message['To'] = email
        message['Subject'] = 'LAC — código de acesso institucional'
        message.set_content('Seu código de acesso ao LAC é: ' + code + '\n\n'
                            'Válido por 10 minutos, para uso único, com no máximo 5 tentativas.\n'
                            'Se você não solicitou este acesso, ignore esta mensagem.\n')
        client = smtplib.SMTP_SSL(conf['HOST'], port, timeout=4, context=context) if security == 'ssl' else smtplib.SMTP(conf['HOST'], port, timeout=4)
        with client as smtp:
            smtp.ehlo()
            if security == 'starttls':
                smtp.starttls(context=context)
                smtp.ehlo()
            smtp.login(conf['USER'], conf['PASS'])
            smtp.send_message(message)

    def code_digest(self, email, code):
        return hmac.new(self.secret, (email + ':' + code).encode(), hashlib.sha256).hexdigest()

    def allowed(self, email):
        allowed = os.environ.get('LAC_AUTH_ALLOWED_EMAILS', '')
        return not allowed or email in {entry.strip().lower() for entry in allowed.split(',') if entry.strip()}

    def request_code(self, args):
        try:
            email = normalize_email(args.get('email', ''))
        except ValueError as exc:
            return self.error(403, str(exc))
        ip = args.get('ip', '')
        if not self.rate(email, ip, 'request'):
            self.audit(email, ip, 'request', 'rate_limited')
            return self.error(429, 'Aguarde antes de solicitar outro código (mínimo de 60 segundos entre envios).')
        generic = self.reply(200, {'ok': True, 'message': 'Se o endereço estiver autorizado, o código será enviado por e-mail. Validade: 10 minutos.'})
        if not self.allowed(email):
            self.audit(email, ip, 'request', 'not_allowed')
            return generic
        if not self.configured():
            self.audit(email, ip, 'request', 'smtp_unconfigured')
            return self.error(503, 'O envio de códigos ainda não está configurado. Contate o administrador.')
        code = f'{secrets.randbelow(1000000):06d}'
        digest = self.code_digest(email, code)
        self.db.execute('INSERT OR REPLACE INTO challenges VALUES(?,?,?,0,1)', (email, digest, int(time.time()) + TTL))
        try:
            self.send_code(email, code)
        except (OSError, ValueError, smtplib.SMTPException):
            self.audit(email, ip, 'request', 'smtp_failed')
            return self.error(503, 'Não foi possível enviar o código. Tente novamente mais tarde.')
        self.db.execute('UPDATE challenges SET used=0 WHERE email=? AND digest=?', (email, digest))
        self.audit(email, ip, 'request', 'sent')
        return generic

    def cookie(self, token, age):
        secure = '; Secure' if os.environ.get('LAC_COOKIE_SECURE') == '1' else ''
        return f'lac_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={age}' + secure

    def verify_code(self, args):
        try:
            email = normalize_email(args.get('email', ''))
        except ValueError:
            return self.error(401, 'Código inválido ou expirado.')
        code, ip = args.get('code', ''), args.get('ip', '')
        if not self.rate(email, ip, 'verify'):
            return self.error(429, 'Muitas tentativas. Aguarde e tente novamente.')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute('SELECT digest,expires,attempts,used FROM challenges WHERE email=?', (email,)).fetchone()
            valid = bool(row and row[1] > int(time.time()) and row[2] < 5 and not row[3] and self.allowed(email))
            if row:
                self.db.execute('UPDATE challenges SET attempts=attempts+1 WHERE email=?', (email,))
            valid = valid and bool(re.fullmatch('[0-9]{6}', code)) and hmac.compare_digest(row[0], self.code_digest(email, code))
            if not valid:
                self.audit(email, ip, 'verify', 'rejected')
                self.db.execute('COMMIT')
                return self.error(401, 'Código inválido ou expirado. Após 5 tentativas, solicite um novo código.')
            self.db.execute('UPDATE challenges SET used=1 WHERE email=?', (email,))
            token = secrets.token_urlsafe(32)
            self.db.execute('INSERT INTO sessions VALUES(?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), email, int(time.time()) + SESSION_TTL))
            self.audit(email, ip, 'verify', 'accepted')
            self.db.execute('COMMIT')
            return self.reply(200, {'authenticated': True, 'email': email, 'session_token': token,
                                    'expires_in': SESSION_TTL}, self.cookie(token, SESSION_TTL))
        except Exception:
            self.db.execute('ROLLBACK')
            raise

    def identity(self, token):
        if not token or len(token) > 256 or not token.isascii():
            return None
        service = os.environ.get('LAC_SERVICE_TOKEN', '')
        if len(service) >= 32 and service.isascii() and hmac.compare_digest(token, service):
            return {'authenticated': True, 'service': True, 'email': None}
        row = self.db.execute('SELECT email FROM sessions WHERE digest=? AND expires>?',
                              (hashlib.sha256(token.encode()).hexdigest(), int(time.time()))).fetchone()
        if row and self.allowed(row[0]):
            return {'authenticated': True, 'service': False, 'email': row[0]}
        return None

    def dispatch(self, action, args):
        if action == 'request-code':
            return self.request_code(args)
        if action == 'verify-code':
            return self.verify_code(args)
        token = args.get('token', '')
        identity = self.identity(token)
        if action == 'authorize':
            return self.reply(200, identity) if identity else self.error(401, 'Entre com seu e-mail @embrapa.br para acessar o LAC.')
        if action == 'status':
            return self.reply(200, {**(identity or {'authenticated': False}), 'domain': DOMAIN,
                                    'smtp_configured': self.configured(), 'auth_required': True})
        if action == 'logout':
            self.db.execute('DELETE FROM sessions WHERE digest=?', (hashlib.sha256(token.encode()).hexdigest(),))
            return self.reply(200, {'ok': True}, self.cookie('', 0))
        return self.error(404, 'Operação não encontrada.')


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--action', required=True)
    parser.add_argument('--params-stdin', action='store_true', required=True)
    options = parser.parse_args()
    auth = None
    try:
        payload = sys.stdin.buffer.read(16385)
        if len(payload) > 16384:
            raise ValueError('Payload too large')
        auth = EmailAuth(options.config)
        reply = auth.dispatch(options.action, dict(parse_qsl(payload.decode(), keep_blank_values=True)))
    except (OSError, ValueError, sqlite3.Error, UnicodeError):
        reply = {'status': 503, 'body': {'error': 'Autenticação indisponível. Contate o administrador.'}, 'cookie': ''}
    finally:
        if auth:
            auth.close()
    print(json.dumps(reply, ensure_ascii=False))


if __name__ == '__main__':
    main()
