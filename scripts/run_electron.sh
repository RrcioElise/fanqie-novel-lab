#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -d .venv ]; then
  echo "未找到 .venv，先运行：bash scripts/setup.sh" >&2
  exit 1
fi
cd electron-client
if [ ! -d node_modules ]; then
  npm install --cache ../.npm-cache
fi
npm start --cache ../.npm-cache
