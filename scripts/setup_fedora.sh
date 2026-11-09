#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
for binary in cmake ninja g++ git python3 pkg-config; do
  command -v "$binary" >/dev/null || { echo "Falta $binary. Rode: sudo dnf install gcc-c++ cmake ninja-build sqlite-devel openssl-devel git python3 pkgconf-pkg-config" >&2; exit 1; }
done
pkg-config --exists sqlite3 openssl || { echo 'Faltam sqlite-devel e/ou openssl-devel' >&2; exit 1; }
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build -j "$(nproc)"
ctest --test-dir build --output-on-failure
printf '\nCompilação validada. Para instalar e iniciar o serviço: ./iniciar.sh\n'
