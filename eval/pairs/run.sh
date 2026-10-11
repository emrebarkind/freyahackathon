#!/usr/bin/env bash
# Build every variant in eval/pairs locally (no deploy), 4 at a time, then score each against its own key.
#   eval/pairs/run.sh <out dir>
set -uo pipefail
cd "$(dirname "$0")/../.."
out="$1"; mkdir -p "$out"
ls -d eval/pairs/*/ | xargs -n1 basename | xargs -P 4 -I{} sh -c \
  'timeout 1500 python3 builder/build.py eval/pairs/{}/brief.md eval/pairs/{}/openapi.json --slot pair-{} --no-deploy > '"$out"'/{}.log 2>&1; echo "exit $?" >> '"$out"'/{}.log'
for v in $(ls -d eval/pairs/*/ | xargs -n1 basename); do
  cp "submission/pair-$v.spec.json" "$out/$v.spec.json" 2>/dev/null
  python3 eval/score.py "$out/$v.spec.json" "eval/pairs/$v" > "$out/$v.score.json" 2>/dev/null
done
