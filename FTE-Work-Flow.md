# Digital FTE — Complete Workflow Documentation

> **Last updated:** 2026-08-25
> **Project:** AI-powered E-commerce Autonomous Employee platform
> **Stack:** Next.js 15 (frontend) + FastAPI (backend) + PostgreSQL + Redis + Google Gemini

---

## 📖 Table of Contents

1. [What is Digital FTE?](#what-is-digital-fte)
2. [High-Level Architecture](#high-level-architecture)
3. [Customer Journey — End to End](#customer-journey)
4. [7 AI Agents — How They Work](#ai-agents)
5. [Event-Driven Communication (Redis)](#event-driven)
6. [Data Flow Diagrams](#data-flow)
7. [Security & Authentication Flow](#security)
8. [External Integrations](#integrations)
9. [Cost & Performance](#cost)

---

## What is Digital FTE?

**Digital FTE** (Full-Time Equivalent) is an AI "employee" that autonomously manages an e-commerce store owner's operations. It replaces 5-6 human employees:

- 📦 **Inventory Manager** — syncs products/orders across platforms
- 📱 **Social Media Manager** — creates & schedules posts
- 💬 **Community Manager** — replies to comments
- 🎧 **Customer Support Agent** — handles questions
- 📊 **Data Analyst** — provides insights & reports

The owner signs up, connects their store, and the AI runs 24/7 in the background.

---

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    CUSTOMER (Browser)                        │
│                  http://localhost:3000                        │
└──────────────────────┬───────────────────────────────────────┘
                       │ HTTPS (JWT in localStorage)
                       ▼
┌──────────────────────────────────────────────────────────────┐
│              NEXT.JS FRONTEND (React 19 + TS)                │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐ │
│  │ LandingPage │  │  AuthForm   │  │  OnboardingFlow      │ │
│  └─────────────┘  └─────────────┘  └──────────────────────┘ │
│  ┌──────────────────────────────────────────────────────────┐│
│  │              Dashboard + 6 Tabs + 5 Modals              ││
│  └──────────────────────────────────────────────────────────┘│
└──────────────────────┬───────────────────────────────────────┘
                       │ REST API calls (fetch)
                       ▼
┌──────────────────────────────────────────────────────────────┐
│             FASTAPI BACKEND (Python 3.11+)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │ Auth Router  │  │  Ecommerce   │  │  8 Agent Routers   │ │
│  │ /auth/*      │  │  /api/v1/*   │  │  (content, etc.)   │ │
│  └──────────────┘  └──────────────┘  └────────────────────┘ │
│  ┌──────────────────────────────────────────────────────────┐│
│  │          Dependency Injection (DB, Redis, LLM)           ││
│  └──────────────────────────────────────────────────────────┘│
│  ┌──────────────────────────────────────────────────────────┐│
│  │       7 Background AI Agents (asyncio tasks)             ││
│  └──────────────────────────────────────────────────────────┘│
└──────┬──────────────────┬─────────────────────┬──────────────┘
       │                  │                     │
       ▼                  ▼                     ▼
┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐
│ PostgreSQL   │  │ Redis        │  │  Google Gemini API     │
│ (asyncpg)    │  │ (Event Bus)  │  │  (LLMClient wrapper)   │
│              │  │              │  │                        │
│ • users      │  │ Channels:    │  │  • generate()          │
│ • stores     │  │ • webhooks   │  │  • generate_structured │
│ • products   │  │ • sync       │  │  • Retry + Rate Limit  │
│ • orders     │  │ • events     │  │                        │
│ • + 20 more  │  │ • agent.*    │  │                        │
└──────────────┘  └──────────────┘  └────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────────┐
        │     EXTERNAL PLATFORMS               │
        │  • Shopify, WooCommerce, BigCommerce│
        │  • Amazon SP-API, Daraz              │
        │  • Instagram, Facebook, TikTok       │
        │  • LinkedIn, YouTube, Twitter        │
        └──────────────────────────────────────┘
```

---

## Customer Journey

### Stage 1: Discovery (Landing Page)

**What customer sees:**
- Hero: "Your AI Employee for E-commerce"
- 4 feature cards (24/7 automation, multi-platform, etc.)
- ROI calculator slider ("Save $3000/month")
- "Get Started Free" button

**Files involved:**
- `frontend/app/page.tsx` → `LandingPage` JSX (lines ~1924-2131)
- `frontend/app/components/InteractiveRobot.tsx` → animated mascot

**No backend call** — pure marketing page.

---

### Stage 2: Signup (Account Creation)

**What customer does:**
1. Clicks "Sign Up"
2. Fills: full_name, username, email, password
3. Password rules enforced client-side: 8+ chars, 1 number, 1 uppercase

**API call:**
```http
POST /auth/signup
Content-Type: application/json

{
  "username": "ahmed_khan",
  "email": "ahmed@shop.com",
  "password": "Secure123Pass",
  "full_name": "Ahmed Khan"
}
```

**Backend processing:**
```
src/domains/auth/routes.py::signup()
   ↓
src/domains/auth/service.py::create_local_user()
   ├─ Check username/email not already taken
   ├─ hash_password() using bcrypt
   ├─ INSERT INTO users (..., hashed_password, auth_provider='LOCAL')
   └─ create_access_token() → JWT with user_id
   ↓
Return: {
  "message": "User created",
  "access_token": "eyJhbGciOiJIUzI1...",
  "token_type": "bearer",
  "user": {id, username, email, full_name, ...}
}
```

**Frontend saves:**
```typescript
saveSession(access_token, user);
// → localStorage.setItem("fte_token", token)
// → localStorage.setItem("fte_user", JSON.stringify(user))
```

**Files involved:**
- `frontend/app/page.tsx` → `handleAuthSubmit()` (line ~363)
- `frontend/lib/api.ts` → `signup()` function
- `Backend/src/domains/auth/routes.py` → `/auth/signup` endpoint
- `Backend/src/domains/auth/service.py` → `create_local_user()`
- `Backend/src/domains/auth/models.py` → User SQLAlchemy model
- `Backend/src/domains/security/jwt.py` → JWT token creation

---

### Stage 3: Onboarding (8-Step Setup Wizard)

**Step-by-step:**

| Step | UI | Backend Action |
|---|---|---|
| 1 | Welcome screen with robot | None |
| 2 | "Enter your store URL" OR "Connect Shopify" | Validation only OR OAuth flow |
| 3 | "Store connected!" success | Store row created in DB |
| 4 | "Connect Instagram" | Social OAuth |
| 5 | "Connect Facebook" | Social OAuth |
| 6 | "Connect TikTok" | Social OAuth |
| 7 | "Connect YouTube" | Social OAuth |
| 8 | "Launchpad" → 2.5s loading → Dashboard | Set user as onboarded |

**Step 2: Shopify OAuth (real flow):**

```
Customer clicks "Connect Shopify"
   ↓
Frontend: window.location.href = '/api/v1/auth/shopify/start?shop=ahmed-store.myshopify.com'
   ↓
Backend: src/domains/ecommerce/oauth.py::shopify_start()
   ├─ Generate state token (CSRF protection)
   ├─ Build Shopify OAuth URL with scopes
   └─ Redirect to: https://ahmed-store.myshopify.com/admin/oauth/authorize?...
   ↓
Customer logs into Shopify, approves permissions
   ↓
Shopify redirects to: /api/v1/auth/shopify/callback?code=xxx&shop=yyy
   ↓
Backend: src/domains/ecommerce/oauth.py::shopify_callback()
   ├─ Verify HMAC signature (src/sdk/auth.py::verify_hmac())
   ├─ Exchange code for permanent access_token via Shopify API
   ├─ Encrypt token (src/sdk/crypto.py::encrypt_token())
   ├─ INSERT INTO stores (platform='shopify', access_token=encrypted, ...)
   └─ Redirect to: {FRONTEND_SUCCESS_URL}/dashboard
   ↓
Dashboard loads with store available
```

**Files involved:**
- `frontend/app/page.tsx` → `OnboardingFlow` component (lines ~1297-1922)
- `Backend/src/domains/ecommerce/oauth.py` → Universal OAuth router
- `Backend/src/domains/ecommerce/routes.py` → Store CRUD
- `Backend/src/sdk/platforms/shopify.py` → Shopify API client
- `Backend/src/sdk/crypto.py` → Fernet encryption
- `Backend/src/sdk/auth.py` → HMAC verification

---

### Stage 4: Dashboard (Customer's Daily Workspace)

**Initial load — 9 parallel API calls:**

```typescript
// frontend/app/page.tsx::loadDashboardData()
const [
  stats,        products,   alerts,
  customers,    comments,   seo,
  analytics,    summary,    revenue
] = await Promise.all([
  getStoreStats(storeId),         // GET /api/v1/stores/{id}/stats
  listProducts(storeId, 1, 50),   // GET /api/v1/stores/{id}/products
  getLowStockAlerts(storeId),     // GET /api/v1/stores/{id}/alerts/low-stock
  listCustomers(storeId),         // GET /api/v1/customers?store_id=...
  listComments(),                 // GET /api/v1/comments
  getSEOAnalysis(storeId),        // GET /api/v1/seo/analysis
  getAnalytics(storeId, 30),      // GET /api/v1/analytics/dashboard
  getAnalyticsSummary(storeId),   // GET /api/v1/analytics/summary
  getRevenueByDay(storeId, 7),    // GET /api/v1/analytics/revenue
]);
```

**Dashboard tabs:**

#### Tab 1: Dashboard (Overview)
- Revenue chart (last 7 days) — bars from `revenue` data
- KPI cards (total products, orders, low stock)
- Recent activity feed (synthesized from comments + posts + alerts)
- AI-generated summary text from Gemini

#### Tab 2: Inventory
- Product list table (paginated)
- Search/filter
- Low stock alert badges
- "Sync Now" button → `POST /api/v1/stores/{id}/sync`

#### Tab 3: Social Media
- Connected accounts grid (Instagram, Facebook, TikTok, etc.)
- Per-account post count
- "Connect" / "Disconnect" buttons

#### Tab 4: Customers (NEW)
- Table of aggregated customers from `Order` table
- Columns: name, email, orders count, total spent, last order
- Sorted by total_spent DESC
- Source: `Backend/src/domains/agents/customers/api.py::list_customers()`

#### Tab 5: Payments
- Recent orders list
- Order details modal

#### Tab 6: Analytics
- Full charts (revenue, orders, conversion)
- Per-platform breakdown
- Date range filter
- Download as CSV (future)

#### Tab 7: Settings
- User profile (name, email)
- Connected accounts management
- API keys (if any)
- Logout button

**Files involved:**
- `frontend/app/page.tsx` → Main `AuthPage` component + all tab render logic
- `frontend/lib/api.ts` → All 9 API client functions
- `Backend/src/domains/ecommerce/routes.py` → Store/product/order endpoints
- `Backend/src/domains/agents/seo_insights/api.py` → SEO endpoint
- `Backend/src/domains/agents/customers/api.py` → Customer endpoint
- `Backend/src/domains/agents/analytics_insights/api.py` → Analytics + revenue

---

### Stage 5: AI Content Generation (Gemini-Powered)

**Customer flow:**
1. Click "AI Post Generator" button
2. Modal opens
3. Select product from dropdown (real products from `realProducts` state)
4. Select platform (Instagram, Facebook, TikTok, LinkedIn)
5. Click "Generate"

**Frontend:**
```typescript
// generatePost() in page.tsx
const result = await generateAIPost({
  product_id: selectedProduct,
  platform: "instagram",
  auto_approve: false,
});
setGeneratedPost({ image: result.image_url, caption: result.caption });
```

**Backend pipeline (3 Gemini calls):**

```
POST /api/v1/content/generate
   ↓
src/domains/agents/content_generation/handler.py::handle_generate()
   ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 1: RESEARCH (Gemini Call #1)                           │
│ _research_product(product)                                  │
│   prompt: "Analyze {product.title}. Extract 3 key selling   │
│            points and target audience."                     │
│   system: "You are a product researcher."                   │
│   LLMClient.generate() → Gemini → returns research text    │
└─────────────────────────────────────────────────────────────┘
   ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 2: WRITE CAPTION (Gemini Call #2)                      │
│ _write_caption(product, research)                           │
│   prompt: "Write an Instagram caption for {product} using  │
│            these selling points: {research}"                │
│   system: "You are a social media copywriter."              │
│   LLMClient.generate() → Gemini → returns caption text     │
└─────────────────────────────────────────────────────────────┘
   ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 3: REVIEW (Gemini Call #3)                             │
│ _review_caption(product, caption)                           │
│   prompt: "Review this caption: {caption}. Does it match   │
│            the brand voice? Suggest improvements."          │
│   system: "You are a brand tone reviewer."                  │
│   LLMClient.generate() → Gemini → returns final caption    │
└─────────────────────────────────────────────────────────────┘
   ↓ (parallel)
┌─────────────────────────────────────────────────────────────┐
│ IMAGE GENERATION                                            │
│ src/domains/agents/content_generation/image_gen.py          │
│   • GeminiImageGenerator OR DalleImageGenerator             │
│   • If no API key: return MOCK_IMAGE_URL                    │
│   • Save to /tmp or upload to CDN (future)                  │
└─────────────────────────────────────────────────────────────┘
   ↓
INSERT INTO generated_posts (...)
   ↓
Publish event: "content.approved" to Redis "events" channel
   ↓
Return: {post_id, caption, image_url, product_title, platform}
```

**Files involved:**
- `frontend/app/page.tsx` → `generatePost()` (line ~320, now real)
- `frontend/lib/api.ts` → `generateAIPost()`
- `Backend/src/domains/agents/content_generation/api.py` → `/api/v1/content/generate`
- `Backend/src/domains/agents/content_generation/handler.py` → 3 Gemini calls
- `Backend/src/sdk/llm/client.py` → LLMClient wrapper (Gemini)
- `Backend/src/sdk/llm/prompts.py` → Prompt templates

---

### Stage 6: Post Scheduling & Publishing

**Customer flow:**
1. After generating post, click "Schedule"
2. Pick date/time
3. Confirm

**Backend:**
```
POST /api/v1/scheduling/posts
{
  "social_account_id": 5,
  "caption": "...",
  "media_urls": ["https://cdn.example.com/img.jpg"],
  "platform": "instagram",
  "scheduled_at": "2026-08-26T18:00:00Z"
}
   ↓
INSERT INTO scheduled_posts (status='scheduled', ...)
   ↓
content_scheduling worker picks it up
   ↓
At scheduled_at:
   ├─ Call Meta Graph API → publish post
   ├─ INSERT INTO posts (platform_post_id, ...)
   ├─ UPDATE scheduled_posts SET status='published'
   └─ Publish event "post.published" to Redis
   ↓
analytics_insights agent receives event → updates metrics
```

**Files involved:**
- `frontend/app/page.tsx` → Schedule Post modal
- `Backend/src/domains/agents/content_scheduling/worker.py` → Background scheduler
- `Backend/src/domains/agents/content_scheduling/handler.py` → Event consumer
- `Backend/src/domains/agents/content_scheduling/meta_client.py` → Instagram/Facebook API
- `Backend/src/domains/agents/content_scheduling/tiktok_client.py` → TikTok API
- `Backend/src/domains/agents/content_scheduling/linkedin_client.py` → LinkedIn API

---

## 7 AI Agents

### Agent 1: Inventory Sync

**Purpose:** Keep products/orders in sync across all connected platforms.

**Subscribed events:**
- `webhooks` channel (Shopify, WooCommerce webhooks)
- `sync` channel (manual sync requests)

**Triggered by:**
- Shopify webhook when order created/updated
- Customer clicks "Sync Now" button
- Scheduled job (every 6 hours)

**Logic:**
```
On webhook received:
   ↓
verify_hmac(headers, body)  # Shopify authenticity
   ↓
INSERT INTO orders (customer_email, total_price, ...)
   ↓
For each order item:
   ├─ Find variant by platform_variant_id
   ├─ UPDATE variants SET inventory_quantity = inventory_quantity - qty
   └─ If inventory < threshold: INSERT INTO low_stock_alerts
   ↓
Publish event: "inventory.updated" to Redis
```

**Files:** `Backend/src/domains/agents/inventory_sync/{worker.py, handler.py}`

---

### Agent 2: Content Generation

**Purpose:** AI-powered social media post creation using Gemini.

**Subscribed events:**
- `content.generation` channel
- `content.generate.requested` channel

**Key methods:**
- `_research_product()` — Gemini call #1
- `_write_caption()` — Gemini call #2
- `_review_caption()` — Gemini call #3
- `_generate_image()` — Gemini/DALL-E

**Files:** `Backend/src/domains/agents/content_generation/{worker.py, handler.py, image_gen.py, schemas.py}`

---

### Agent 3: Content Scheduling

**Purpose:** Publish scheduled posts at the right time on the right platform.

**Subscribed events:**
- `events` channel (listens for `content.approved`)

**Background loop:**
```
Every 60 seconds:
   SELECT * FROM scheduled_posts
   WHERE status='scheduled' AND scheduled_at <= NOW()
   ↓
For each due post:
   ├─ Get social_account from DB (decrypt token)
   ├─ Call platform API (Meta/TikTok/LinkedIn)
   ├─ UPDATE status='published' OR 'failed'
   └─ Publish event: "post.published" or "post.publish.failed"
```

**Files:** `Backend/src/domains/agents/content_scheduling/{worker.py, handler.py, scheduler.py, meta_client.py, tiktok_client.py, linkedin_client.py}`

---

### Agent 4: Comment Engagement

**Purpose:** Auto-reply to comments on social media posts.

**Subscribed events:**
- `events` channel

**Background loop:**
```
Every 5 minutes (per connected account):
   Fetch recent comments from Meta Graph API
   ↓
For each comment:
   ├─ Classify intent (rules-based):
   │   ├─ ESCALATE: contains "refund", "complaint", "angry"
   │   ├─ PRICE_QUERY: contains "price", "cost", "how much"
   │   └─ NEEDS_LLM: general questions
   ├─ If ESCALATE: notify human (future: email/Slack)
   ├─ If PRICE_QUERY: reply with product price from DB
   └─ If NEEDS_LLM: Gemini call → friendly reply
   ↓
INSERT INTO replies (status='posted', platform_reply_id, ...)
```

**Gemini call (with fallback):**
```python
try:
    reply = await self.llm.generate(
        prompt=f"Reply to: {comment.text}",
        system="You are a friendly brand social media assistant."
    )
except LLMError:
    # Deterministic fallback if API key missing
    reply = "Thanks so much for your comment! 🙌"
```

**Files:** `Backend/src/domains/agents/comment_engagement/{worker.py, handler.py, meta_client.py, rules.py, database.py}`

---

### Agent 5: Customer Support

**Purpose:** Answer customer questions via chat widget.

**Subscribed events:**
- `events` channel
- `agent.customer_support` channel

**Intent classification (rules + keywords):**
- `GREETING` — "hi", "hello"
- `ORDER_STATUS` — "where is my order"
- `PRODUCT_QUESTION` — "does X come in red?"
- `CART_ADD` / `CART_REMOVE` / `CART_UPDATE`
- `OUT_OF_SCOPE` — anything else

**Multi-language support:** English + Urdu/Roman Urdu

**Gemini call (with fallback):**
```python
if intent == "PRODUCT_QUESTION":
    try:
        answer = await self.llm.generate(
            prompt=f"Product: {product.title}\nQuestion: {question}",
            system="You are a helpful customer support agent."
        )
    except LLMError:
        # Use deterministic DB catalog answer
        answer = format_product_answer(product)
```

**Files:** `Backend/src/domains/agents/customer_support/{worker.py, handler.py, shopify_storefront_client.py, rules.py}`

---

### Agent 6: Analytics Insights

**Purpose:** Compute metrics, generate insights, track KPIs.

**Subscribed events:**
- `events` channel
- `agent.analytics_insights` channel

**Background loop:**
```
Every 1 hour:
   ├─ posts_published = COUNT FROM generated_posts WHERE status='published'
   ├─ replies_sent = COUNT FROM replies WHERE status='posted'
   ├─ revenue_total = SUM FROM orders
   ├─ orders_count = COUNT FROM orders
   ├─ low_stock_open = COUNT FROM low_stock_alerts WHERE is_resolved=false
   └─ handoffs_count = COUNT FROM handoff_logs
   ↓
INSERT INTO report_snapshots (metric_name, value, period_start, period_end)
   ↓
UPDATE kpis SET current_value=...
```

**Dashboard endpoint** (computed on-demand):
- `GET /api/v1/analytics/dashboard` → live metrics
- `GET /api/v1/analytics/summary` → Gemini-generated executive summary
- `GET /api/v1/analytics/revenue?days=7` → daily revenue for charts

**Files:** `Backend/src/domains/agents/analytics_insights/{worker.py, handler.py, metrics.py, api.py}`

---

### Agent 7: Collaboration Orchestrator

**Purpose:** Coordinate multi-agent workflows for complex tasks.

**Subscribed events:**
- `events` channel
- `orchestrator.registry` (agent registration)
- `orchestrator.heartbeat` (agent liveness)

**Example workflow — "Low Stock Clearance":**
```
Trigger: LowStockAlert created (variant inventory < 5)
   ↓
plan_workflow() — Gemini call:
   "Given low stock on Cotton Tee, design a 3-step workflow:
    1. Generate promotional post
    2. Schedule for peak hours
    3. Send to customers who bought similar items"
   ↓
Gemini returns JSON: {
   "steps": [
     {"agent": "content_generation", "action": "generate_post", "params": {...}},
     {"agent": "content_scheduling", "action": "schedule_post", "params": {...}},
     {"agent": "comment_engagement", "action": "broadcast_dm", "params": {...}}
   ]
}
   ↓
INSERT INTO workflows (steps_json=..., status='pending')
   ↓
_run_step() executes each step sequentially:
   Step 1 → calls content_generation agent
   Step 2 → calls content_scheduling agent
   Step 3 → calls comment_engagement agent
   ↓
UPDATE workflows SET status='completed'
```

**Files:** `Backend/src/domains/agents/collaboration_orchestrator/{worker.py, handler.py, planner.py, api.py}`

---

## Event-Driven Communication (Redis)

### Channel Map

| Channel | Publisher | Subscribers | Purpose |
|---|---|---|---|
| `webhooks` | `webhooks.py` | `inventory_sync` | Shopify order/product webhooks |
| `sync` | `routes.py` (manual) | `inventory_sync` | Manual sync requests |
| `events` | All agents | All agents | General event bus (post.published, etc.) |
| `content.generation` | API endpoint | `content_generation` | Generate post requests |
| `content.generate.requested` | API endpoint | `content_generation` | Explicit generate trigger |
| `agent.{name}` | API endpoint | Specific agent | Direct agent commands |
| `orchestrator.registry` | All agents | `collaboration_orchestrator` | Agent registration |
| `orchestrator.heartbeat` | All agents | `collaboration_orchestrator` | Liveness (every 30s) |

### Event Flow Example: Customer Places Shopify Order

```
Shopify → POST /webhooks/shop/ahmed-store/orders/create
   ↓
webhooks.py::shopify_webhook()
   ├─ verify_hmac(headers, body)
   ├─ Lookup Store by shop_name
   └─ publish_event(WebhookEvent(...))
   ↓
Redis channel: "webhooks" → message: WebhookEvent
   ↓
inventory_sync handler consumes
   ├─ INSERT INTO orders
   ├─ UPDATE variants.inventory_quantity
   ├─ Check low stock → maybe INSERT INTO low_stock_alerts
   └─ publish_event(InventoryUpdatedEvent(...))
   ↓
Redis channel: "events" → message: InventoryUpdatedEvent
   ↓
analytics_insights handler consumes → updates metrics
   ↓
collaboration_orchestrator handler consumes → maybe triggers workflow
```

---

## Data Flow Diagrams

### Authentication Flow

```
┌──────────┐                    ┌──────────┐                 ┌──────────┐
│ Browser  │                    │ FastAPI  │                 │PostgreSQL│
└────┬─────┘                    └────┬─────┘                 └────┬─────┘
     │                               │                            │
     │ POST /auth/signup             │                            │
     │ {email, password, ...}        │                            │
     ├──────────────────────────────>│                            │
     │                               │ Check email not taken      │
     │                               ├───────────────────────────>│
     │                               │                            │
     │                               │ Hash password (bcrypt)     │
     │                               │ INSERT INTO users          │
     │                               ├───────────────────────────>│
     │                               │                            │
     │                               │ Create JWT (user_id)       │
     │                               │                            │
     │ 201 {access_token, user}      │                            │
     │<──────────────────────────────┤                            │
     │                               │                            │
     │ Save to localStorage          │                            │
     │                               │                            │
```

### Content Generation Flow (3 Gemini Calls)

```
┌──────────┐         ┌──────────┐         ┌──────────┐         ┌──────────┐
│ Frontend │         │ FastAPI  │         │ Gemini   │         │PostgreSQL│
└────┬─────┘         └────┬─────┘         └────┬─────┘         └────┬─────┘
     │                     │                    │                    │
     │ POST /content/      │                    │                    │
     │ generate             │                    │                    │
     │ {product_id: 5}     │                    │                    │
     ├────────────────────>│                    │                    │
     │                     │                    │                    │
     │                     │ RESEARCH prompt    │                    │
     │                     ├───────────────────>│                    │
     │                     │                    │                    │
     │                     │ "Selling points:   │                    │
     │                     │  - Soft cotton     │                    │
     │                     │  - Affordable      │                    │
     │                     │  - Unisex"         │                    │
     │                     │<───────────────────┤                    │
     │                     │                    │                    │
     │                     │ WRITE CAPTION      │                    │
     │                     ├───────────────────>│                    │
     │                     │                    │                    │
     │                     │ "✨ New Cotton Tee │                    │
     │                     │  just dropped!..." │                    │
     │                     │<───────────────────┤                    │
     │                     │                    │                    │
     │                     │ REVIEW             │                    │
     │                     ├───────────────────>│                    │
     │                     │                    │                    │
     │                     │ "Caption approved, │                    │
     │                     │  add #NewDrop"    │                    │
     │                     │<───────────────────┤                    │
     │                     │                    │                    │
     │                     │ Generate image (parallel)              │
     │                     ├───────────────────>│                    │
     │                     │                    │                    │
     │                     │ INSERT INTO generated_posts             │
     │                     ├────────────────────────────────────────>│
     │                     │                    │                    │
     │ 200 {caption,       │                    │                    │
     │      image_url}     │                    │                    │
     │<────────────────────┤                    │                    │
```

---

## Security & Authentication Flow

### JWT Token Lifecycle

```
Signup/Login
   ↓
create_access_token({"sub": user_id, "exp": now+30min})
   ↓
Token stored in localStorage (frontend)
   ↓
Every API call: Authorization: Bearer <token>
   ↓
Backend: get_current_user() dependency
   ├─ Extract token from header
   ├─ decode_access_token(token) → user_id
   ├─ SELECT * FROM users WHERE id=user_id
   └─ Return User object
   ↓
If token expired (30 min):
   └─ 401 response → frontend clearSession() → redirect to /login
```

### Rate Limiting

**Login endpoint:** 5 attempts per 15 minutes (per IP)
- Implementation: `slowapi` in-memory limiter
- Returns 429 Too Many Requests when exceeded

### Platform Token Encryption

**Why:** Shopify/WooCommerce access tokens are permanent. If DB leaks, attackers get full store access.

**How:**
```python
# src/sdk/crypto.py
from cryptography.fernet import Fernet

def encrypt_token(plaintext: str) -> str:
    key = derive_key(settings.ENCRYPTION_KEY)
    f = Fernet(key)
    return f.encrypt(plaintext.encode()).decode()

def decrypt_token(ciphertext: str) -> str:
    key = derive_key(settings.ENCRYPTION_KEY)
    f = Fernet(key)
    return f.decrypt(ciphertext.encode()).decode()
```

**At rest:** `stores.access_token` column stores encrypted ciphertext.
**At use:** Agent decrypts in-memory, uses for API call, never logs.

---

## External Integrations

### Supported Platforms

| Platform | Auth | Capabilities | Status |
|---|---|---|---|
| **Shopify** | OAuth | Products, Orders, Inventory, Webhooks | ✅ Full |
| **WooCommerce** | Basic Auth | Products, Orders | ✅ Full |
| **BigCommerce** | OAuth | Products, Orders | ✅ Full |
| **Amazon SP-API** | OAuth (1hr tokens) | Orders (products need ASIN list) | ⚠️ Partial |
| **Daraz** | OAuth 2.0 (HMAC) | Products, Orders | ✅ Full |
| **Instagram** | Meta Graph OAuth | Posts, Comments | ✅ Full |
| **Facebook** | Meta Graph OAuth | Posts, Comments | ✅ Full |
| **TikTok** | OAuth | Posts | ✅ Full |
| **LinkedIn** | OAuth | Posts | ✅ Full |
| **YouTube** | OAuth | Posts | 🚧 Stub |
| **Twitter/X** | OAuth | Posts | 🚧 Stub |

### Google Gemini Integration

**Used by:** content_generation, comment_engagement, customer_support, analytics_insights, collaboration_orchestrator

**Setup:**
1. Get API key from https://aistudio.google.com/app/apikey
2. Add to `.env`: `GEMINI_API_KEY=AIzaSy...`
3. SDK: `google-generativeai>=0.8.0` (already in requirements.txt)

**Model:** `gemini-2.0-flash-exp` (default, fast + cheap)

**Rate limits (free tier):**
- 15 RPM (requests per minute)
- 1M TPM (tokens per minute)
- 1500 RPD (requests per day)

---

## Cost & Performance

### Per-Customer Daily Usage Estimate

| Operation | Gemini Calls/Day |
|---|---|
| Content generation (3 calls per post × 5 posts) | 15 |
| Comment auto-replies (~2 per day) | 2 |
| Customer support questions (~5 per day) | 5 |
| Analytics summary (1 per day) | 1 |
| **Total per customer per day** | **~23 calls** |

**Free tier capacity:** ~65 customers

**Scaling:** When exceeding free tier, upgrade to paid plan (~$0.075 per 1M input tokens).

### Backend Performance

- **FastAPI async** — handles 1000+ concurrent requests on modest hardware
- **Redis pub/sub** — microsecond latency for inter-agent messaging
- **PostgreSQL** — indexed on user_id, store_id, platform_product_id for fast queries
- **LLM rate limiter** — 3 concurrent Gemini calls max (semaphore in LLMClient)

### Frontend Performance

- **Next.js 15 + React 19** — server components + client components
- **Tailwind CSS 4** — utility-first, no runtime CSS-in-JS
- **Framer Motion** — hardware-accelerated animations
- **localStorage caching** — JWT + user cached, no re-fetch on every page

---

## Monitoring & Observability

### Logs

- **Backend:** `logging.basicConfig(level=INFO)` to stdout
- **Format:** `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- **Key events logged:**
  - LLM calls (model, tokens, duration)
  - Agent lifecycle (start, shutdown, errors)
  - Webhook receipts (with HMAC verification status)
  - OAuth flows (success/failure)

### Health Check

```http
GET /health
   → 200 {"status": "healthy", "service": "Digital FTE Agent", "version": "1.0.0"}
```

### Future Enhancements

- Prometheus metrics endpoint (`/metrics`)
- Sentry integration for error tracking
- Datadog APM for request tracing
- Audit log table for compliance

---

## Quick Reference: Where Things Live

| Need to change... | File |
|---|---|
| LLM model | `Backend/src/sdk/config.py` (line 65) |
| Add new API endpoint | `Backend/src/domains/{auth,ecommerce,agents}/{name}.py` |
| Add new frontend page | `frontend/app/{name}/page.tsx` |
| Add new API client function | `frontend/lib/api.ts` |
| Add new AI agent | `Backend/src/domains/agents/{name}/{worker,handler,api}.py` |
| Add new event type | `Backend/src/sdk/events.py` |
| Add new DB model | `Backend/src/sdk/models/{name}.py` |
| Add new platform connector | `Backend/src/sdk/platforms/{name}.py` |

---

**End of Workflow Documentation**
