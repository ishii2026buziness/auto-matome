#!/usr/bin/env bash
# Compatibility wrapper for the standard CLI entrypoint.
# Prefer `python -m cli run` directly in docs, containers, and systemd units.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

unset CLAUDECODE
source .venv/bin/activate
AUTO_MATOME_DEPLOY_SITE=1 PYTHONPATH=src python -m cli run "$@"
