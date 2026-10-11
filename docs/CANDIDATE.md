# Submission candidates

## Candidate 4 (recommended): builder at `22f774a`

Candidate 3 plus the skill-review fixes and the brief-stated rule options. The platform rehearsal below was built at
`b913754`; `22f774a` changes only the spec doc (the extraction prompt): the built-in "I don't want to talk" handling
is now listed, so a build no longer reports that rule as unsupported.

Changes since candidate 3:
* The opening ask enters the repeat check only if the brief says so (`rules.opening_blocks_repeat`,
  `opening_is_attempt`). In candidate 3 this was a fixed rule taken from r2, and it broke p1 C9.
* `rules.too_much_skips_full`: once the customer says the full amount is too much, later steps naming it are skipped,
  and "too much" counts as a refusal of the current step. Both r2 readings had flagged rule 19 as unsupported.
* The self-test expectations follow dated code changes (`event_changes`) on the scenario date.
* A spec-doc/engine contract test, which found and removed a dead alias.
* Source sentences for critical values (`sources`): a quote that is not in the materials counts as an error.

Local checks: 159 tests pass, and the self-test passes on every stored spec (A, B, C, D, E, h1, p2, q1, A-prime).

Re-extraction (new readings, keys frozen beforehand):

| package | value written | key |
|---|---|---|
| p1 (two readings) | `skipped_repeat_counts: false`, `opening_blocks_repeat: false` | 30/30, 30/30 (candidate 3: 29/30) |
| r2 (two readings) | `skipped_repeat_counts: true`, `opening_blocks_repeat: true` | 22/22, 22/22; both INCOMPLETE (rule 19) |
| r2 (after the new option) | `too_much_skips_full: true` | 22/22 |
| q1 | `skipped_repeat_counts: false` | 16/16 |

Targeted platform rehearsal: A-prime (`eval/platform/aprime/`) is kit brief A plus a memo with two changes:
(1) hardship gets one sentence of sympathy, then a transfer to the support queue with no question asked;
(2) from 12 October 2026, "already paid" closes as `no_promise`/`dispute`.

| | |
|---|---|
| build | 227 s, 3 model calls, $1.09, self-test 13/13; workflow `d7bbc462-6f01-43bc-95f4-8517400e0282`, agent `086f4e3c-2c7a-4762-8dca-dafde431b1be` |
| PUB-01 | promise > close_call `promise` (as in brief A) |
| PUB-05 | "I'm very sorry to hear that. I will connect you with our customer support team now." > `transfer_to_agent {queue: support}` > `close_call {transferred, support}`, no question asked |
| PUB-08 (case date 14 Oct) | `close_call {no_promise, dispute}`, accepted by the bank |

The kit scorer marks PUB-05 and PUB-08 as failed because it applies brief A's expected results; the bank ledger is
what was checked here. The first A-prime run (`eval/platform/aprime/v1/`) used `paid_claimed`, a code made up in
the test memo. The bank rejected it ("this outcome needs one of these reasons"). That was an error in the test brief,
not in the builder: the API's `reason` field has no enum, so only the brief's table defines the allowed values.

Artifacts (sha256):

```
3d2460c3553acf65088e9fe90b72dc5c8a9c028e97453d4d8b63ea878e3a9bc2  submission/rehearsal-aprime2.workflow.json
c9b7a5c072bf7ecca0dc62e247245379273ffd5b4c4a322975bf8a3ddc2a41e2  submission/rehearsal-aprime2.spec.json
9cacf7cb3c83935def5ea6621f86dbe0b0b4f627f6dc25a9ddc4f988ba110d0a  traces/rehearsal-aprime2.log
5f37c640a9630912d55583a3478ba92088d37e7ff1702e61ea3f874556e35ead  traces/rehearsal-aprime2.trace.log
```

## Candidate 3: builder at `41de6d0` (merged as `87a6839`)

Candidate 2 plus the robustness fixes (eval/robust r1-r3, eval/hard h1): floor percentage per product type, step
rounding (up/nearest/down:<step>), minimum floor, a band whose floor is the whole debt, rounded percentage steps;
skipped repeats, promise retries and the week-end rule come from the brief (silent: engine default, written as an
assumption); the refused opening ask is never proposed again; returning to a product repeats its open offer; a
customer reference under another field name reaches every node; the self-test fails a call missing a required field;
tools the API lacks are never called and need no mapping; no callback day means no time question. Repairs only while
they make progress (fewer problems, none new, no passing scenario broken, no stated value dropped, no rule moved to
`unsupported_rules`). A rule not carried or a failing local scenario makes the run INCOMPLETE (exit 3, agent still
exported). `git diff 41de6d0 87a6839 -- builder requirements.txt scripts kit` is empty. 151 tests pass.

Rehearsal on `87a6839` (clean tree): `scripts/final_run.sh rehearsal-h1 eval/hard/h1/brief.md eval/hard/h1/openapi.json`

| | |
|---|---|
| start / end | 2026-10-11 06:11:05 / 06:14:04 UTC, 179 s |
| model calls | 2, $0.63; validation 0 problems, repair rounds 0/3 |
| local checks | structural 0, tool API 0, self-test 13/13 |
| platform | dry-run passed; workflow `ea7991d5-c9c3-423c-95bb-fbcc7df9be6d`, agent `fb681a32-98b0-4306-adb1-00fdec171054`; chat smoke test passed |
| verdict | INCOMPLETE (exit 3): two rules named as not carried (hardship transfer without a question; outcome code switched by call date) |
| spec vs frozen key (hard h1) | 34/34 (candidate 2 on the same brief: 20/34, engine error on per-type floors) |

```
0bd5ae7451cc021b1986e8265b5d78ba741accfb2b4b5dfe0d6ce6b675b86a5e  submission/rehearsal-h1.workflow.json
1d0da208871e3a53f8356e6f8241ea1f2e99dd55cdc1ac282caa06460bb35ba5  submission/rehearsal-h1.spec.json
511eb2dd56f4cd08a69c4534146c0e3a5cc2914bf191e2a2e8731549f0d6159e  traces/rehearsal-h1.log
614b687becbe37d365b6eef2700a42eb08cc37a77cdf938a795856d3bcf20735  traces/rehearsal-h1.trace.log
```

Local builds on this builder: p1 29/30 (INCOMPLETE, 1 rule named), q1 16/16 (COMPLETE), r2 22/22 (INCOMPLETE, 1 rule
named), r3 20/20 (COMPLETE), h1 34/34 (eval/branch-results).

## Candidate 2: builder at `4a919df` (merged as `4a17cd8`)

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
