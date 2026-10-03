# Digital FTE — Environment Variables & Credentials Setup Guide

> **Last updated:** 2026-08-25
> **Purpose:** Step-by-step guide to get all required API keys, secrets, and credentials, then add them to your `.env` file.

---

## 📖 Table of Contents

1. [Quick Start](#quick-start)
2. [Required vs Optional Credentials](#required-vs-optional)
3. [Step-by-Step: Each Credential](#step-by-step)
4. [Complete .env File Template](#complete-env-file)
5. [Verification Checklist](#verification)

---

## Quick Start

**Minimum to run the app:**

```bash
# 1. Copy template
cd Backend
cp .env.example .env

# 2. Edit .env — at minimum, set:
#    - GEMINI_API_KEY (for AI features)
#    - SECRET_KEY (for JWT — generate random 32+ char string)
#    - DATABASE_URL (already has default for local postgres)
#    - REDIS_URL (already has default for local redis)

# 3. Generate secure SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 4. Start infrastructure
docker-compose up -d

# 5. Run backend
uvicorn src.main:app --reload

# 6. Run frontend (separate terminal)
cd ../frontend
npm install
npm run dev
```

**Without setting any credentials:**
- Auth works (signup/login)
- Database works (if PostgreSQL running)
- AI features will return "GEMINI_API_KEY is empty" error
- External platform integrations won't work

---

## Required vs Optional Credentials

| Credential | Required? | Used For | Free Tier? |
|---|---|---|---|
| `SECRET_KEY` | ✅ **Required** | JWT token signing | N/A (generate yourself) |
| `DATABASE_URL` | ✅ **Required** | PostgreSQL connection | N/A (local docker) |
| `REDIS_URL` | ✅ **Required** | Event bus | N/A (local docker) |
| `GEMINI_API_KEY` | 🟡 **Highly recommended** | AI content generation | ✅ Yes (generous) |
| `GOOGLE_CLIENT_ID` | 🟡 For Google login | OAuth login | ✅ Yes |
| `SHOPIFY_API_KEY` + `SHOPIFY_API_SECRET` | ⚪ Optional | Shopify integration | ✅ Free dev store |
| `WOOCOMMERCE_*` | ⚪ Optional | WooCommerce integration | ✅ Yes |
| `BIGCOMMERCE_*` | ⚪ Optional | BigCommerce integration | ✅ Trial |
| `AMAZON_*` | ⚪ Optional | Amazon SP-API | ⚠️ Requires approval |
| `DARAZ_*` | ⚪ Optional | Daraz integration | ✅ Yes |
| `SMTP_*` | ⚪ Optional | Email verification + password reset | ✅ Yes (Gmail) |
| `TIKTOK_*`, `LINKEDIN_*` | ⚪ Optional | Social media posting | ⚠️ App review needed |
| `GEMINI_API_KEY` (image) | ⚪ Optional | Image generation | ✅ Same as above |
| `DALLE_API_KEY` | ⚪ Optional | DALL-E image generation | 💰 Paid |

---

## Step-by-Step: Each Credential

### 1. SECRET_KEY (JWT Token Signing) — REQUIRED

**What it does:** Signs JWT tokens used for authentication. If compromised, attackers can forge user sessions.

**How to get:**

```bash
# Option 1: Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Option 2: OpenSSL
openssl rand -base64 32

# Option 3: Node.js
node -e "console.log(require('crypto').randomBytes(32).toString('base64'))"

# Option 4: Online (less secure)
# Visit: https://generate-secret.vercel.app/32
```

**Example output:**
```
aB3xK9mN2pQ7vR5tY8uW1zC4dF6gH0jL3nM5oP8qS2tU
```

**Add to .env:**
```env
SECRET_KEY=aB3xK9mN2pQ7vR5tY8uW1zC4dF6gH0jL3nM5oP8qS2tU
```

**Validation:** Must be 32+ characters. App will reject shorter values in production.

---

### 2. DATABASE_URL (PostgreSQL) — REQUIRED

**What it does:** Connection string to your PostgreSQL database.

**Default (local Docker):**
```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/digital_fte
```

**How to set up locally:**

**Option A: Docker (recommended for dev)**
```bash
cd Backend
docker-compose up -d postgres
# Wait 5 seconds for postgres to start
```

**Option B: Local PostgreSQL install**
```bash
# Install PostgreSQL 16
# Windows: Download from https://www.postgresql.org/download/windows/
# Mac: brew install postgresql@16
# Linux: sudo apt install postgresql-16

# Create database
psql -U postgres
CREATE DATABASE digital_fte;
CREATE USER fte_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE digital_fte TO fte_user;
\q

# Update .env
DATABASE_URL=postgresql+asyncpg://fte_user:your_password@localhost:5432/digital_fte
```

**Option C: Cloud (production)**
- **Supabase:** Free tier — https://supabase.com → New project → Settings → Database → Connection string (use the "Transaction" pooler URL with `?pgbouncer=true`)
- **Neon:** Free tier — https://neon.tech → Create project → Connection string
- **Railway:** https://railway.app → New project → Add PostgreSQL → Variables → `DATABASE_URL`

**Example for Supabase:**
```env
DATABASE_URL=postgresql+asyncpg://postgres.xxxx:password@aws-0-us-east-1.pooler.supabase.com:6543/postgres?pgbouncer=true
```

---

### 3. REDIS_URL (Event Bus) — REQUIRED

**What it does:** Connection string to Redis (used for inter-agent pub/sub messaging).

**Default (local Docker):**
```env
REDIS_URL=redis://localhost:6379/0
```

**How to set up:**

**Option A: Docker (recommended)**
```bash
cd Backend
docker-compose up -d redis
```

**Option B: Local install**
```bash
# Windows: https://github.com/microsoftarchive/redis/releases
# Mac: brew install redis && brew services start redis
# Linux: sudo apt install redis-server && sudo systemctl start redis
```

**Option C: Cloud (production)**
- **Upstash:** Free tier (10K commands/day) — https://upstash.com → Create database → Copy `REDIS_URL`
- **Redis Cloud:** https://redis.com/cloud/ → Free tier (30MB)
- **Railway:** Add Redis plugin → Copy `REDIS_URL`

**Example for Upstash:**
```env
REDIS_URL=rediss://default:AbC123...@us1-perfect-koala-31234.upstash.io:31234
```

**Note:** Use `rediss://` (double s) for TLS connections.

---

### 4. GEMINI_API_KEY (AI Features) — HIGHLY RECOMMENDED

**What it does:** Authenticates calls to Google Gemini API for content generation, comment replies, customer support, analytics, and workflow planning.

**How to get:**

1. Visit **Google AI Studio:** https://aistudio.google.com/app/apikey
2. Sign in with your Google account
3. Click **"Create API Key"**
4. Select or create a Google Cloud project
5. Copy the generated key (starts with `AIzaSy...`)

**Free tier limits (as of 2026):**
- 15 requests per minute (RPM)
- 1 million tokens per minute (TPM)
- 1,500 requests per day (RPD)
- Enough for ~65 active customers

**Add to .env:**
```env
GEMINI_API_KEY=AIzaSyAbCdEfGhIjKlMnOpQrStUvWxYz1234567890
```

**Also used for image generation** (same key, different endpoint).

**Note:** The SDK package is `google-generativeai` (already in requirements.txt).

---

### 5. GOOGLE_CLIENT_ID (Google OAuth Login) — RECOMMENDED

**What it does:** Allows users to sign in with their Google account.

**How to get:**

1. Visit **Google Cloud Console:** https://console.cloud.google.com/
2. Create a new project (or select existing) → Name it "Digital FTE"
3. **Enable APIs:** APIs & Services → Library → Search "Google Identity" → Enable
4. **Configure OAuth Consent Screen:**
   - APIs & Services → OAuth consent screen
   - User type: External (for public users)
   - App name: "Digital FTE"
   - Support email: your email
   - Scopes: `email`, `profile`, `openid`
   - Save
5. **Create OAuth Client:**
   - APIs & Services → Credentials → Create Credentials → OAuth client ID
   - Application type: **Web application**
   - Name: "Digital FTE Web"
   - Authorized JavaScript origins:
     - `http://localhost:3000` (dev)
     - `https://your-production-domain.com` (prod)
   - Authorized redirect URIs:
     - `http://localhost:3000` (dev)
     - `https://your-production-domain.com` (prod)
   - Click **Create**
6. Copy the **Client ID** (looks like `123456789-abc...xyz.apps.googleusercontent.com`)

**Add to Backend .env:**
```env
GOOGLE_CLIENT_ID=123456789-abcdefghijklmnop.apps.googleusercontent.com
```

**Add to Frontend .env.local:**
```env
NEXT_PUBLIC_GOOGLE_CLIENT_ID=123456789-abcdefghijklmnop.apps.googleusercontent.com
```

**Verification:** Visit http://localhost:3000 → Click "Sign in with Google" button → Should open Google popup.

---

### 6. SHOPIFY_API_KEY + SHOPIFY_API_SECRET (Shopify Integration) — OPTIONAL

**What it does:** Allows users to connect their Shopify stores via OAuth.

**How to get:**

1. Visit **Shopify Partners:** https://partners.shopify.com/
2. Sign up (free) or log in
3. **Apps** → Create app → **Create app manually**
4. App name: "Digital FTE"
5. App URL: `http://localhost:8000` (for dev)
6. Allowed redirection URL(s):
   - `http://localhost:8000/api/v1/auth/shopify/callback`
   - `https://your-production.com/api/v1/auth/shopify/callback`
7. **Configuration:**
   - Scopes: `read_products`, `read_orders`, `read_inventory` (minimum)
   - Webhooks: Optional (we use webhooks to receive order notifications)
8. Copy **API key** and **API secret key**

**Set up a development store** (free):
- Partners dashboard → Stores → Add store → Create development store
- Use this store to test the integration

**Add to .env:**
```env
SHOPIFY_API_KEY=your_api_key_here
SHOPIFY_API_SECRET=your_api_secret_here
SHOPIFY_SCOPES=read_products,read_orders,read_inventory
SHOPIFY_REDIRECT_URI=http://localhost:8000/api/v1/auth/shopify/callback
BACKEND_PUBLIC_URL=http://localhost:8000
FRONTEND_SUCCESS_URL=http://localhost:3000/dashboard
```

---

### 7. SMTP Credentials (Email Verification + Password Reset) — OPTIONAL

**What it does:** Sends verification emails and password reset links to users.

**Recommended: Gmail (free for low volume)**

**How to set up Gmail:**

1. Go to your Google Account → Security → 2-Step Verification (enable it)
2. Go to https://myaccount.google.com/apppasswords
3. App: "Mail" → Device: "Other" → Name: "Digital FTE"
4. Click Generate → Copy the 16-character password

**Add to .env:**
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your.email@gmail.com
SMTP_PASSWORD=abcd efgh ijkl mnop  # 16-char app password
EMAIL_FROM=your.email@gmail.com
```

**Alternative: SendGrid (better for production)**
- Sign up: https://sendgrid.com (free 100 emails/day)
- Settings → API Keys → Create API Key
- Use `apikey` as username and the API key as password

```env
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=SG.xxxxxxxxxxxxxxxxxxxx
EMAIL_FROM=noreply@yourdomain.com
```

**Note:** If `SMTP_HOST` is empty, the email service becomes a no-op (logs a warning but doesn't crash).

---

### 8. WOOCOMMERCE Credentials — OPTIONAL

**What it does:** Allows users to connect WooCommerce stores.

**How to get:**

1. Log into your WordPress + WooCommerce site
2. **WooCommerce → Settings → Advanced → REST API**
3. Click **Add key**
4. Description: "Digital FTE Integration"
5. User: Admin user
6. Permissions: **Read**
7. Click **Generate API key**
8. Copy the **Consumer key** and **Consumer secret**

**Add to .env:**
```env
WOOCOMMERCE_REDIRECT_URI=http://localhost:8000/api/v1/auth/woocommerce/callback
```

**Note:** The consumer key/secret are entered by the user in the frontend connect flow, not stored in .env.

---

### 9. BIGCOMMERCE Credentials — OPTIONAL

**How to get:**

1. Visit **BigCommerce Developer Portal:** https://developer.bigcommerce.com/
2. Sign up → My Apps → Create app
3. App name: "Digital FTE"
4. OAuth scopes: `Products (read)`, `Orders (read)`, `Customers (read)`
5. Callback URL: `http://localhost:8000/api/v1/auth/bigcommerce/callback`
6. Copy **Client ID** and **Client Secret**

**Add to .env:**
```env
BIGCOMMERCE_CLIENT_ID=your_client_id
BIGCOMMERCE_CLIENT_SECRET=your_client_secret
BIGCOMMERCE_REDIRECT_URI=http://localhost:8000/api/v1/auth/bigcommerce/callback
```

---

### 10. AMAZON SP-API Credentials — OPTIONAL (REQUIRES APPROVAL)

**What it does:** Connects Amazon Seller Central accounts.

**⚠️ Note:** Requires Amazon approval (can take 1-2 weeks). Skip if not needed.

**How to get:**

1. **Register as Amazon Developer:** https://developer.amazon.com/
2. **Apply for SP-API access:** https://developer.amazon.com/selling-partner-api
3. **Register your application:**
   - Login with Seller Central credentials
   - Developer → Register your application
   - Use case: "Integrate with Digital FTE platform"
4. After approval:
   - Get **Client ID**, **Client Secret**, **Refresh Token**

**Add to .env:**
```env
AMAZON_CLIENT_ID=amzn1.sp.solution.xxx
AMAZON_CLIENT_SECRET=your_secret
AMAZON_REDIRECT_URI=http://localhost:8000/api/v1/auth/amazon/callback
AMAZON_REFRESH_TOKEN=Atzr|xxx
```

---

### 11. DARAZ Credentials — OPTIONAL

**How to get:**

1. Visit **Daraz Open Platform:** https://openplatform.daraz.pk/
2. Sign up as a developer
3. **My Apps → Create App**
4. App name: "Digital FTE"
5. Callback URL: `http://localhost:8000/api/v1/auth/daraz/callback`
6. Copy **App Key** and **App Secret**

**Add to .env:**
```env
DARAZ_APP_KEY=your_app_key
DARAZ_APP_SECRET=your_app_secret
DARAZ_REDIRECT_URI=http://localhost:8000/api/v1/auth/daraz/callback
```

---

### 12. TIKTOK_CLIENT_KEY + TIKTOK_CLIENT_SECRET — OPTIONAL

**What it does:** Allows users to connect TikTok accounts for auto-posting.

**How to get:**

1. Visit **TikTok for Developers:** https://developers.tiktok.com/
2. Sign up → My Apps → Create app
3. App name: "Digital FTE"
4. Category: "Business tools"
5. Scopes: `user.info.basic`, `video.upload`, `video.publish`
6. **Important:** TikTok requires app review for `video.publish` scope (takes 3-7 days)
7. Copy **Client Key** and **Client Secret**

**Add to .env:**
```env
TIKTOK_CLIENT_KEY=your_client_key
TIKTOK_CLIENT_SECRET=your_client_secret
```

---

### 13. LINKEDIN_CLIENT_ID + LINKEDIN_CLIENT_SECRET — OPTIONAL

**How to get:**

1. Visit **LinkedIn Developer Portal:** https://www.linkedin.com/developers/
2. My Apps → Create app
3. App name: "Digital FTE"
4. Use LinkedIn API products:
   - **Sign In with LinkedIn** (for OAuth)
   - **Marketing Developer Platform** (for posting)
5. Redirect URL: `http://localhost:8000/api/v1/auth/linkedin/callback`
6. Copy **Client ID** and **Client Secret**

**Add to .env:**
```env
LINKEDIN_CLIENT_ID=your_client_id
LINKEDIN_CLIENT_SECRET=your_client_secret
```

---

### 14. DALLE_API_KEY (Alternative Image Generation) — OPTIONAL

**What it does:** Use DALL-E 3 instead of Gemini for image generation.

**How to get:**

1. Visit **OpenAI Platform:** https://platform.openai.com/
2. Sign up → API Keys → Create new secret key
3. Add $5+ credits to your account (DALL-E is paid only)
4. Copy the key (starts with `sk-...`)

**Add to .env:**
```env
DALLE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
IMAGE_MODEL_DEFAULT=gemini-2.0-flash-exp  # or "dall-e-3"
```

**Cost:** ~$0.04 per image (1024x1024 standard quality)

---

## Complete .env File Template

Here's a complete `.env` file with all variables (commented out optional ones):

```bash
# ═══════════════════════════════════════════════════════════════
# Digital FTE Backend .env
# Copy this to Backend/.env and fill in your values
# ═══════════════════════════════════════════════════════════════

# ─── Application ──────────────────────────────────────────────
APP_NAME="Digital FTE Agent"
APP_VERSION="1.0.0"
ENV=development
DEBUG=true

# ─── Database (PostgreSQL) ──────────────────────────────────
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/digital_fte

# ─── Redis (Event Bus) ───────────────────────────────────────
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=

# ─── Orchestrator ────────────────────────────────────────────
ORCHESTRATOR_URL=http://localhost:8000
AGENT_TOKEN=

# ─── JWT (REQUIRED) ─────────────────────────────────────────
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY=REPLACE_WITH_RANDOM_32_CHAR_STRING_HERE_PLEASE_PLEASE_PLEASE
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# ─── Google OAuth (RECOMMENDED) ─────────────────────────────
# Get from: https://console.cloud.google.com/ → APIs & Services → Credentials
GOOGLE_CLIENT_ID=

# ─── CORS ────────────────────────────────────────────────────
CORS_ORIGINS=*
FRONTEND_URL=http://localhost:3000
BACKEND_PUBLIC_URL=http://localhost:8000
FRONTEND_SUCCESS_URL=http://localhost:3000/dashboard

# ─── Email (SMTP) ────────────────────────────────────────────
# Gmail example:
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=your.email@gmail.com
# SMTP_PASSWORD=your_16_char_app_password
# EMAIL_FROM=your.email@gmail.com
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
EMAIL_FROM=

# ─── Rate Limiting ───────────────────────────────────────────
RATE_LIMIT_LOGIN_MAX_ATTEMPTS=5
RATE_LIMIT_LOGIN_WINDOW_SECONDS=900

# ─── LLM (Google Gemini) — HIGHLY RECOMMENDED ───────────────
# Get from: https://aistudio.google.com/app/apikey
GEMINI_API_KEY=AIzaSy_YOUR_KEY_HERE
LLM_API_KEY=                    # Legacy alias — leave empty
LLM_MODEL=gemini-2.0-flash-exp

# ─── Encryption (Fernet) ────────────────────────────────────
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=

# ─── Platform: Shopify ──────────────────────────────────────
# Get from: https://partners.shopify.com/
SHOPIFY_API_KEY=
SHOPIFY_API_SECRET=
SHOPIFY_SCOPES=read_products,read_orders,read_inventory
SHOPIFY_REDIRECT_URI=http://localhost:8000/api/v1/auth/shopify/callback

# ─── Platform: WooCommerce ──────────────────────────────────
WOOCOMMERCE_REDIRECT_URI=http://localhost:8000/api/v1/auth/woocommerce/callback

# ─── Platform: BigCommerce ──────────────────────────────────
BIGCOMMERCE_CLIENT_ID=
BIGCOMMERCE_CLIENT_SECRET=
BIGCOMMERCE_REDIRECT_URI=http://localhost:8000/api/v1/auth/bigcommerce/callback

# ─── Platform: Amazon SP-API ────────────────────────────────
AMAZON_CLIENT_ID=
AMAZON_CLIENT_SECRET=
AMAZON_REDIRECT_URI=http://localhost:8000/api/v1/auth/amazon/callback
AMAZON_REFRESH_TOKEN=

# ─── Platform: Daraz ────────────────────────────────────────
DARAZ_APP_KEY=
DARAZ_APP_SECRET=
DARAZ_REDIRECT_URI=http://localhost:8000/api/v1/auth/daraz/callback

# ─── Image Generation ───────────────────────────────────────
# Gemini is free; DALL-E is paid
DALLE_API_KEY=
IMAGE_MODEL_DEFAULT=gemini-2.0-flash-exp

# ─── Social: TikTok ─────────────────────────────────────────
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=

# ─── Social: LinkedIn ───────────────────────────────────────
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=

# ─── Sync defaults ──────────────────────────────────────────
LOW_STOCK_THRESHOLD=10
ORDERS_SYNC_DAYS=90
```

---

## Frontend .env.local Template

**File:** `frontend/.env.local`

```bash
# Backend API URL (where FastAPI is running)
NEXT_PUBLIC_API_URL=http://localhost:8000

# Google OAuth Client ID (same as Backend GOOGLE_CLIENT_ID)
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
```

---

## Verification Checklist

After setting up your `.env`, verify each piece works:

### ✅ Backend Startup

```bash
cd Backend
python -c "from src.sdk.config import get_settings; s = get_settings(); print('SECRET_KEY length:', len(s.SECRET_KEY)); print('GEMINI_API_KEY set:', bool(s.GEMINI_API_KEY))"
```

**Expected:**
```
SECRET_KEY length: 43  (or 32+)
GEMINI_API_KEY set: True
```

### ✅ Database Connection

```bash
python -c "import asyncio; from src.sdk.database import init_db; asyncio.run(init_db()); print('DB OK')"
```

**Expected:** `DB OK` (no errors)

### ✅ Redis Connection

```bash
python src/sdk/test_redis.py
```

**Expected:** `Redis connection successful`

### ✅ Gemini API

```bash
python -c "
import asyncio
from src.sdk.llm.client import LLMClient
async def test():
    c = LLMClient(api_key='YOUR_KEY')
    print(await c.generate('Say hello'))
asyncio.run(test())
"
```

**Expected:** `Hello! How can I help you today?` (or similar)

### ✅ Backend Server

```bash
uvicorn src.main:app --reload
```

**Expected:** Server starts on http://localhost:8000

```bash
curl http://localhost:8000/health
```

**Expected:**
```json
{"status": "healthy", "service": "Digital FTE Agent", "version": "1.0.0"}
```

### ✅ Frontend Server

```bash
cd ../frontend
npm run dev
```

**Expected:** Compiles successfully, opens on http://localhost:3000

### ✅ End-to-End

1. Visit http://localhost:3000
2. Click "Sign Up" → Fill form → Submit
3. Should redirect to onboarding
4. Try connecting a Shopify test store (if Shopify credentials set)
5. Try "AI Post Generator" (if Gemini key set + at least 1 product)

---

## Common Issues & Fixes

### ❌ "SECRET_KEY must be 32+ characters in production"
**Fix:** Set `ENV=development` in .env, OR generate a longer SECRET_KEY (32+ chars).

### ❌ "could not connect to server: Connection refused" (PostgreSQL)
**Fix:** Start PostgreSQL: `docker-compose up -d postgres` OR check `DATABASE_URL` is correct.

### ❌ "Connection refused" (Redis)
**Fix:** Start Redis: `docker-compose up -d redis` OR check `REDIS_URL`.

### ❌ "GEMINI_API_KEY is empty — cannot call LLM"
**Fix:** Set `GEMINI_API_KEY=AIzaSy...` in .env. Get key from https://aistudio.google.com/app/apikey

### ❌ "CORS policy: No 'Access-Control-Allow-Origin' header"
**Fix:** Set `CORS_ORIGINS=http://localhost:3000` in Backend .env (not `*` for production).

### ❌ Shopify OAuth: "Invalid API key or access token"
**Fix:** Verify `SHOPIFY_API_KEY` and `SHOPIFY_API_SECRET` are correct, and the redirect URI matches exactly.

### ❌ Google Login button doesn't work
**Fix:** Verify `NEXT_PUBLIC_GOOGLE_CLIENT_ID` in frontend `.env.local` AND authorized origins in Google Cloud Console include `http://localhost:3000`.

---

## 🔒 Security Best Practices

1. **Never commit `.env` to git** — Already in `.gitignore` (added in Phase 4)
2. **Use different credentials for dev vs production** — Separate `.env.dev` and `.env.prod` files
3. **Rotate SECRET_KEY every 90 days** in production
4. **Enable 2FA on all third-party accounts** (Google Cloud, Shopify Partners, etc.)
5. **Use app-specific passwords** for Gmail SMTP, not your main password
6. **Set up billing alerts** on Google Cloud, OpenAI to avoid surprise charges
7. **Audit credentials quarterly** — remove unused ones
8. **Use environment-specific redirect URIs** — `localhost:8000` for dev, your domain for prod

---

## 📞 Support

If you're stuck on getting a credential:

- **Google Gemini:** https://ai.google.dev/gemini-api/docs/troubleshooting
- **Google Cloud:** https://cloud.google.com/support
- **Shopify:** https://help.shopify.com/en/partners
- **OpenAI:** https://help.openai.com/
- **Gmail App Passwords:** https://support.google.com/accounts/answer/185833

For Digital FTE-specific issues, check `FTE-Work-Flow.md` and `FTE-Structure.md`.

---

**End of Environment Setup Guide**
