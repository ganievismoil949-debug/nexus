#!/usr/bin/env bash
set -euo pipefail
NEXUS_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$NEXUS_DIR"
export PATH="$HOME/.local/bin:$PATH"
if [[ "${XDG_SESSION_TYPE:-}" == wayland && -n "${WAYLAND_DISPLAY:-}" ]]; then
  export GDK_BACKEND="${NEXUS_GDK_BACKEND:-wayland}"
fi
NEXUS_PYTHON="$NEXUS_DIR/.venv/bin/python"
if [[ ! -x "$NEXUS_PYTHON" ]]; then NEXUS_PYTHON=python3; fi
exec "$NEXUS_PYTHON" "$NEXUS_DIR/app.py" "$@"
