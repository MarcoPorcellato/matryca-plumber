#!/usr/bin/env bash
# Re-index matryca-plumber with GitNexus semantic embeddings (BM25 + vector).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
mkdir -p "$HF_HOME"

export NODE_OPTIONS="--import ./scripts/gitnexus-hf-cache.mjs${NODE_OPTIONS:+ $NODE_OPTIONS}"

if command -v gitnexus >/dev/null 2>&1; then
  GITNEXUS=gitnexus
elif [[ -x "$ROOT/tools/gitnexus-cli/node_modules/.bin/gitnexus" ]]; then
  GITNEXUS="$ROOT/tools/gitnexus-cli/node_modules/.bin/gitnexus"
else
  echo "gitnexus CLI not found (install globally or run: npm install --prefix tools/gitnexus-cli gitnexus@1.6.1)" >&2
  exit 1
fi

exec "$GITNEXUS" analyze --embeddings --skip-agents-md "$@"
