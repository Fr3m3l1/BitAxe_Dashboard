#!/usr/bin/env bash
# Build and push the dashboard image.
# Run locally with:
#   docker run -d --name bitaxe-dashboard --restart unless-stopped \
#     --env-file .env -p 5000:5000 -v bitaxe-dashboard-data:/data \
#     fr3m3l/miner-app:latest
set -euo pipefail
cd "$(dirname "$0")"

docker build -t fr3m3l/miner-app:latest .
docker push fr3m3l/miner-app:latest
