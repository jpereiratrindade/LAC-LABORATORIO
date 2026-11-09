#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
umask 077

if [ "$#" -ne 0 ]; then
  printf 'Uso: ./iniciar.sh\nCompila, testa, instala e reinicia o LAC com inicialização no boot.\n' >&2
  exit 2
fi

for binary in cmake ctest python3 git systemctl loginctl install; do
  if ! command -v "$binary" >/dev/null; then
    printf 'Comando necessário não encontrado: %s\n' "$binary" >&2
    printf 'Fedora com dnf: sudo dnf install gcc-c++ cmake ninja-build sqlite-devel openssl-devel git python3\n' >&2
    exit 1
  fi
done

cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON
cmake --build build --parallel 2
ctest --test-dir build --output-on-failure
cmake --install build --prefix "$HOME/.local"

# Import only SMTP settings; never execute a project's environment file.
python3 scripts/configure_auth.py

mkdir -p "$HOME/.config/systemd/user"
install -m 644 systemd/lac-lan.service "$HOME/.config/systemd/user/lac-lan.service"
systemctl --user daemon-reload

# Linger makes this user manager start at boot and survive logout.
if [ "$(loginctl show-user "$(id -un)" -p Linger --value)" != yes ]; then
  loginctl enable-linger "$(id -un)"
fi
systemctl --user enable lac-lan.service
# enable --now alone would keep an old process running after installation.
systemctl --user restart lac-lan.service
systemctl --user is-active lac-lan.service
python3 - <<'PY'
import http.client
import json
from pathlib import Path
import time
for attempt in range(50):
    conn = http.client.HTTPConnection('127.0.0.1', 8765, timeout=1)
    try:
        conn.request('GET', '/api/health')
        response = conn.getresponse()
        if response.status == 200 and json.loads(response.read()).get('auth_required'):
            break
    except (OSError, ValueError, http.client.HTTPException):
        pass
    finally:
        conn.close()
    time.sleep(0.1)
else:
    raise SystemExit('A API não ficou disponível. Consulte: journalctl --user -u lac-lan.service -n 50')
PY
printf '\nLAC iniciado e habilitado no boot, independente de login.\n'
printf 'Neste computador: http://127.0.0.1:8765\n'
if command -v ip >/dev/null; then
  python3 - <<'PY'
import ipaddress
import json
import subprocess
for interface in json.loads(subprocess.check_output(['ip', '-j', '-4', 'address', 'show', 'up'])):
    if interface.get('operstate') != 'UP':
        continue
    for address in interface.get('addr_info', []):
        value = address.get('local', '')
        if address.get('scope') == 'global' and ipaddress.ip_address(value).is_private:
            print('Rede local: http://' + value + ':8765')
PY
fi
printf 'Acesso: informe seu e-mail @embrapa.br no painel e valide o código recebido.\n'
printf 'Estado: systemctl --user status lac-lan.service\n'
printf 'Recoll/ActivityWatch: configure em Integrações. MCP é iniciado pelo cliente LLM.\n'
