# ═══════════════════════════════════════════════════════════════
# Backend Dockerfile — unified Digital FTE backend (port 8000)
# ═══════════════════════════════════════════════════════════════

FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

EXPOSE 8000

# Railway and similar hosts inject $PORT; default to 8000 locally / on a VPS.
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
