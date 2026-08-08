"""gunicorn config for the webhook service — real graceful shutdown.

On SIGTERM (what every container platform sends before killing a container),
gunicorn's master:
  1. stops routing new connections to workers,
  2. lets each worker finish in-flight requests, up to `graceful_timeout`,
  3. then exits.

That's "stop accepting new requests, drain in-flight, then exit" — for free,
because it's what gunicorn's master process already does. The Flask dev
server (`app.run()`, still used for local dev in webhook_server.py's
__main__ block) does none of this, which is exactly why production runs
under gunicorn instead.
"""
import os

# Cloud Run (and most PaaS container platforms) inject $PORT and require the
# container to listen on it; WEBHOOK_PORT is the local-dev/docker-compose
# override when there's no platform assigning a port for you.
bind = f"0.0.0.0:{os.getenv('PORT', os.getenv('WEBHOOK_PORT', '8000'))}"
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", "4"))

# Kill a worker that's genuinely stuck (not just slow) after this long.
timeout = int(os.getenv("GUNICORN_TIMEOUT", "30"))
# On SIGTERM, give in-flight requests this long to finish before force-exit.
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = 5

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()
