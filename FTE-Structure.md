# Digital FTE — Complete Project Structure

> **Last updated:** 2026-08-25
> **Purpose:** Reference guide for every file in the project — what code lives where and what it does.

---

## 📂 Root Directory

```
E:\Internship\MERGE\
├── Backend/                  # Python FastAPI backend
├── frontend/                 # Next.js 15 frontend
├── FTE-Work-Flow.md          # Customer journey + agent workflows (this dir)
├── FTE-Structure.md          # This file — complete file inventory
├── env-update.md             # Step-by-step .env credential guide
├── docker-compose.yml        # (Optional) Docker orchestration
└── README.md                 # Project intro
```

---

## 🔧 Backend Structure

```
Backend/
├── requirements.txt          # Python dependencies (FastAPI, SQLAlchemy, Gemini SDK, etc.)
├── .env.example              # Template for environment variables
├── .env                      # ACTUAL secrets (gitignored)
├── .gitignore                # Python, venv, .env, logs, IDE files
├── pytest.ini                # pytest configuration (asyncio_mode=auto)
├── alembic.ini               # Alembic migration config
├── Dockerfile                # Container image definition
├── docker-compose.yml        # postgres + redis + backend services
│
├── alembic/                  # Database migration history
│   ├── env.py                # Alembic environment setup
│   ├── script.py.mako        # Migration template
│   └── versions/             # Generated migration files (currently empty)
│
├── server_test.log           # Stale log file (gitignored)
│
└── src/                      # Main source code
    ├── main.py               # FastAPI app entry point — registers all routers, lifespan
    ├── dependencies.py       # DI: DB session, Redis event bus, LLM client singletons
    │
    ├── domains/              # Feature-organized business logic
    │   ├── __init__.py
    │   │
    │   ├── auth/             # User authentication
    │   │   ├── __init__.py
    │   │   ├── models.py     # SQLAlchemy: User, LoginLog tables
    │   │   ├── schemas.py    # Pydantic: SignupRequest, LoginRequest, AuthResponse, etc.
    │   │   ├── service.py    # create_local_user(), authenticate_local_user(), get_current_user()
    │   │   ├── routes.py     # FastAPI router: /auth/signup, /auth/login, /auth/google, etc.
    │   │   └── google_oauth.py # verify_google_token() — Google id_token validation
    │   │
    │   ├── ecommerce/        # Multi-platform store management
    │   │   ├── __init__.py
    │   │   ├── routes.py     # REST: /api/v1/stores/* (CRUD, sync, products, orders, alerts)
    │   │   ├── webhooks.py   # Shopify webhook receiver: /webhooks/{shop}/{topic}
    │   │   ├── oauth.py      # Universal OAuth: /api/v1/auth/{platform}/start & /callback
    │   │   └── event_publisher.py # EventPublisher — publishes events to Redis
    │   │
    │   ├── security/         # Auth helpers, rate limiting, email
    │   │   ├── __init__.py
    │   │   ├── jwt.py        # hash_password, verify_password, create_access_token, decode_access_token
    │   │   ├── rate_limiter.py # In-memory sliding window rate limiter (5 attempts / 15 min)
    │   │   └── email_service.py # send_email() — SMTP with HTML body, graceful no-op if not configured
    │   │
    │   └── agents/           # The 7 AI agents + 2 read-only aggregation agents
    │       ├── __init__.py
    │       │
    │       ├── inventory_sync/      # Agent 1
    │       │   ├── __init__.py
    │       │   ├── worker.py        # Background task: listens to webhooks + sync events
    │       │   └── handler.py       # Event consumer: creates/updates products, orders, low stock alerts
    │       │
    │       ├── content_generation/  # Agent 2 (Gemini-powered)
    │       │   ├── __init__.py
    │       │   ├── worker.py        # Background task
    │       │   ├── handler.py       # _research_product, _write_caption, _review_caption (3 Gemini calls)
    │       │   ├── image_gen.py     # GeminiImageGenerator + DalleImageGenerator
    │       │   └── schemas.py       # Pydantic models for content requests/responses
    │       │
    │       ├── content_scheduling/  # Agent 3
    │       │   ├── __init__.py
    │       │   ├── worker.py        # Background task
    │       │   ├── handler.py       # Event consumer (content.approved → schedule post)
    │       │   ├── scheduler.py     # Polls DB for due posts, publishes them
    │       │   ├── meta_client.py   # Instagram + Facebook API
    │       │   ├── tiktok_client.py # TikTok API
    │       │   └── linkedin_client.py # LinkedIn API
    │       │
    │       ├── comment_engagement/  # Agent 4 (Gemini-powered)
    │       │   ├── __init__.py
    │       │   ├── worker.py        # Background poller (every 5 min)
    │       │   ├── handler.py       # _generate_llm_reply (Gemini with fallback)
    │       │   ├── meta_client.py   # Fetch comments from Meta API
    │       │   ├── rules.py         # Intent classification (ESCALATE / PRICE_QUERY / NEEDS_LLM)
    │       │   └── database.py      # Comment + Reply DB operations
    │       │
    │       ├── customer_support/    # Agent 5 (Gemini-powered)
    │       │   ├── __init__.py
    │       │   ├── worker.py        # Background task
    │       │   ├── handler.py       # Multi-intent chat: GREETING, ORDER_STATUS, PRODUCT_QUESTION
    │       │   ├── shopify_storefront_client.py # Cart operations via Shopify Storefront API
    │       │   └── rules.py         # Intent classification (English + Urdu)
    │       │
    │       ├── analytics_insights/  # Agent 6 (Gemini-powered)
    │       │   ├── __init__.py
    │       │   ├── worker.py        # Background task (hourly rollup)
    │       │   ├── handler.py       # run_rollup, dashboard, generate_summary (Gemini call)
    │       │   ├── metrics.py       # Metric definitions + rollup logic
    │       │   └── api.py           # REST: /api/v1/analytics/* (dashboard, summary, rollup, kpis, revenue)
    │       │
    │       ├── collaboration_orchestrator/ # Agent 7 (Gemini-powered)
    │       │   ├── __init__.py
    │       │   ├── worker.py        # Background task (heartbeat + workflow execution)
    │       │   ├── handler.py       # plan_workflow (Gemini), _run_step, agent registry
    │       │   ├── planner.py       # Workflow step definitions
    │       │   └── api.py           # REST: /api/v1/orchestrator/* (status, attention, workflows)
    │       │
    │       ├── seo_insights/        # NEW: Read-only SEO analysis
    │       │   ├── __init__.py      # (empty)
    │       │   ├── api.py           # GET /api/v1/seo/analysis — keyword extraction + suggestions
    │       │   └── worker.py        # No-op worker (on-demand only)
    │       │
    │       └── customers/           # NEW: Read-only customer aggregation
    │           ├── __init__.py      # (empty)
    │           ├── api.py           # GET /api/v1/customers — aggregate from Order table
    │           └── worker.py        # No-op worker (on-demand only)
    │
    └── sdk/                  # Shared SDK — reusable libraries
        ├── __init__.py
        │
        ├── config.py         # Pydantic Settings — ALL env vars + validation
        ├── database.py       # Async SQLAlchemy engine, session factory, get_db(), init_db()
        ├── auth.py           # verify_hmac() — Shopify webhook signature verification
        ├── crypto.py         # Fernet-based encrypt_token / decrypt_token (with SHA-256 key derivation)
        ├── event_bus.py      # AbstractEventBus, RedisEventBus (pub/sub implementation)
        ├── events.py         # Event type hierarchy: WebhookEvent, SyncRequestEvent, ContentRequestEvent, etc.
        ├── exceptions.py     # Custom exceptions: LLMError, AgentError, etc.
        ├── agent_base.py     # BaseAgent ABC — run(), heartbeat, subscriptions, shutdown
        ├── logging.py        # setup_logging() — centralized logging config
        ├── test_redis.py     # Standalone Redis connectivity test script
        │
        ├── llm/              # LLM integration (Gemini)
        │   ├── __init__.py
        │   ├── client.py     # LLMClient — generate(), generate_structured() (Gemini-based)
        │   ├── council.py    # CouncilBase ABC — multi-step LLM pipeline (research → write → review)
        │   └── prompts.py    # Centralized prompt templates for all agents
        │
        ├── models/           # SQLAlchemy ORM models
        │   ├── __init__.py
        │   ├── base.py       # Store, Product, Variant, Order, OrderItem, LowStockAlert
        │   ├── social.py     # SocialAccount, ScheduledPost, Comment, Reply
        │   ├── content.py    # BrandVoiceProfile, GeneratedPost, ImageAsset
        │   ├── analytics.py  # MetricDefinition, ReportSnapshot, KPI
        │   ├── support.py    # Conversation, Message, HandoffLog
        │   └── workflow.py   # Workflow, WorkflowLog, AgentTask
        │
        ├── oauth/            # OAuth helper utilities
        │   ├── __init__.py
        │   ├── base.py       # BaseOAuthProvider ABC — refresh, validate, revoke
        │   ├── providers.py  # Platform-specific OAuth URL builders
        │   └── tokens.py     # Token storage, encryption, refresh logic
        │
        ├── platforms/        # E-commerce platform connectors
        │   ├── __init__.py
        │   ├── base.py       # PlatformConnector ABC — verify_credentials, fetch_products, fetch_orders
        │   ├── shopify.py    # Full implementation: OAuth, products, orders, webhooks
        │   ├── woo_commerce.py # Full: REST API + basic auth
        │   ├── big_commerce.py # Full: X-Auth-Token
        │   ├── amazon.py     # Partial: orders only (products need ASIN list)
        │   ├── daraz.py      # Full: OAuth 2.0 with HMAC-SHA256
        │   └── templates/    # Templates for adding new platforms
        │       └── new_platform.md # Documentation
        │
        └── schemas/          # Common Pydantic schemas
            ├── __init__.py
            └── common.py     # Pagination, ErrorResponse, etc.

└── tests/                    # pytest test suite
    ├── __init__.py
    ├── conftest.py           # Fixtures: llm_client_with_key, llm_client_no_key
    ├── test_llm_client.py    # 7 tests: empty key, lazy init, generate, structured, retry, close
    └── test_seo_insights.py  # 5 tests: keyword extraction (basic, empty, none, case, length)
```

