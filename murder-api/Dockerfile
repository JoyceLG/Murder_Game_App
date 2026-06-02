# syntax=docker/dockerfile:1

# ---- builder: install dependencies into an isolated venv ----
FROM python:3.12-slim AS builder
WORKDIR /app
ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install -r requirements.txt

# ---- runtime: copy the venv + source, run as a non-root user ----
FROM python:3.12-slim AS runtime
ENV PATH="/opt/venv/bin:$PATH" PYTHONPATH=/app PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --create-home --uid 1000 app
COPY --from=builder /opt/venv /opt/venv
COPY src/ ./src/
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
