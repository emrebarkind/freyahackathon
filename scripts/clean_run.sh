#!/usr/bin/env bash
# Run the official command from a clean checkout of one exact commit, and record what the evidence belongs to.
#   scripts/clean_run.sh <commit> <slot> <brief files...> <tool_api.json>
# Secrets come from the environment (source env.sh first); nothing is copied into the checkout but the inputs.
# Writes <repo>/eval/clean-runs/<slot>/{record.json, outputs...}.
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
commit="$1"; slot="$2"; shift 2
dir="$(mktemp -d)/clean"
git -C "$repo" worktree add --detach -q "$dir" "$commit"
trap 'git -C "$repo" worktree remove --force "$dir" >/dev/null 2>&1 || true' EXIT
mkdir -p "$dir/inputs"
ins=()
for f in "$@"; do cp "$repo/$f" "$dir/inputs/$(basename "$f")"; ins+=("inputs/$(basename "$f")"); done
test -z "$(git -C "$dir" status --porcelain --untracked-files=no)" || { echo "checkout not clean"; exit 1; }
cd "$dir"
set +e
scripts/final_run.sh "$slot" "${ins[@]}"
status=$?
set -e
out="$repo/eval/clean-runs/$slot"
mkdir -p "$out"
cp traces/"$slot".log traces/"$slot".trace.log "$out/" 2>/dev/null || true
cp submission/"$slot".workflow.json submission/"$slot".spec.json "$out/" 2>/dev/null || true
python3 - "$out" "$commit" "$status" "${ins[@]}" <<'EOF'
import hashlib, json, pathlib, re, subprocess, sys
out, commit, status, ins = pathlib.Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), sys.argv[4:]
h = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
log = (out / [p.name for p in out.glob("*.log") if not p.name.endswith(".trace.log")][0]).read_text() if list(out.glob("*.log")) else ""
end = re.search(r"END \S+ total_seconds=([\d.]+) model_calls=(\d+) model_cost_usd=([\d.]+)", log)
res = re.search(r"RESULT: (COMPLETE|INCOMPLETE)[^\n]*((?:\n\[[^\]]*\]   - [^\n]*)*)", log)
ids = re.search(r"workflow_id=(\S+) agent_id=(\S+)", log)
rec = dict(builder_commit=subprocess.check_output(["git", "rev-parse", commit], text=True).strip(), exit_status=status,
           inputs={p: h(p) for p in ins},
           outputs={p.name: h(p) for p in sorted(out.iterdir()) if p.name != "record.json"},
           seconds=float(end.group(1)) if end else None, model_calls=int(end.group(2)) if end else None,
           cost_usd=float(end.group(3)) if end else None, result=res.group(1) if res else None,
           reasons=[l.split("   - ", 1)[1] for l in (res.group(2).strip().splitlines() if res else [])],
           workflow_id=ids.group(1) if ids else None, agent_id=ids.group(2) if ids else None)
(out / "record.json").write_text(json.dumps(rec, indent=1))
print(json.dumps(rec, indent=1))
EOF
