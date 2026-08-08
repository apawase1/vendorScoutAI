#!/usr/bin/env sh
# Used by the Dockerfile HEALTHCHECK. Branches on $SERVICE_ROLE because the
# two roles expose different health paths — Streamlit ships its own
# /_stcore/health endpoint; the webhook service has our own /health.
set -e

PORT="${PORT:-8080}"
if [ "$SERVICE_ROLE" = "webhook" ]; then
  PATH_SEGMENT="/health"
else
  PATH_SEGMENT="/_stcore/health"
fi

python -c "
import sys, urllib.request
try:
    urllib.request.urlopen('http://127.0.0.1:${PORT}${PATH_SEGMENT}', timeout=3)
except Exception as exc:
    print(exc, file=sys.stderr)
    sys.exit(1)
"