---

## 🎨 Frontend Structure

```
frontend/
├── package.json              # npm dependencies (Next.js 15, React 19, Tailwind 4, Framer Motion, etc.)
├── package-lock.json         # Locked dependency tree
├── tsconfig.json             # TypeScript config (strict mode, paths)
├── next.config.ts            # Next.js config (env vars, build settings)
├── tailwind.config.js        # Tailwind CSS v4 config
├── postcss.config.mjs        # PostCSS config for Tailwind
├── .gitignore                # Next.js standard gitignore
├── .env.example              # Template: NEXT_PUBLIC_API_URL, NEXT_PUBLIC_GOOGLE_CLIENT_ID
├── .env.local                # ACTUAL values (gitignored)
│
├── README.md                 # Frontend-specific docs (mentions mock data, backend not connected)
│
├── public/                   # Static assets
│   ├── favicon.ico
│   └── (other static files)
│
├── app/                      # Next.js 15 App Router
│   ├── layout.tsx            # Root layout — wraps in GoogleOAuthProvider, sets metadata
│   ├── page.tsx              # ⭐ MAIN FILE (2700 lines) — entire SPA
│   │                         #   Contains: LandingPage, AuthForm, OnboardingFlow, Dashboard + 6 tabs + 5 modals
│   │                         #   All in ONE big "AuthPage" component (intentional monolith)
│   │
│   ├── globals.css           # Tailwind CSS v4 + custom keyframes (float, pulse-shadow, fade-in)
│   │
│   └── components/           # Shared React components
│       └── InteractiveRobot.tsx # Animated SVG robot mascot (idle, surprised, private, wink, wave states)
│
└── lib/                      # Shared utilities
    └── api.ts                # ⭐ CENTRAL API CLIENT — all backend calls go through here
                              #   Exports: signup, login, getMe, listStores, generateAIPost,
                              #   listCustomers, getSEOAnalysis, getAnalytics, etc. (~25 functions)
                              #   Plus types: ApiUser, Store, Product, Order, Customer, etc. (~15 types)
                              #   Plus error class: ApiError
                              #   Plus session helpers: getToken, saveSession, clearSession
```

