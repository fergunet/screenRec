#!/usr/bin/env bash
# Lanza ScreenRec creando el entorno virtual la primera vez.
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
fi
exec .venv/bin/python screenrec.py "$@"
