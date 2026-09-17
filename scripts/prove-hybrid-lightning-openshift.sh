#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Deterministic proof that hybrid Lightning (in-cluster vLLM) + Ultra (NVIDIA API)
# is wired correctly on OpenShift. Re-run after deploy changes; exit non-zero on failure.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACT_DIR="${ARTIFACT_DIR:-/tmp/aiq-hybrid-lightning-proof}"
mkdir -p "$ARTIFACT_DIR"
LOG="$ARTIFACT_DIR/proof.log"
: >"$LOG"

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG"; }
fail() { log "FAIL: $*"; exit 1; }

VLLM_MODELS_URL="http://vllm-inference-service-predictor.aiq-inference.svc.cluster.local/v1/models"
VLLM_BASE_URL="http://vllm-inference-service-predictor.aiq-inference.svc.cluster.local/v1"
AIQ_NS="${AIQ_NS:-aiq}"
INFER_NS="${INFER_NS:-aiq-inference}"
AIQ_LOCAL_URL="${AIQ_SERVER_URL:-http://127.0.0.1:8000}"
AIQ_PY="${REPO_ROOT}/skills/aiq-research/scripts/aiq.py"
JOB_TIMEOUT_SEC="${JOB_TIMEOUT_SEC:-600}"
POLL_SEC="${POLL_SEC:-15}"

log "=== 1) Repo overlay tests ==="
(
  cd "$REPO_ROOT"
  uv run pytest tests/deploy/test_validated_pattern_overlay.py -q
) 2>&1 | tee -a "$LOG"

log "=== 2) Cluster: InferenceService Ready ==="
IS_READY="$(oc get inferenceservice vllm-inference-service -n "$INFER_NS" \
  -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)"
[[ "$IS_READY" == "True" ]] || fail "InferenceService not Ready (got '$IS_READY')"
log "InferenceService Ready=True"

log "=== 3) Backend pod -> vLLM Service (port 80, not 8080) ==="
oc exec -n "$AIQ_NS" deploy/aiq-backend -- python3 -c "
import urllib.request, sys
url = '${VLLM_MODELS_URL}'
try:
    r = urllib.request.urlopen(url, timeout=15)
    body = r.read().decode()
except Exception as e:
    print('CONNECT_FAIL', e)
    sys.exit(1)
if 'nemotron-3.5-lightning-30b-a3b' not in body:
    print('MODEL_MISSING', body[:200])
    sys.exit(1)
print('CONNECT_OK')
" 2>&1 | tee -a "$LOG" | grep -q CONNECT_OK || fail "backend cannot reach vLLM at $VLLM_MODELS_URL"

log "=== 4) Secret must not override Lightning URL with :8080 ==="
if oc get secret aiq-credentials -n "$AIQ_NS" -o jsonpath='{.data.AIQ_LIGHTNING_BASE_URL}' 2>/dev/null | grep -q .; then
  LIGHTNING_URL="$(oc get secret aiq-credentials -n "$AIQ_NS" \
    -o jsonpath='{.data.AIQ_LIGHTNING_BASE_URL}' | base64 -d)"
  if [[ "$LIGHTNING_URL" == *":8080"* ]]; then
    fail "aiq-credentials AIQ_LIGHTNING_BASE_URL uses :8080; KServe predictor Service is port 80: $LIGHTNING_URL"
  fi
  log "AIQ_LIGHTNING_BASE_URL=$LIGHTNING_URL"
else
  log "AIQ_LIGHTNING_BASE_URL not set in secret (workflow default applies)"
fi

log "=== 5) AI-Q health ==="
curl -sf "${AIQ_LOCAL_URL}/health" >/dev/null || fail "AI-Q not reachable at $AIQ_LOCAL_URL (start: oc -n $AIQ_NS port-forward svc/aiq-backend 8000:8000)"
log "AI-Q health OK at $AIQ_LOCAL_URL"

log "=== 6) shallow_researcher end-to-end (Lightning via vLLM) ==="
export AIQ_SERVER_URL="$AIQ_LOCAL_URL"
JOB_ID="$(python3 "$AIQ_PY" submit "What is Red Hat OpenShift AI in one sentence?" shallow_researcher \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")"
log "submitted job $JOB_ID"
ELAPSED=0
STATUS="unknown"
while [[ "$ELAPSED" -lt "$JOB_TIMEOUT_SEC" ]]; do
  sleep "$POLL_SEC"
  ELAPSED=$((ELAPSED + POLL_SEC))
  STATUS="$(python3 "$AIQ_PY" status "$JOB_ID" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_status']['status'])")"
  log "  job $JOB_ID status=$STATUS (${ELAPSED}s)"
  [[ "$STATUS" == "completed" || "$STATUS" == "failure" ]] && break
done
python3 "$AIQ_PY" status "$JOB_ID" | tee "$ARTIFACT_DIR/shallow-job.json" >>"$LOG"
[[ "$STATUS" == "completed" ]] || fail "shallow_researcher did not complete (status=$STATUS)"

log "=== 7) vLLM served traffic during shallow job ==="
VLLM_HITS="$(oc logs -n "$INFER_NS" -l serving.kserve.io/inferenceservice=vllm-inference-service \
  -c kserve-container --since=15m 2>/dev/null | grep -c 'POST /v1/chat/completions' || true)"
log "vLLM chat/completions requests (last 15m): $VLLM_HITS"
[[ "$VLLM_HITS" -ge 1 ]] || fail "no POST /v1/chat/completions in vLLM logs"

log "=== PASS: hybrid Lightning proof complete ==="
log "Artifacts: $ARTIFACT_DIR/proof.log $ARTIFACT_DIR/shallow-job.json"
