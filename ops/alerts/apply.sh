#!/usr/bin/env bash
# Applies every alert policy in this directory. Run create-log-metrics.sh
# first (circuit-breaker-open.yaml depends on it).
#
# Usage:
#   export NOTIFICATION_CHANNEL="projects/YOUR_PROJECT/notificationChannels/1234567890"
#   ./ops/alerts/apply.sh
#
# Create a notification channel first if you don't have one:
#   gcloud beta monitoring channels create \
#     --display-name="VendorScoutAI on-call" \
#     --type=email --channel-labels=email_address=you@example.com
# (or --type=slack / --type=pagerduty — see `gcloud beta monitoring channels create --help`)
set -euo pipefail

: "${NOTIFICATION_CHANNEL:?Set NOTIFICATION_CHANNEL first — see the header comment above}"

cd "$(dirname "$0")"

for policy in error-rate.yaml latency.yaml saturation.yaml circuit-breaker-open.yaml; do
  echo "Applying $policy ..."
  envsubst < "$policy" > "/tmp/${policy}.rendered"
  gcloud alpha monitoring policies create --policy-from-file="/tmp/${policy}.rendered"
done

echo "Done. List policies with: gcloud alpha monitoring policies list"
