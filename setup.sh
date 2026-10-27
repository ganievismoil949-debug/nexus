#!/usr/bin/env bash
set -euo pipefail
NEXUS_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$NEXUS_DIR"
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python download_assets.py
chmod +x "Launch Nexus.sh"
echo 'Nexus is ready. Run ./Launch\ Nexus.sh'
