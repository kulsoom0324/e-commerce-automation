# Deploy on a Hostinger VPS (Ubuntu)

1. **DNS** (Hostinger -> Domains -> DNS): add two `A` records pointing to the VPS IP,
   e.g. `fte` and `api-fte` (for `fte.codecraftai.net` / `api-fte.codecraftai.net`).
2. **Server:** `ssh root@<VPS_IP>`, then:
   ```bash
   apt-get update && apt-get install -y git
   git clone https://github.com/kulsoom0324/e-commerce-automation.git
   cd e-commerce-automation && git checkout fix/workers-and-auth   # or main once merged
   cp deploy/.env.production.example deploy/.env.production
   nano deploy/.env.production      # fill POSTGRES_PASSWORD, SECRET_KEY, ENCRYPTION_KEY, GEMINI_API_KEY...
   bash deploy/deploy.sh
   ```
   (A private repo needs a GitHub token or deploy key on the server.)
3. **Check:** `https://<API_DOMAIN>/health`, `https://<API_DOMAIN>/docs`, `https://<APP_DOMAIN>`.
4. **Logs:** `docker compose --env-file deploy/.env.production -f deploy/docker-compose.prod.yml logs -f backend`
5. **Update later:** `git pull && bash deploy/deploy.sh`

Postgres and Redis are not exposed to the internet (internal Docker network only).
Google login: set `GOOGLE_CLIENT_ID` and add `https://<APP_DOMAIN>` to the OAuth client's authorized JavaScript origins.