---

## 📋 Detailed File Responsibilities

### Backend — Core Files

#### `src/main.py`
**Purpose:** FastAPI application entry point
**Responsibilities:**
- Create `app = FastAPI(...)` with lifespan
- Add CORS middleware, security headers middleware
- Add SlowAPI rate limiter
- Register all routers: `auth_router`, `routes_router`, `webhooks_router`, `oauth_router`, + 8 agent routers
- Lifespan startup: `init_db()` → `init_event_bus()` → `_start_workers()` (9 background tasks)
- Lifespan shutdown: cancel workers → `close_event_bus()` → `close_llm_client()`
- `/health` endpoint

**Modified by:** Phase 1 (added close_llm_client), Phase 3 (registered SEO + customers routers)

---

#### `src/dependencies.py`
**Purpose:** Dependency injection hub — singletons for DB, Redis, LLM
**Responsibilities:**
- `get_event_bus()` → singleton RedisEventBus
- `init_event_bus()` / `close_event_bus()` — lifespan
- `get_llm_client()` → singleton LLMClient (Gemini)
- `close_llm_client()` — lifespan
- Re-exports `get_db` from `src/sdk/database.py`

**Modified by:** Phase 1 (added LLM client singleton)

---

#### `src/sdk/config.py`
**Purpose:** Centralized configuration using Pydantic Settings
**Responsibilities:**
- Loads ALL env vars (database, Redis, JWT, OAuth, LLM, email, platforms)
- Validates production safety (SECRET_KEY length, CORS not "*")
- `get_settings()` cached singleton

