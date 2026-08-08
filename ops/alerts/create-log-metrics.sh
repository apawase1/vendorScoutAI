#!/usr/bin/env bash
# One-time setup: turns our circuit breaker's log line into a Cloud Logging
# log-based metric, which circuit-breaker-open.yaml then alerts on. Run once
# per GCP project (idempotent — safe to re-run, it just updates).
#
# Usage: ./ops/alerts/create-log-metrics.sh
set -euo pipefail

gcloud logging metrics create vendorscoutai_circuit_breaker_open \
  --description="Counts circuit_breaker state=open log lines from either VendorScoutAI service (tools/circuit_breaker.py)" \
  --log-filter='resource.type="cloud_run_revision"
    AND (resource.labels.service_name="vendorscoutai-ui" OR resource.labels.service_name="vendorscoutai-webhook")
    AND textPayload:"circuit_breaker" AND textPayload:"state=open"' \
  || gcloud logging metrics update vendorscoutai_circuit_breaker_open \
  --log-filter='resource.type="cloud_run_revision"
    AND (resource.labels.service_name="vendorscoutai-ui" OR resource.labels.service_name="vendorscoutai-webhook")
    AND textPayload:"circuit_breaker" AND textPayload:"state=open"'

echo "Log-based metric ready: logging.googleapis.com/user/vendorscoutai_circuit_breaker_open"
