# The Morning Desk — one image serves the API *and* the frontend.
# Portable to Fly, Render, Railway, or a VPS.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend ./backend
COPY frontend ./frontend

# main.py resolves ../frontend relative to itself, and --app-dir puts backend/
# on the import path so `import main`, `from config`, `from sources...` resolve.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8000}"]
