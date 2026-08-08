#!/usr/bin/env sh
# Single image, two roles — selected by $SERVICE_ROLE so nothing
# environment/role-specific is baked into the image itself; the same image
# built once in CI runs as either service depending on how it's started.
set -e

ROLE="${SERVICE_ROLE:-ui}"
PORT="${PORT:-8080}"

case "$ROLE" in
  ui)
    # `exec` so streamlit becomes PID 1 and receives SIGTERM directly
    # (needed for its own shutdown handling to run at all).
    exec streamlit run app.py \
      --server.port="$PORT" \
      --server.address=0.0.0.0 \
      --server.headless=true \
      --browser.gatherUsageStats=false
    ;;
  webhook)
    # gunicorn's master becomes PID 1 -> real graceful shutdown on SIGTERM
    # (stop accepting new connections, drain in-flight, then exit).
    exec gunicorn -c gunicorn.conf.py webhook_server:app
    ;;
  *)
    echo "Unknown SERVICE_ROLE: '$ROLE' (expected 'ui' or 'webhook')" >&2
    exit 1
    ;;
esac
