# Deploying VendorScoutAI to production

This covers everything needed to run VendorScoutAI as a real, always-on
service on Google Cloud Run: the container image, CI/CD, config, graceful
shutdown, circuit breakers, and alerting. The code and automation are all in
this repo already — the parts that are missing are the ones that *require
your own Google Cloud account and credentials*, which I can't provision on
your behalf. Everything below marked **[YOU RUN THIS]** is a command you run
once, yourself, outside of any assistant session.

## Architecture in one paragraph

The app is one Docker image with two roles, selected by `SERVICE_ROLE`
(`entrypoint.sh`): `ui` runs the Streamlit dashboard, `webhook` runs the
Flask endpoint Meta calls with inbound WhatsApp replies. They deploy as two
separate Cloud Run services from the same image so each scales and fails
independently. Because they can end up as genuinely different containers,
the WhatsApp "inbox" that bridges them is Redis in production, not a local
file (see `tools/inbox_store.py`) — a local file would silently drop replies
the moment they're not the same instance.

## 1. One-time GCP setup **[YOU RUN THIS]**

```bash
# Pick a project + region you'll use for this.
export PROJECT_ID=your-gcp-project
export REGION=asia-south1

gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com monitoring.googleapis.com logging.googleapis.com

# Artifact Registry repo the CI/CD workflow pushes images to.
gcloud artifacts repositories create vendorscoutai \
  --repository-format=docker --location="$REGION"

# Service account CI deploys as. Keep its permissions minimal: it can push
# images, deploy Cloud Run revisions, and read the secrets it needs — nothing
# else.
gcloud iam service-accounts create vendorscoutai-deployer \
  --display-name="VendorScoutAI CI/CD deployer"

for role in roles/run.admin roles/artifactregistry.writer roles/iam.serviceAccountUser roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:vendorscoutai-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$role"
done

# Simplest auth path for a fast setup: a JSON key, stored as a GitHub secret.
# (Workload Identity Federation avoids this long-lived key entirely — see
# google-github-actions/auth's docs if you want to harden this later; the
# deploy.yml workflow's `auth` step is a one-line swap either way.)
gcloud iam service-accounts keys create vendorscoutai-deployer-key.json \
  --iam-account="vendorscoutai-deployer@${PROJECT_ID}.iam.gserviceaccount.com"
# Copy the *contents* of that file into the GCP_SA_KEY GitHub secret (step 3
# below), then delete the local copy — it's a live credential.
```

## 2. Secrets **[YOU RUN THIS]**

Everything sensitive — API keys, tokens, phone numbers, the Redis connection
string — lives in Secret Manager, never in the image or in plain env vars in
the Cloud Run service config. `deploy.yml` wires these in via `--set-secrets`.

```bash
# Repeat for each secret below: create it once, then set its value.
for name in GOOGLE_API_KEY META_ACCESS_TOKEN META_PHONE_NUMBER_ID \
            META_VERIFY_TOKEN META_APP_SECRET VENDOR_WHATSAPP_TO \
            DEMO_PRIORITY_VENDOR_CONTACT DEMO_PRIORITY_VENDOR_NAME REDIS_URL; do
  gcloud secrets create "$name" --replication-policy=automatic 2>/dev/null || true
done

# Then set each one's value (this prompts for input so it's never in shell
# history):
echo -n "your-value" | gcloud secrets versions add GOOGLE_API_KEY --data-file=-
# ...repeat for the others. DEMO_PRIORITY_VENDOR_CONTACT/NAME can be empty
# secrets if you don't want a guaranteed demo vendor in production.
```

Grant access to **two** service accounts — they're different identities
doing different jobs, and both need it:

