#!/usr/bin/env bash
# Final-day helper: run the builder on one hidden brief exactly as submitted, keep the full log, check the outputs.
#   scripts/final_run.sh hidden-1 briefs/hidden-1.md briefs/hidden-1.openapi.json
# Produces traces/hidden-1.log (everything printed), traces/hidden-1.trace.log (the builder's own trace),
# submission/hidden-1.workflow.json (the export we submit) and submission/hidden-1.spec.json.
set -euo pipefail
cd "$(dirname "$0")/.."
name="$1"; shift
mkdir -p traces submission
[ -f env.sh ] && source env.sh
set +e
python3 builder/build.py "$@" --slot "$name" 2>&1 | tee "traces/$name.log"
status=${PIPESTATUS[0]}
set -e
test -s "submission/$name.workflow.json" || { echo "MISSING submission/$name.workflow.json (build exit $status)"; exit 1; }
grep -E "fak_[A-Za-z0-9]{8}|sk-ant-" "traces/$name.log" "traces/$name.trace.log" && { echo "SECRET IN TRACE"; exit 1; } || true
echo "---- summary"
grep -E "TEST FAIL|validation round|local self-test|UNSUPPORTED|RESULT|FREYA workflow_id|END " "traces/$name.log" || true
if [ "$status" -ne 0 ]; then
  echo "INCOMPLETE (exit $status): the agent is exported but does not meet every rule; read the RESULT note above"
  exit "$status"
fi
echo "OK: submission/$name.workflow.json, traces/$name.log, traces/$name.trace.log"
