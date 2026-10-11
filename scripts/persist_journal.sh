#!/bin/bash
# Make the simulation journal durable off this machine: commit the tracked copy and push it (4 tries, backoff).
# Called by run_cases.py the moment a simulation id exists (SIM_JOURNAL_GIT=1), so a lost container loses no id.
cd "$(dirname "$0")/.." || exit 1
exec 9>/tmp/persist_journal.lock; flock 9
git add eval/sim-journal.jsonl && git commit -qm "Journal: simulation $1 $2

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01KdXdkXwz4hnpWNsx5cadPC" -- eval/sim-journal.jsonl >/dev/null
for d in 2 4 8 16; do git push -q origin HEAD 2>/dev/null && exit 0; sleep $d; done
exit 1