- `vendorscoutai-deployer@...` — runs the `gcloud run deploy` command from CI.
- The Cloud Run **runtime** service account — what the container actually
  runs as once deployed, which is what resolves `--set-secrets` at
  container start. Unless you set `--service-account` explicitly in
  `deploy.yml` (we don't, to keep setup simple), this defaults to the
  project's Compute Engine default service account,
  `PROJECT_NUMBER-compute@developer.gserviceaccount.com` — find your
  project number with `gcloud projects describe $PROJECT_ID --format="value(projectNumber)"`.

Skipping the second one is a common trip-up: the deploy step itself
succeeds, then Cloud Run fails to start the revision with a "Permission
denied on secret ... Revision service account" error.

```bash
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")

for name in GOOGLE_API_KEY META_ACCESS_TOKEN META_PHONE_NUMBER_ID \
            META_VERIFY_TOKEN META_APP_SECRET VENDOR_WHATSAPP_TO \
            DEMO_PRIORITY_VENDOR_CONTACT DEMO_PRIORITY_VENDOR_NAME REDIS_URL; do
  for member in "serviceAccount:vendorscoutai-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
                "serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"; do
    gcloud secrets add-iam-policy-binding "$name" \
      --member="$member" \
      --role="roles/secretmanager.secretAccessor"
  done
done
```

### Redis (shared WhatsApp inbox)

Any managed Redis works — the code just needs a `REDIS_URL`. The fastest
free option:

1. Create a free database at [upstash.com](https://upstash.com) (a few
   minutes, no card required at the free tier).
2. Copy its `rediss://...` connection string into the `REDIS_URL` secret
   above.

(Cloud Memorystore is the GCP-native option if you'd rather stay in one
cloud, but it requires a VPC connector for Cloud Run to reach it — more
one-time setup than a hackathon timeline usually wants.)

## 3. GitHub repo config **[YOU RUN THIS]**

In **Settings → Secrets and variables → Actions**:

**Secrets:**
| Name | Value |
|---|---|
| `GCP_SA_KEY` | contents of `vendorscoutai-deployer-key.json` from step 1 |
| `GOOGLE_API_KEY` | (optional) lets `ci.yml` also run the full pipeline test, not just the guardrail unit tests |

**Variables:**
| Name | Value |
|---|---|
| `GCP_PROJECT_ID` | your project id |
| `GCP_REGION` | e.g. `asia-south1` |
| `AR_REPO` | `vendorscoutai` |
| `VENDORSCOUT_STUB` | `0` for live Google Search, `1` to keep it deterministic |
| `VENDORSCOUT_WHATSAPP_STUB` | `0` for live WhatsApp |

Push to `main`. `ci.yml` runs on every push/PR (no cloud credentials needed —
safe on forks too); `deploy.yml` fires automatically once CI goes green on
`main` and deploys both Cloud Run services.

## 4. Alerting **[YOU RUN THIS]**

```bash
./ops/alerts/create-log-metrics.sh   # one-time: turns circuit-breaker logs into a metric

export NOTIFICATION_CHANNEL=$(gcloud beta monitoring channels create \
  --display-name="VendorScoutAI on-call" \
  --type=email --channel-labels=email_address=you@example.com \
  --format="value(name)")

./ops/alerts/apply.sh
```

Four policies, each tied to something a user actually feels, each with a
runbook in its own YAML (`ops/alerts/*.yaml`):

- **Error rate** — 5xx responses piling up.
- **Latency** — p95 request latency crossing a threshold for a sustained window.
- **Saturation** — CPU utilization sustained above 80%, i.e. "about to fail," not a momentary blip.
- **Circuit breaker open** — Gemini or Meta has failed 3+ times in a row and we've stopped hammering them.

Deliberately not included: raw CPU/memory threshold alerts with no
sustained-window requirement, request-count alerts, or anything that fires
on normal traffic variance. An alert that isn't reliably actionable trains
people to ignore the next one.

## 5. Graceful shutdown

**Webhook service:** runs under `gunicorn` (`gunicorn.conf.py`), not Flask's
dev server. On `SIGTERM` — what Cloud Run sends before stopping a container
— gunicorn's master stops routing new requests to workers, lets in-flight
requests finish (up to `graceful_timeout`, 30s by default), then exits. This
is exactly "stop accepting new requests, drain in-flight, then exit," and
it's gunicorn's default behavior, not custom code.

**UI service:** Streamlit isn't a traditional request/response server — it's
a long-lived WebSocket connection per browser tab, so "drain in-flight
requests" doesn't map onto it the same way. Streamlit registers its own
`SIGTERM`/`SIGINT` handlers and closes its server on receipt. The practical
production concern isn't per-request draining, it's **mid-negotiation
sessions surviving a deploy** — Cloud Run's rolling deploy model handles
this: a new revision starts, passes its health check, traffic shifts to it,
and the old revision keeps serving existing connections for its termination
grace period before being killed. No code change needed; just don't set an
aggressively short grace period if you ever tune it.

## 6. Circuit breakers

`tools/circuit_breaker.py` — no new dependency, ~90 lines, fully auditable.
Wraps two calls to services we don't control:

- **Meta's Graph API** (`tools/whatsapp_provider.py`) — opens after 3
  consecutive send failures, stays open 30s, then allows one probe.
- **Gemini/ADK** (`agents.py`'s `VendorScout._drive`) — same pattern, 20s
  reset. When open, the UI shows a plain "service temporarily unavailable,
  try again shortly" message instead of hanging or crashing.

Every state transition logs at `WARNING` (`circuit_breaker name=... state=...`),
which is what `ops/alerts/circuit-breaker-open.yaml` alerts on.

## 7. Config — what's externalized

Nothing environment-specific is baked into the image. Every value that
differs between dev/staging/prod is either a plain env var (`SERVICE_ROLE`,
`VENDORSCOUT_STUB`, `GEMINI_MODEL`, ...) or a Secret Manager secret (API
keys, tokens, phone numbers, `REDIS_URL`). `.env.example` documents every
variable both services read; there's no personal phone number, name, or
credential hardcoded anywhere in the source anymore — `DEMO_PRIORITY_VENDOR_*`
defaults to empty/generic and the demo-vendor injection is a no-op until you
set it.

The webhook's inbound requests are also verified — `META_APP_SECRET` (if
set) is used to check Meta's `X-Hub-Signature-256` HMAC on every POST, so an
unauthenticated request can't inject fake vendor replies into a live
negotiation.

## 8. Manual deploy (bypassing CI, for emergencies) **[YOU RUN THIS]**

```bash
docker build -t "${REGION}-docker.pkg.dev/${PROJECT_ID}/vendorscoutai/vendorscoutai:manual" .
docker push "${REGION}-docker.pkg.dev/${PROJECT_ID}/vendorscoutai/vendorscoutai:manual"

gcloud run deploy vendorscoutai-ui \
  --image "${REGION}-docker.pkg.dev/${PROJECT_ID}/vendorscoutai/vendorscoutai:manual" \
  --region "$REGION" --set-env-vars "SERVICE_ROLE=ui"
  # ...plus --set-secrets as in deploy.yml
```

## 9. Local dev

```bash
cp .env.example .env   # fill in values; VENDORSCOUT_STUB=1 needs nothing but GOOGLE_API_KEY
docker compose up --build
# UI:      http://localhost:8501
# Webhook: http://localhost:8000/health
```

This runs both services plus Redis locally, exercising the exact same
multi-instance-safe path production uses.

## What I couldn't do for you

I don't have your GCP project, billing account, or credentials, so I
couldn't create the Artifact Registry repo, the service account, the
Secret Manager secrets, the Redis instance, or the notification channel —
every command above marked **[YOU RUN THIS]** is one you need to actually
run. Once those exist and the GitHub secrets/variables are set, pushing to
`main` deploys automatically from then on.
