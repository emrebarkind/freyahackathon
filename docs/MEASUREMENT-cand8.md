# Candidate 8: validation record

## Version under test
* Builder commit **`9cb2300d9ada3449fbf88a5968fcd8df9cb8d6d8`** on branch `claude/keen-fermat-t25udu-cutfix`.
* **Rollback point:** candidate 7 (`3d62e44`).
* Changes since candidate 7 (only these two commits):
  * **`217e298`:**
    * An unanswered read-back is not a refusal; the agreed plan is kept and re-read every third time.
    * "please go on" is capped at 4 per call.
  * **`9cb2300`:**
    * A non-answer counts against the customer only when the brief says so (`rules.non_answer_counts`, default
      false). A cut-off fragment never counts.
    * Empty turns in negotiation and read-back are bounded at 12 in a row. At the cap the call closes with the
      brief's close for used-up attempts, and only when the brief's non-answer rule is on. Nothing is recorded
      without a clear yes.
* **Local evidence:**
  * 210 tests pass. 6 new tests in `tests/test_cut_fragments.py`; the two from `217e298` fail on candidate 7.
  * The frozen packages p1–p3 and h2 give the same scores on 26 stored specs before and after. Those keys do not
    exercise non-answers, so this shows no local harm, not correctness.
  * **Replays of the recorded PUB-13 talkative calls** (`scripts/replay_call.py`):
    * plan kept;
    * no return to the first offer;
    * 4 content-free lines.
* **Clean build at 9cb2300** (`eval/clean-runs/cand8-ab/record.json`):
  * Briefs A+B: COMPLETE, 180.7 s, 3 model calls, $1.04, agent `3578abe5-3368-4fd6-889f-01be4ea7fdd1`.
  * `rules.non_answer_counts`: explicit true, quoting brief A rule 30: "A flat refusal or a non-answer uses one
    persuasion attempt."
  * **Spec difference from candidate 7:** in rules, only `non_answer_counts`. The rest is wording of agent lines
    from a fresh extraction, which confounds a direct comparison.

## Platform (agent 3578abe5; simulation ids pushed the moment they existed, `eval/sim-journal.jsonl`)

| Run | Simulation | Result |
|---|---|---|
| PUB-13 talkative | `9a2c49a3` | **pass** (ledger and judge) |
| B default rep 1 | `6a811438` | 3/3 |
| B default rep 2 | `91d7eeca` | 3/3 |
| B default rep 3 | `b160ecbc` | 3/3 |

Per customer, B default: PUB-11 3/3, PUB-12 3/3, PUB-13 3/3. No platform retries (attempt 0 everywhere). Turn median
was 7–14 s.

### What the PUB-13 talkative pass does and does not show
* **The persona did cut off.** 4 fragments: 1 in identity, 3 in negotiation, 1 after the promise.
* **Agent response:** "please go on" 3 times, under the cap.
* **Customer outcome:** the customer finished each sentence, proposed 30 October for both products, and accepted
  23 October for the loan. They confirmed the read-back at once.
* **Not exercised on the platform:** the paths this candidate fixes, namely
  * repeated unanswered read-backs (plan retention);
  * the "please go on" cap;
  * the stall close.

  Their evidence is local only (tests and replays).
* **One talkative run is not a rate.** On candidate 7, 1 of 3 talkative PUB-13 calls in this style passed.

## Decision against the agreed criteria
| Criterion | Evidence | Met |
|---|---|---|
| The plan is kept | Local tests and replays; not triggered on the platform | locally |
| The loop ends | Local tests (go-on cap 4; stall close at 12 with the brief's rule) | locally |
| An explicit yes is handled correctly | Platform PUB-13 talkative (confirmed → 2 promises → close promise); local test | yes |
| No new regression in B default | 9/9 runs, 3/3 per customer | yes |

**Candidate 8 is selected; candidate 7 remains the rollback.** Not measured on candidate 8:
* brief A on the platform. Candidate 7's A result (30/30) is not carried over.
* other customer styles;
* the fixed paths on the platform.
