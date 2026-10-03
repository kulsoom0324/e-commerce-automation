# 🏗️ Digital FTE — System Architecture

## Overview

**Digital FTE** is an AI-powered e-commerce automation platform designed to function as a digital full-time employee for online businesses. It unifies a modern web frontend, a robust API backend, AI-driven agents, persistent data storage, and third-party e-commerce integrations into a single cohesive system.

The platform is organized into clearly separated layers — presentation, API, business logic, AI orchestration, and data — so that new features, integrations, and automation capabilities can be added without disrupting the core system.

---

## 1. High-Level Architecture

The system follows a **layered client-server architecture**, with a clear separation of concerns between each layer:

| Layer | Responsibility |
|---|---|
| **Client Layer** | Web browser, chatbot widgets, and future client applications |
| **Frontend Layer** | User interface, dashboards, and interactive experiences |
| **API / Backend Layer** | Authentication, business logic, and request handling |
| **AI Orchestration Layer** | Coordinates specialized AI agents for automation tasks |
| **AI / LLM Layer** | Executes natural language and generative AI tasks via Google Gemini |
| **Data Layer** | Persistent storage (PostgreSQL) and caching/queuing (Redis) |
| **External Services** | Third-party e-commerce platforms and OAuth providers |

### Request Flow

```
Client (Browser / Chatbot)
        │
        │  HTTPS / REST
        ▼
  Frontend (Next.js)
        │
        │  REST API + JWT
        ▼
  Backend API (FastAPI)
        │
        ├─► Authentication & Domain Services
        │
        ▼
  AI Agent Orchestration
        │
        ├─► PostgreSQL   (persistent data)
        ├─► Redis        (cache, queues, coordination)
        ├─► External APIs (Shopify, WooCommerce, etc.)
        └─► Google Gemini (AI generation)
        │
        ▼
  Response → Dashboard / User
```

**In short:** the frontend handles everything the user sees and interacts with, while the backend owns authentication, business rules, AI orchestration, data persistence, and communication with external platforms.

---

## 2. Frontend Layer

Built with **Next.js, React, and TypeScript**, the frontend layer provides the dashboard and user-facing tools:

- **Dashboard** — central control panel for store owners
- **Stores** — manage connected e-commerce platforms
- **Products** — catalog and inventory views
- **Analytics** — performance metrics and insights
- **AI Chatbots** — Free and Pro conversational assistants

This layer communicates with the backend exclusively through authenticated REST API calls.

---

## 3. Backend / API Layer

Built with **FastAPI (Python)**, the backend layer is organized into modular domains:

- **Authentication** — signup, login, Google OAuth, JWT issuance
- **Store Management** — connecting, syncing, and managing e-commerce stores
- **OAuth / Integrations** — secure connections to Shopify, WooCommerce, and other platforms

These domains feed into a central **AI Agent Orchestration** layer, which decides which specialized agent should handle a given task.

---

## 4. AI Agent Architecture

Digital FTE's automation is powered by a set of **specialized, single-responsibility agents**. Each agent focuses on one business function, making the system easier to extend and maintain.

| Agent | Responsibility |
|---|---|
| 📦 Inventory Sync | Synchronizes products, stock levels, and order data |
| ✍️ Content Generation | Produces AI-generated marketing and social content |
| 📅 Content Scheduling | Plans and schedules generated content |
| 💬 Comment Engagement | Classifies and responds to customer comments |
| 🎧 Customer Support | Handles AI-powered customer conversations |
| 📊 Analytics Insights | Calculates KPIs, metrics, and summaries |
| 🔄 Collaboration Orchestrator | Coordinates multi-step, multi-agent workflows |
| 🔎 SEO Insights | Performs SEO analysis and recommendations |
| 👥 Customers | Aggregates and processes customer data |

### Agent Execution Flow

