#!/usr/bin/env bash
# Run on the Ubuntu VPS as root:  bash deploy/deploy.sh
# Installs Docker if missing, opens ports 22/80/443, then builds and starts the stack.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env.production ]; then
  echo "Missing deploy/.env.production (copy .env.production.example and fill it in)." >&2
  exit 1
fi
for v in APP_DOMAIN API_DOMAIN POSTGRES_PASSWORD SECRET_KEY ENCRYPTION_KEY; do
  if ! grep -Eq "^${v}=.+" .env.production; then
    echo "Set ${v} in deploy/.env.production" >&2
    exit 1
  fi
done

if ! command -v docker >/dev/null 2>&1; then
  # get.docker.com may not support a brand-new Ubuntu release yet; fall back to Ubuntu's own packages.
  curl -fsSL https://get.docker.com | sh || {
    apt-get update && apt-get install -y docker.io docker-compose-v2
  }
fi

if command -v ufw >/dev/null 2>&1; then
  ufw allow OpenSSH
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw --force enable
fi

docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.production -f docker-compose.prod.yml ps
echo
echo "Done. Check: https://$(grep ^API_DOMAIN= .env.production | cut -d= -f2)/health"
