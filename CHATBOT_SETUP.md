# Digital FTE Chatbot Setup

The project contains two chatbot widgets and one shared backend brain:

- `Backend/chatbot_free/` — Free Plan, read-only
- `Backend/chatbot_pro/` — Pro Plan, action-capable
- `Backend/src/domains/agents/customer_support/` — shared Customer Support Agent

## Backend routes

After starting FastAPI, Swagger will show:

- `POST /chatbot/query` — Free chatbot
- `POST /agent/query` — Pro Agent
- `POST /api/v1/support/chat` — underlying Customer Support API

Both chatbot routes require the normal Bearer JWT and a connected active store. The backend resolves the first active store owned by the signed-in user when `store_id` is not supplied.

## Free vs Pro

Free is enforced server-side as read-only: cart action intents are rejected even if a client is modified in the browser.

Pro uses the same Customer Support Agent but can reach the action flows exposed by the handler. At the moment the supported store action is cart-add; cart remove/update return a safe "not available yet" response instead of accidentally calling cart-add.

This zip does not invent payment/subscription verification. The `dfte_plan` switch selects the widget, while real billing entitlements should be wired to your future subscription model/gateway before production.

## Run backend with Docker

From `Backend/`:

```powershell
docker compose up --build
```

Then open:

`http://localhost:8000/docs`

For a clean project database during development, the compose file uses its own `postgres_data` volume. If you intentionally need to reset only this compose project's database:

```powershell
docker compose down -v
docker compose up --build
```

Do not run `down -v` against another compose project that contains data you need.

## Run backend locally with Docker PostgreSQL/Redis

Use the host-published ports from compose:

```env
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/digital_fte"
REDIS_URL="redis://localhost:6379/0"
```

Run FastAPI with the project's virtualenv Python:

```powershell
& ".\.venv\Scripts\python.exe" -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
```

## Test the widgets directly

- Free: `http://localhost:8000/static/chatbot_free/chatbot_test.html`
- Pro: `http://localhost:8000/static/chatbot_pro/chatbot_test.html`

You must first log in and connect an active store because the chatbot routes are authenticated.

## Frontend

The Next.js layout now loads one chatbot widget automatically. Default is Free.

To test Pro in the browser console:

```js
localStorage.setItem("dfte_plan", "pro");
location.reload();
```

For Free:

```js
localStorage.setItem("dfte_plan", "free");
location.reload();
```

The frontend uses `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`) for the chatbot API and static widget assets.