**Modified by:** Phase 1 (changed LLM_MODEL default to `gemini-2.0-flash-exp`)

---

#### `src/sdk/llm/client.py` ⭐ CRITICAL FILE
**Purpose:** LLM API wrapper (Google Gemini)
**Responsibilities:**
- `__init__(api_key, model, max_concurrent=3)` — store config, create semaphore
- `_get_model()` — lazy initialize `genai.GenerativeModel` on first call
- `generate(prompt, system, max_tokens)` — text generation with retry + rate limit
- `generate_structured(prompt, schema)` — JSON output via `response_schema`
- `close()` — cleanup
- `token_usage` dict — tracks input/output/calls

**Retry logic:** 3 attempts, delays 0.5s, 1.5s, 3.0s on `ConnectionError` / `TimeoutError` / `OSError`

**Replaced by:** Phase 1 (was `NotImplementedError` stubs, now full Gemini implementation)

---

#### `src/sdk/agent_base.py`
**Purpose:** Abstract base class for all 7 agents
**Responsibilities:**
- `BaseAgent` ABC with lifecycle: connect → register → heartbeat → subscribe → handle → shutdown
- `_heartbeat_loop()` — publishes HeartbeatEvent every 30s
- `setup_subscriptions()` — default: subscribes to `agent.{name}` channel
- `handle_event(event)` — abstract, must be overridden
- `shutdown()` — graceful: stop heartbeat, unregister, disconnect bus

---

### Backend — Auth Domain

#### `src/domains/auth/routes.py`
**Purpose:** User authentication REST endpoints
**Endpoints:**
- `POST /auth/signup` — new user registration
- `POST /auth/login` — email+password login
- `POST /auth/google` — Google OAuth login
- `GET /auth/me` — current user profile
- `POST /auth/send-verification` — send email verification link
- `GET /auth/verify-email?token=...` — verify email
- `POST /auth/forgot-password` — send password reset link
- `POST /auth/reset-password` — reset password with token

---

#### `src/domains/auth/service.py`
**Purpose:** Auth business logic
**Functions:**
- `create_local_user(db, payload)` — signup with conflict check
- `authenticate_local_user(db, email, password)` — login
- `get_or_create_google_user(db, google_id, email, full_name)` — Google OAuth
- `log_login(db, user_id, method, ip, ua)` — audit log
- `get_current_user(token, db)` — FastAPI dependency (Bearer token → User)

---

#### `src/domains/auth/models.py`
**Purpose:** SQLAlchemy models
**Tables:**
- `users` — id, username, email, full_name, hashed_password, auth_provider (LOCAL/GOOGLE), google_id, is_active, is_verified, created_at, updated_at
- `login_logs` — id, user_id (FK), login_method, ip_address, user_agent, logged_in_at

---

### Backend — Ecommerce Domain

