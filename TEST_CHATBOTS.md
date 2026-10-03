# Quick Chatbot Test

1. Start Docker PostgreSQL + Redis and FastAPI:

```powershell
.\START_LOCAL.ps1
```

2. Open Swagger:

`http://127.0.0.1:8000/docs`

Look under **Chatbots** for:

- `POST /chatbot/query` — Free
- `POST /agent/query` — Pro

3. Log in through the existing frontend first and connect a store. The chatbot routes use the same Bearer JWT as the rest of the app.

4. Test the packaged widgets directly:

- `http://127.0.0.1:8000/static/chatbot_free/chatbot_test.html`
- `http://127.0.0.1:8000/static/chatbot_pro/chatbot_test.html`

The widgets now persist their conversation ID and send it back to the backend.

5. To switch the dashboard widget between plans:

```js
localStorage.setItem("dfte_plan", "free");
location.reload();
```

or:

```js
localStorage.setItem("dfte_plan", "pro");
location.reload();
```

The frontend loader points to the FastAPI server via `NEXT_PUBLIC_API_URL`.
