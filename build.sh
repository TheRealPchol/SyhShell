#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PY="env/bin/python"

"$PY" -m pip install --quiet --upgrade pyinstaller

"$PY" -m PyInstaller \
    --noconfirm --clean \
    --name syhshell \
    --onefile \
    --hidden-import pytcc \
    --collect-all lupa \
    --collect-binaries pytcc \
    --collect-all cppyy \
    --collect-all cppyy_backend \
    --collect-all cpycppyy \
    --collect-all ziglang \
    --collect-submodules prompt_toolkit \
    --exclude-module kaa \
    --add-data "env/tcc-rtlib:tcc-rtlib" \
    --add-data "compilers/_cpp_run_helper.py:compilers" \
    syhshell.py
echo
echo "Готово: dist/syhshell"