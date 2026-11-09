"""Private TLS SMTP sink for integration tests. Never relays or sends external mail."""
from email import policy
from email.parser import BytesParser
from pathlib import Path
import queue
import re
import socketserver
import ssl
import subprocess
import threading


class MailSink:
    def __init__(self, folder):
        folder=Path(folder)
        cert,key=folder/'smtp.crt',folder/'smtp.key'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),
                        '-out',str(cert),'-days','1','-subj','/CN=localhost',
                        '-addext','subjectAltName=DNS:localhost'],check=True,capture_output=True,timeout=10)
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,key)
        messages=self.messages=queue.Queue()
        class Server(socketserver.ThreadingTCPServer):
            allow_reuse_address=True
            daemon_threads=True
            def get_request(self):
                sock,address=super().get_request()
                sock.settimeout(4)
                return context.wrap_socket(sock,server_side=True),address
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.wfile.write(b'220 localhost test SMTP\r\n')
                while True:
                    line=self.rfile.readline(8192)
                    if not line:return
                    command=line.split(b' ',1)[0].strip().upper()
                    if command in (b'EHLO',b'HELO'):
                        self.wfile.write(b'250-localhost\r\n250 AUTH PLAIN\r\n')
                    elif command==b'AUTH':self.wfile.write(b'235 authenticated\r\n')
                    elif command==b'DATA':
                        self.wfile.write(b'354 send message\r\n')
                        data=[]
                        while True:
                            part=self.rfile.readline(8192)
                            if part in (b'.\r\n',b''):break
                            data.append(part)
                        messages.put(BytesParser(policy=policy.default).parsebytes(b''.join(data)))
                        self.wfile.write(b'250 accepted locally\r\n')
                    elif command==b'QUIT':self.wfile.write(b'221 bye\r\n');return
                    else:self.wfile.write(b'250 OK\r\n')
        self.server=Server(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.environment={'LAC_SMTP_HOST':'localhost','LAC_SMTP_PORT':str(self.server.server_address[1]),
                          'LAC_SMTP_SECURITY':'ssl','LAC_SMTP_CA_FILE':str(cert),
                          'LAC_SMTP_USER':'test-sender','LAC_SMTP_PASS':'test-password',
                          'LAC_SMTP_FROM':'sender@example.invalid'}

    def code(self):
        message=self.messages.get(timeout=5)
        assert message['To'].endswith('@embrapa.br')
        return re.search(r': ([0-9]{6})',message.get_content()).group(1)

    def close(self):
        self.server.shutdown();self.server.server_close()
