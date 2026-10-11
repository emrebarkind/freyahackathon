# Submission candidates

## Candidate 2 (recommended): builder at `4a919df` (merged as `4a17cd8`)

Candidate 1 plus the policy guards: an amount `create_promise` cannot take is never sent and never changed (the
product ends as not recorded); "last business day of this week" moves to next week only when the brief says so
(`rules.week_end_today`), otherwise it is read literally and reported; attempts count proposals made (a skipped
repeat uses none); no callback window on any weekday is the same as no callback day. `git diff 4a919df 4a17cd8 --
builder requirements.txt scripts kit` is empty. 139 tests pass; the self-test passes on every stored spec.

Rehearsal on `4a919df` (clean tree): `scripts/final_run.sh rehearsal-q1 eval/holdout/q1/brief.md eval/holdout/q1/openapi.json`

| | |
|---|---|
| start / end | 2026-10-11 05:11:42 / 05:14:10 UTC, 149 s |
| model calls | 2, $0.49; validation 0 problems, repair rounds 0/3 |
| local checks | structural 0, tool API 0, self-test 12/12 |
| platform | dry-run passed; workflow `935e69c5-1311-4bbe-b70a-30665085d96a`, agent `680f80f0-4255-4dac-b1a9-5914984c9e13`, version 2; chat smoke test passed |
| reported in the trace | UNSUPPORTED: week-end step not stated by the brief (read literally); no callback day |
| spec vs frozen key (holdout q1) | 16/16 |

```
75ab37f3dbce7264f0255590dfb3ba4342d33dc49b138d30d09e449def6eeb55  submission/rehearsal-q1.workflow.json
4085d2b3af9d6833d90794c0b416ed8197f74b5b754ee1195624f43f68f3fe1b  submission/rehearsal-q1.spec.json
54d22faa24e77e6e32319c785b990f810fd0db06c8cb7fa936cf6b565457e7be  traces/rehearsal-q1.log
428aaee3d4f5966e94b50012230365553ce8a01e620fbfb33843eaae0bd65d65  traces/rehearsal-q1.trace.log
```

The extractor on kit brief A with this candidate writes `week_end_today: next_week` (brief A's rule 30) and
`opening_is_attempt: false` (one check run, $0.61).

## Candidate 1: builder at `e071300`

**Builder code: commit `e07130073f6bd261669a9dc542a3728f1ecd90d7`** (branch `claude/keen-fermat-t25udu`, mirrored to
`hack/main`). Every builder file (`builder/`, `requirements.txt`, `scripts/final_run.sh`) is as in that commit; later
commits add only outputs and documents. A change to `builder/` after this point needs a new rehearsal and a new entry
here.

### Rehearsal on candidate 1 (full pipeline, platform included)

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

### Measured limits (see README "Known limits", docs/EXPERIMENTS.md)

* Pence/cents `create_promise`: verified locally and in the compiled workflow (integer field, `promise_scale` 100,
  no silent rounding); on the platform only the pounds path was observed (`{"amount": 420, ...}`), because practice
  sessions accept only the public cases.
* (Candidate 1 only, fixed in candidate 2) a pounds-integer API without a rounding rule got a fractional value, and
  "last business day of this week" always moved to next week when today was that day (brief A's rule).
* Extraction accuracy: three frozen packages x 2 runs per mode, plus holdout q1 x 2 runs. Small samples.
