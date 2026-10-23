#!/usr/bin/env bash
# Bật ADK Web UI cho demo Checkpoint 2.
#
#   ./run_adk_web.sh            # cổng 8000
#   ./run_adk_web.sh 8080       # cổng khác
set -euo pipefail

PORT="${1:-8000}"
VENV_PY="/Users/tungdl/Documents/CO5151/.venv-adk/bin/python"
ADK_BIN="/Users/tungdl/Documents/CO5151/.venv-adk/bin/adk"

if [[ ! -x "$ADK_BIN" ]]; then
  echo "Không thấy ADK CLI tại $ADK_BIN" >&2
  echo "Cài: $VENV_PY -m pip install 'google-adk' 'sqlalchemy[asyncio]' aiosqlite" >&2
  exit 1
fi

cd "$(dirname "$0")"
echo "ADK Web UI: http://127.0.0.1:${PORT}"
echo "Chọn app:   legalpilot_web"
echo "Câu demo:   Vốn điều lệ tối thiểu để cấp phép dịch vụ ví điện tử là bao nhiêu?"
echo

exec "$ADK_BIN" web --port "$PORT"