#### `src/domains/ecommerce/routes.py`
**Purpose:** Multi-platform store REST API
**Endpoints (all under `/api/v1`):**
- `POST /stores/connect` — connect any platform store
- `GET /stores` — list user's stores
- `GET /stores/{id}` — get single store
- `GET /platforms` — list supported platforms
- `DELETE /stores/{id}` — disconnect (soft delete)
- `POST /stores/{id}/sync` — trigger full sync
- `POST /stores/{id}/sync/products` — products-only sync
- `POST /stores/{id}/sync/orders` — orders-only sync
- `GET /stores/{id}/stats` — store statistics
- `GET /stores/{id}/products?page=&limit=` — paginated products
- `GET /stores/{id}/products/{platform_product_id}` — single product
- `GET /stores/{id}/orders?page=&limit=` — paginated orders
- `GET /stores/{id}/alerts/low-stock` — low stock alerts
- `POST /stores/{id}/alerts/{alert_id}/resolve` — resolve alert

---

#### `src/domains/ecommerce/oauth.py`
**Purpose:** Universal OAuth router for all platforms
**Endpoints:**
- `GET /api/v1/auth/{platform}/start` — redirect to platform OAuth
- `GET /api/v1/auth/{platform}/callback` — OAuth callback
- `POST /api/v1/auth/{platform}/verify` — verify credentials without OAuth

**Modified by:** Phase 3 (improved 501 error message to guide users to API credentials path)

---

#### `src/domains/ecommerce/webhooks.py`
**Purpose:** Shopify webhook receiver
**Endpoint:** `POST /webhooks/{shop_name}/{topic}`
**Flow:**
1. Verify HMAC signature (`src/sdk/auth.py::verify_hmac()`)
2. Lookup Store by shop_name
3. Publish `WebhookEvent` to Redis `webhooks` channel
4. `inventory_sync` agent consumes

---

### Backend — SDK Libraries

#### `src/sdk/database.py`
**Purpose:** Async SQLAlchemy setup
**Responsibilities:**
- Create async engine from `DATABASE_URL`
- `async_session_factory` — session maker
- `get_db()` — FastAPI dependency
- `init_db()` — calls `Base.metadata.create_all()` (dev mode)
- `Base` — declarative base for all models

---

#### `src/sdk/event_bus.py`
**Purpose:** Redis pub/sub abstraction
**Classes:**
- `AbstractEventBus` — interface (publish, subscribe, connect, disconnect)
- `RedisEventBus` — implementation using `redis.asyncio`

**Channels used:**
- `webhooks`, `sync`, `events`, `agent.{name}`, `orchestrator.registry`, `orchestrator.heartbeat`

---

#### `src/sdk/crypto.py`
**Purpose:** Token encryption at rest
**Functions:**
- `encrypt_token(plaintext: str) -> str` — Fernet encryption
- `decrypt_token(ciphertext: str) -> str` — Fernet decryption
- `_derive_key(passphrase: str)` — SHA-256 hash for any-length key

**Key source:** `ENCRYPTION_KEY` env var

---

#### `src/sdk/platforms/shopify.py`
**Purpose:** Shopify platform connector
**Implements:** `PlatformConnector` ABC
**Methods:**
- `verify_credentials(shop_name, access_token)` — test API call
- `fetch_products(store, since=None)` — list products
- `fetch_orders(store, since=None)` — list orders
- `fetch_inventory(store)` — current stock levels
- `register_webhook(store, topic, url)` — create webhook
- `unregister_webhook(store, webhook_id)` — remove webhook
- Uses `ShopifyAPI` Python SDK

---

### Backend — AI Agents (7 + 2 = 9)

#### Agent 1: `inventory_sync`
**Files:** `worker.py`, `handler.py`
**Subscribes to:** `webhooks`, `sync` channels
**Does:** Sync products/orders from any platform → DB
**LLM:** ❌ None (pure data sync)

---

#### Agent 2: `content_generation` ⭐
**Files:** `worker.py`, `handler.py`, `image_gen.py`, `schemas.py`
**Subscribes to:** `content.generation`, `content.generate.requested` channels
**Does:** 3-step Gemini pipeline (research → write → review) + image gen
**LLM:** ✅ 3 Gemini calls per post

---

#### Agent 3: `content_scheduling`
**Files:** `worker.py`, `handler.py`, `scheduler.py`, `meta_client.py`, `tiktok_client.py`, `linkedin_client.py`
**Subscribes to:** `events` (for `content.approved`)
**Does:** Schedule posts, publish at due time
**LLM:** ❌ None

