#!/usr/bin/env bash
# Builds the Python agent into an onedir bundle via PyInstaller.
# Output: client/resources/agent/  (rs-agent binary + support files)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$SCRIPT_DIR/../agent"
RESOURCES_DIR="$SCRIPT_DIR/../resources/agent"

echo "==> Building rs-agent (onedir)..."
cd "$AGENT_DIR"

uv sync --no-dev
uv pip install pyinstaller

# --optimize 2: compile .pyc at level 2 — removes docstrings AND assert statements
uv run pyinstaller rs_agent.spec --distpath dist --noconfirm --optimize 2

# Sync the onedir output into resources/agent/
# rsync preserves _internal/ and all support libs
rm -rf "$RESOURCES_DIR"
mkdir -p "$RESOURCES_DIR"
cp -r dist/rs-agent/. "$RESOURCES_DIR/"
chmod +x "$RESOURCES_DIR/rs-agent"

echo "==> Done: $RESOURCES_DIR"
ls -lh "$RESOURCES_DIR/rs-agent"
