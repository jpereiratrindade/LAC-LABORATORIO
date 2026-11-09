#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel 2
ctest --test-dir build --output-on-failure
cmake --install build --prefix "$HOME/.local"

# Keep credentials out of argv, logs and the source tree. Reuse an existing token.
python3 - <<'PY'
from pathlib import Path
import os
import secrets
os.umask(0o077)
folder = Path.home() / '.config/lac'
folder.mkdir(parents=True, exist_ok=True)
target = folder / 'server.env'
if not target.exists():
    with target.open('x') as stream:
        stream.write('LAC_API_TOKEN=' + secrets.token_hex(32) + '\n')
target.chmod(0o600)
(Path.home() / '.local/share/lac').mkdir(parents=True, exist_ok=True)
PY

mkdir -p "$HOME/.config/systemd/user"
install -m 644 systemd/lac-lan.service "$HOME/.config/systemd/user/lac-lan.service"
systemctl --user daemon-reload

# Linger makes this user manager start at boot and survive logout.
if [ "$(loginctl show-user "$(id -un)" -p Linger --value)" != yes ]; then
  loginctl enable-linger "$(id -un)"
fi
systemctl --user enable --now lac-lan.service
systemctl --user is-active lac-lan.service
printf '\nLAC habilitado no boot, independente de login.\nToken: ~/.config/lac/server.env (arquivo privado; não compartilhar).\n'
