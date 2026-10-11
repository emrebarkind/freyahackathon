# Submission candidate

**Builder code: commit `e07130073f6bd261669a9dc542a3728f1ecd90d7`** (branch `claude/keen-fermat-t25udu`, mirrored to
`hack/main`). Every builder file (`builder/`, `requirements.txt`, `scripts/final_run.sh`) is as in that commit; later
commits add only outputs and documents. A change to `builder/` after this point needs a new rehearsal and a new entry
here.

## Rehearsal on the candidate (full pipeline, platform included)

Run from a clean working tree at `e071300`:
`scripts/final_run.sh rehearsal-p2 eval/packages/p2/brief.md eval/packages/p2/openapi.json`

| | |
|---|---|
| start / end | 2026-10-11 04:52:34 / 04:55:12 UTC, 158 s |
| model calls | 2 (one reading at effort high, one targeted audit), $0.65; validation 0 problems, no repair round |
| local checks | structural 0, tool API 0, self-test 13/13 |
| platform | dry-run validation passed; workflow `325139dd-1843-4fdd-8053-80393cdc53a2`, agent `3a2d08a5-2c33-4668-a168-4b24b1ed1d70`, version 2; 25 nodes, 16 engine-run calls |
| chat smoke test | engine runs on the platform (asks the first security question), no unfilled placeholder, nothing about the debt before verification |
| spec vs frozen key | 30/30 (p2 is no longer a clean holdout: its failures shaped the opening-count option) |
| secrets in traces | none |

Artifacts of that run (sha256):

```
c10a0e93e648c86e6ffb574cdbd0f82a6b5cce9deb2d56004aeeb00343803a03  submission/rehearsal-p2.workflow.json
b70681888d0b9ebc137978d834d4096f423a216ac02d1823ba00a1aa203ea19a  submission/rehearsal-p2.spec.json
c2cbe81b52ce47c3a70bb5f43fc78b891fa76736b10df01535a960f906f566ad  traces/rehearsal-p2.log
5d1054418ef0b406789fa538c8afcdff2dd1da42072971d362499219d43e9a3e  traces/rehearsal-p2.trace.log
```

Local state at the candidate: 134 tests pass; the self-test passes on every stored spec (A, B, C, D, E, F, p2).

## Measured limits (see README "Known limits", docs/EXPERIMENTS.md)

* Pence/cents `create_promise`: verified locally and in the compiled workflow (integer field, `promise_scale` 100,
  no silent rounding); on the platform only the pounds path was observed (`{"amount": 420, ...}`), because practice
  sessions accept only the public cases.
* Ladder date "last business day of this week" when today is that day: moves to next week (brief A's rule); a brief
  that skips that step instead is not expressible (holdout q1, C5).
* Extraction accuracy: three frozen packages x 2 runs per mode, plus holdout q1 x 2 runs. Small samples.
