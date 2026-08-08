# syntax=docker/dockerfile:1
#
# One image, two roles (SERVICE_ROLE=ui|webhook — see entrypoint.sh). Built
# once in CI, deployed as two separate Cloud Run services. Nothing
# environment-specific is baked in: every value that differs between dev,
# staging, and prod comes from env vars / Secret Manager at run time, never
# from a build arg or a file copied into the image.

# ---------------------------------------------------------------- builder
FROM python:3.11-slim AS builder
WORKDIR /app

# build-essential only exists in this stage — some transitive deps (grpcio,
# used by google-adk/google-genai) occasionally need to compile on platforms
# without a prebuilt wheel. The final image never sees this layer.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ----------------------------------------------------------------- final
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SERVICE_ROLE=ui \
    PORT=8080

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app --home /app app

COPY --from=builder /install /usr/local

# Only what the two services actually import at runtime — tests/, docs/,
# and the markdown docs are excluded via .dockerignore.
COPY agents.py app.py webhook_server.py gunicorn.conf.py entrypoint.sh healthcheck.sh ./
COPY tools/ ./tools/
COPY .streamlit/ ./.streamlit/

RUN chmod +x entrypoint.sh healthcheck.sh && chown -R app:app /app

USER app

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["/app/healthcheck.sh"]

ENTRYPOINT ["/app/entrypoint.sh"]