---

#### Agent 4: `comment_engagement` ⭐
**Files:** `worker.py`, `handler.py`, `meta_client.py`, `rules.py`, `database.py`
**Subscribes to:** `events`
**Does:** Auto-reply to social comments
**LLM:** ✅ 1 Gemini call per comment (with deterministic fallback)

---

#### Agent 5: `customer_support` ⭐
**Files:** `worker.py`, `handler.py`, `shopify_storefront_client.py`, `rules.py`
**Subscribes to:** `events`, `agent.customer_support`
**Does:** Multi-intent chat support
**LLM:** ✅ 1 Gemini call per product question (with DB catalog fallback)

---

#### Agent 6: `analytics_insights` ⭐
**Files:** `worker.py`, `handler.py`, `metrics.py`, `api.py`
**Subscribes to:** `events`, `agent.analytics_insights`
**Does:** Hourly rollup, KPI tracking, executive summary
**LLM:** ✅ 1 Gemini call per summary request
**API:** `/api/v1/analytics/{rollup, dashboard, summary, metrics, snapshots, kpis, revenue}`

**Modified by:** Phase 3 (added `/revenue` endpoint)

---

#### Agent 7: `collaboration_orchestrator` ⭐
**Files:** `worker.py`, `handler.py`, `planner.py`, `api.py`
**Subscribes to:** `events`, `orchestrator.registry`, `orchestrator.heartbeat`
**Does:** Multi-agent workflow planning + execution
**LLM:** ✅ 1 Gemini call per workflow (with rule-based fallback)
**API:** `/api/v1/orchestrator/*`

---

#### NEW: `seo_insights` (Phase 3)
**Files:** `api.py`, `worker.py`
**Does:** On-demand SEO analysis (keyword extraction from product titles)
**LLM:** ❌ None (pure regex-based)
**API:** `GET /api/v1/seo/analysis?store_id=X`

---

#### NEW: `customers` (Phase 3)
**Files:** `api.py`, `worker.py`
**Does:** On-demand customer aggregation from `Order` table
**LLM:** ❌ None (SQL aggregation)
**API:** `GET /api/v1/customers?store_id=X`

---

### Frontend — Core Files

#### `app/page.tsx` ⭐
**Purpose:** The entire single-page app (2700 lines)
**Contains:**
- `LandingPage` JSX (~200 lines)
- `AuthForm` JSX (~250 lines)
- `OnboardingFlow` JSX (~600 lines, 8 steps)
- `Dashboard` JSX with 6 tabs (~700 lines)
- 5 modals: AIPostModal, SchedulePostModal, CommentsModal, SEOModal, SettingsModal
- `DEMO_PRODUCTS` array (REMOVED in Phase 2)
- State management: 20+ `useState` hooks
- Mock data blocks (REPLACED with real API calls in Phase 2)

**Key state variables (after Phase 2):**
- `sessionUser`, `activeStore`, `storeStats`, `realProducts`, `lowStockAlerts`
- **NEW:** `customers`, `comments`, `seoData`, `analytics`, `analyticsSummary`, `revenueByDay`, `generatingPost`

**Key functions (after Phase 2):**
- `handleAuthSubmit()` — signup/login → backend
- `handleGoogleCredential()` — Google OAuth
- `loadDashboardData()` — **9 parallel API calls** (was 3)
- `generatePost()` — **real `generateAIPost()` API call** (was synchronous mock)
- `handleLogout()` — clear session + all state

---

#### `lib/api.ts` ⭐
**Purpose:** Central API client — all backend calls go through here
**Size:** ~400 lines (after Phase 2 additions)
**Exports:**

**Auth (5):**
- `signup(payload)` → POST /auth/signup
- `login(payload)` → POST /auth/login
- `googleLogin(idToken)` → POST /auth/google
- `getMe()` → GET /auth/me
- `forgotPassword(email)` → POST /auth/forgot-password
- **NEW:** `resetPassword(token, newPassword)` → POST /auth/reset-password
- **NEW:** `updateUser(payload)` → PATCH /auth/me
- **NEW:** `deleteAccount()` → DELETE /auth/me
- **NEW:** `refreshToken()` → POST /auth/refresh

