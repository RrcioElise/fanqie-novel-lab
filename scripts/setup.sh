#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
if [ ! -f .env ]; then
  cp .env.example .env
  echo "已创建 .env，请编辑模型配置后再运行。"
fi
python -m fanqie_novel_lab.cli init-db
