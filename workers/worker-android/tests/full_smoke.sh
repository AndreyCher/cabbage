#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH=/opt/worker-android
python3 -c 'import logging; from app.android import AndroidDevice; AndroidDevice({}, logging.getLogger("qa")).wait_ready(240)'
bash /tmp/tests/qa-app/build.sh
python3 -m app.main
python3 /tmp/tests/verify_run.py