**Stores (6):**
- `listStores()` → GET /api/v1/stores
- `connectStore(payload)` → POST /api/v1/stores/connect
- `triggerSync(storeId)` → POST /api/v1/stores/{id}/sync
- `getStoreStats(storeId)` → GET /api/v1/stores/{id}/stats
- `listProducts(storeId, page, limit)` → GET /api/v1/stores/{id}/products
- `listOrders(storeId, page, limit)` → GET /api/v1/stores/{id}/orders
- `getLowStockAlerts(storeId)` → GET /api/v1/stores/{id}/alerts/low-stock
- **NEW:** `disconnectStore(storeId)` → DELETE /api/v1/stores/{id}

**Social (3 NEW):**
- `listSocialAccounts(storeId)` → GET /api/v1/scheduling/accounts
- `connectSocialAccount(payload)` → POST /api/v1/scheduling/accounts
- `disconnectSocialAccount(accountId)` → DELETE /api/v1/scheduling/accounts/{id}

**Content (1 NEW):**
- `generateAIPost(payload)` → POST /api/v1/content/generate

**Scheduling (2 NEW):**
- `schedulePost(payload)` → POST /api/v1/scheduling/posts
- `listScheduledPosts(storeId)` → GET /api/v1/scheduling/posts

**Comments (2 NEW):**
- `listComments(socialAccountId?)` → GET /api/v1/comments
- `replyToComment(commentId, text)` → POST /api/v1/comments/{id}/reply

**SEO (1 NEW):**
- `getSEOAnalysis(storeId)` → GET /api/v1/seo/analysis

**Analytics (3 NEW):**
- `getAnalytics(storeId, periodDays)` → GET /api/v1/analytics/dashboard
- `getAnalyticsSummary(storeId, periodDays)` → GET /api/v1/analytics/summary
- `getRevenueByDay(storeId, days)` → GET /api/v1/analytics/revenue

**Customers (1 NEW):**
- `listCustomers(storeId)` → GET /api/v1/customers

**Types (15+):**
- `ApiUser`, `AuthResponse`, `Store`, `StoreStats`, `Product`, `Variant`, `ProductListResponse`, `Order`, `OrderListResponse`, `LowStockAlert`, `AlertListResponse`
- **NEW:** `SocialAccount`, `AIPostResponse`, `ScheduledPost`, `Comment`, `SEOSummary`, `AnalyticsDashboard`, `Customer`, `RevenuePoint`

**Error class:** `ApiError extends Error` — carries HTTP status

**Session helpers:**
- `getToken()` — read from localStorage
- `getStoredUser()` — read user from localStorage
- `saveSession(token, user)` — write to localStorage
- `clearSession()` — remove from localStorage

**Core helper:** `request<T>(path, options, auth)` — fetch wrapper with JWT injection + 401 auto-clear

---

#### `app/components/InteractiveRobot.tsx`
**Purpose:** Animated SVG robot mascot
**States:** idle, surprised (email focus), private (password visible), wink (password focus), wave
**Features:**
- Mouse-tracking pupils
- Blink animation every 3.8s
- Speech bubble on form field focus
- Used in landing, auth, onboarding screens

---

#### `app/layout.tsx`
**Purpose:** Root layout
**Responsibilities:**
- Wraps in `<GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>`
- Sets viewport, metadata (title, description, favicon)
- Theme initialization script (light/dark mode from localStorage)

---

#### `app/globals.css`
**Purpose:** Global styles
**Imports:** Google Fonts (Plus Jakarta Sans, Inter, JetBrains Mono), Tailwind CSS v4
**Custom keyframes:** `float`, `float-delayed`, `pulse-shadow`, `bounce-short`, `fade-in`, `bounce-right`, `pulse-slow`

---

## 🧪 Test Files

#### `tests/conftest.py`
**Pytest fixtures:**
- `llm_client_with_key` — LLMClient with fake API key (no real calls)
- `llm_client_no_key` — LLMClient with empty API key (raises LLMError)

---

#### `tests/test_llm_client.py` (7 tests)
1. `test_generate_raises_when_no_api_key` — empty key → LLMError(503)
2. `test_model_not_initialized_in_constructor` — lazy init verified
3. `test_generate_calls_gemini_and_returns_text` — happy path with mock
4. `test_generate_with_system_prompt` — system prompt prepended
5. `test_generate_structured_parses_json` — JSON response parsed
6. `test_generate_retries_on_connection_error` — retry logic works
7. `test_close_clears_model_instance` — close() is safe

