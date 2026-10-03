# Fixes Applied

This package keeps the original project source and applies the following integration fixes:

1. Added a `Chatbots` FastAPI router with:
   - `POST /chatbot/query` for Free Plan read-only chat.
   - `POST /agent/query` for Pro Agent chat/actions.
   - Both routes use the existing Customer Support Agent handler.
   - Store ownership is checked against the authenticated user.

2. Mounted the existing chatbot assets:
   - `/static/chatbot_free/*`
   - `/static/chatbot_pro/*`

3. Fixed the frontend chatbot API mismatch:
   - Free no longer calls a missing `/chatbot/query` under a manually concatenated base path.
   - Pro can use the real `/agent/query` adapter.
   - Both widgets preserve `conversation_id`.

4. Added automatic Next.js `ChatbotLoader` so the selected plan widget can appear on the frontend.

5. Free Plan is server-enforced as read-only for cart actions. Pro can use the action paths already exposed by Customer Support.

6. Prevented the current Customer Support handler from mistakenly treating cart-remove/cart-update intents as cart-add.

7. Made the Docker stack project-specific and isolated:
   - Docker PostgreSQL host port: `5434`
   - Docker Redis host port: `6380`
   - Dedicated compose project name: `fte_ecommerce`

8. Added `START_DOCKER.ps1`, `START_LOCAL.ps1`, `CHATBOT_SETUP.md`, and `TEST_CHATBOTS.md`.

Note: real payment/subscription entitlement enforcement is not fabricated here. The Free/Pro widget selector is functional, while actual billing status should be wired to the future subscription/gateway implementation before production.