```
Business Event
      │
      ▼
FastAPI Domain Service
      │
      ▼
Agent Selection (Orchestrator)
      │
      ▼
   AI Agent
      │
      ├──► PostgreSQL (read/write data)
      ├──► Redis (queue / cache)
      ├──► External Platform (Shopify, WooCommerce, etc.)
      └──► Google Gemini (AI reasoning / generation)
              │
              ▼
         Agent Result
              │
              ▼
      User / Dashboard
```

This design keeps each agent independent, testable, and replaceable — new agents can be added without modifying existing ones.

---

## 5. E-Commerce Integration Layer

Digital FTE uses a **connector-based integration model**, allowing new e-commerce platforms to be added without redesigning the core application.

```
                Digital FTE
                     │
        ┌────────────┼────────────┐
        ▼                         ▼
  Platform Router            OAuth Layer
        │                         │
 ┌──────┼──────┬───────────┐      │
 ▼      ▼      ▼           ▼      ▼
Shopify WooCommerce BigCommerce  OAuth Providers
        │
        ▼
   Unified Domain Model
        │
Products / Orders / Customers
```

Currently supported integration targets: **Shopify, WooCommerce, BigCommerce, Amazon, and Daraz.**

Each connector translates a platform's native data format into a common internal model, so the rest of the system doesn't need to know which platform a store is connected to.

---

## 6. Chatbot Architecture

Two distinct chatbot experiences are provided, each with a different purpose and API endpoint:

```
             Chatbot UI
                 │
      ┌──────────┴──────────┐
      ▼                     ▼
 Free Chatbot           Pro Chatbot
      │                     │
      ▼                     ▼
/chatbot/query         /agent/query
      │                     │
      ▼                     ▼
General Knowledge     Agent-Oriented AI
```

- **Free Chatbot** — general-purpose Q&A, no agent access
- **Pro Chatbot** — connects to the AI agent layer for store-specific, action-oriented assistance

**Supported languages:** English 🇬🇧, Urdu 🇵🇰, Roman Urdu 🇵🇰

---

## 7. Authentication Flow

```
User
 │
 ├── Signup
 ├── Login
 └── Google OAuth
        │
        ▼
   Authentication Service
        │
        ▼
     JWT Token
        │
        ▼
 Protected API Requests
        │
        ▼
User / Store / Agent Data
```

All protected endpoints require a valid JWT issued after successful authentication (standard signup/login or Google OAuth).

---

## 8. Data Layer

| Store | Purpose |
|---|---|
| **PostgreSQL** | Primary persistent storage — users, stores, products, orders, customers, analytics |
| **Redis** | Caching, background task queues, and cross-agent coordination |

---

## 9. Production Deployment Architecture

```
                    Internet
                       │
                       ▼
              ┌─────────────────┐
              │   Vercel        │
              │  Next.js App    │
              └────────┬────────┘
                       │ HTTPS
                       ▼
              ┌─────────────────┐
              │   Railway       │
              │  FastAPI API    │
              └────────┬────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
   PostgreSQL        Redis      Worker / Agent Tasks
                       │
                       ▼
              External APIs & Google Gemini
```

- **Frontend** deploys to **Vercel**
- **Backend** deploys to **Railway**
- **Database and cache** run as managed services
- **Background workers** handle asynchronous agent tasks

---

## 10. Technology Stack Summary

**Frontend:** Next.js 15, React 19, TypeScript, Tailwind CSS, Framer Motion, Google OAuth
**Backend:** Python, FastAPI, Uvicorn, SQLAlchemy, Pydantic, Alembic, JWT
**AI:** Google Gemini via a centralized LLM client with agent-specific handlers
**Infrastructure:** Docker, Docker Compose, PostgreSQL, Redis, Vercel, Railway

---

## Why This Architecture Works

- **Separation of concerns** — frontend, backend, AI orchestration, and data are cleanly decoupled
- **Extensibility** — new agents or e-commerce connectors can be added independently
- **Scalability** — Redis-backed queues allow agent workloads to scale asynchronously
- **Security** — JWT-based auth and OAuth isolate credentials from business logic
- **Maintainability** — domain-driven backend structure keeps each business area self-contained
# auto-fte