---

#### `tests/test_seo_insights.py` (5 tests)
1. `test_extract_keywords_basic` — tokenization + counting
2. `test_extract_keywords_empty_input` — empty list → empty dict
3. `test_extract_keywords_handles_none` — None entries skipped
4. `test_extract_keywords_counts_case_insensitive` — case-insensitive counting
5. `test_extract_keywords_skips_short_words` — min_length filter

**Total: 12 passing tests**

---

## 📊 File Count Summary

| Category | Count |
|---|---|
| Backend Python files | ~70 |
| Backend test files | 4 |
| Frontend TS/TSX files | 4 |
| Config files (yaml, json, ini, toml) | ~10 |
| Documentation (.md) | 4 (this + Work-Flow + env-update + README) |
| **Total source files** | **~95** |

---

## 🔄 Files Modified Across All Phases

### Phase 1 (LLM Client — Gemini)
- ✏️ `Backend/requirements.txt` — added `google-generativeai`, `pytest`, `pytest-asyncio`
- ✏️ `Backend/src/sdk/config.py` — `LLM_MODEL` default → `gemini-2.0-flash-exp`
- ✏️ `Backend/src/sdk/llm/client.py` — full Gemini implementation
- ✏️ `Backend/src/dependencies.py` — `get_llm_client()` / `close_llm_client()` singleton
- ✏️ `Backend/src/main.py` — lifespan wiring

### Phase 2 (Frontend Mock → Real)
- ✏️ `frontend/lib/api.ts` — 8 new types + 15 new functions
- ✏️ `frontend/app/page.tsx` — `DEMO_PRODUCTS` removed, `generatePost` real, `loadDashboardData` extended, logout extended

### Phase 3 (New Backend Endpoints)
- ➕ `Backend/src/domains/agents/seo_insights/__init__.py`
- ➕ `Backend/src/domains/agents/seo_insights/api.py`
- ➕ `Backend/src/domains/agents/seo_insights/worker.py`
- ➕ `Backend/src/domains/agents/customers/__init__.py`
- ➕ `Backend/src/domains/agents/customers/api.py`
- ➕ `Backend/src/domains/agents/customers/worker.py`
- ✏️ `Backend/src/domains/agents/analytics_insights/api.py` — added `/revenue` endpoint
- ✏️ `Backend/src/domains/ecommerce/oauth.py` — improved 501 message
- ✏️ `Backend/src/main.py` — registered 2 new routers

### Phase 4 (Cleanup)
- ➕ `Backend/.gitignore`

### Phase 5 (Tests)
- ➕ `Backend/pytest.ini`
- ➕ `Backend/tests/__init__.py`
- ➕ `Backend/tests/conftest.py`
- ➕ `Backend/tests/test_llm_client.py`
- ➕ `Backend/tests/test_seo_insights.py`

**Total: 5 modified (Phase 1) + 2 modified + 6 new files (Phase 2-3) + 1 new (Phase 4) + 5 new (Phase 5) = 19 files**

---

## 🎯 Quick Navigation

**Need to...** → **Go to file...**

| Task | File |
|---|---|
| Change LLM model | `Backend/src/sdk/config.py` |
| Add new API endpoint | `Backend/src/domains/{domain}/{file}.py` |
| Add new frontend page | `frontend/app/{route}/page.tsx` |
| Add new API client function | `frontend/lib/api.ts` |
| Add new AI agent | `Backend/src/domains/agents/{name}/` |
| Add new DB model | `Backend/src/sdk/models/{file}.py` |
| Add new platform (e.g., Etsy) | `Backend/src/sdk/platforms/{name}.py` |
| Add new event type | `Backend/src/sdk/events.py` |
| Change UI styling | `frontend/app/globals.css` + Tailwind classes |
| Add new env var | `Backend/src/sdk/config.py` + `.env` + `.env.example` |
| Add new test | `Backend/tests/test_{module}.py` |
| Debug LLM call | `Backend/src/sdk/llm/client.py` + check `token_usage` |
| See customer flow | `FTE-Work-Flow.md` |
| Setup credentials | `env-update.md` |

---

**End of Structure Documentation**
