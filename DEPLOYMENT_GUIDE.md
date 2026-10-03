# Digital FTE Deployment Guide

## Local Docker

From the project root:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\START_DOCKER.ps1
```
Backend docs: http://localhost:8000/docs

## Frontend local

```powershell
cd frontend
npm install
copy .env.example .env.local
npm run dev
```
Open http://localhost:3000

Set:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_CHATBOT_PLAN=free
```

To test the Pro widget in the browser console:
```js
localStorage.setItem("dfte_plan","pro")
location.reload()
```

## Production recommendation

Recommended architecture:
- Frontend: Vercel (Next.js)
- Backend/API + workers: Railway (Dockerfile)
- PostgreSQL: Railway managed PostgreSQL
- Redis: Railway managed Redis
- Static chatbot assets: served by FastAPI and loaded by the frontend

Railway maps Docker Compose services to separate Railway services and supports managed PostgreSQL/Redis. Configure the backend with Railway reference variables for DATABASE_URL and REDIS_URL.

Production environment variables must include:
- DATABASE_URL
- REDIS_URL
- SECRET_KEY
- JWT settings
- FRONTEND_URL
- BACKEND_PUBLIC_URL
- CORS_ORIGINS
- Shopify/Google/social OAuth credentials
- Gemini/LLM credentials
- any payment gateway credentials used by the project

After deployment:
1. Open the backend public URL + `/docs`.
2. Open `/health`.
3. Verify `/chatbot/query` and `/agent/query`.
4. Deploy the frontend to Vercel with NEXT_PUBLIC_API_URL set to the backend public HTTPS URL.
5. Update backend CORS_ORIGINS and OAuth callback URLs to the production URLs.
