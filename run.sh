#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -f .env ]; then
    echo ".env not found — copying from .env.template"
    cp .env.template .env
    echo "Fill in .env with real values, then re-run this script."
    exit 1
fi

docker compose up --build
