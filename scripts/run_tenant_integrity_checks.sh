#!/usr/bin/env bash

set -euo pipefail

if [[ -f "venv/bin/activate" ]]; then
  source venv/bin/activate
fi

export DJANGO_SETTINGS_MODULE=intelliwiz_config.settings.production
export PYTHONPATH="$(pwd):${PYTHONPATH:-}"

echo "[1/2] Running Django system checks..."
python3 manage.py check

echo "[2/2] Running multi-tenant verification suite..."
python3 scripts/verify_tenant_setup.py --verbose

echo "Tenant integrity checks completed successfully."
