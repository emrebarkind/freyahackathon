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

## Brief A on candidate 8 (regression check for `non_answer_counts`)
* **Clean build at 9cb2300** (`eval/clean-runs/cand8-a/record.json`):
  * Brief A only: COMPLETE, agent `0a63e696-de73-4f10-ac0a-c63c3afa29ce`.
  * `rules.non_answer_counts`: explicit true, quoting rule 30.
* **Default style, 3 reps:** simulations `783dd760`, `6fe2c7fa`, `62726386`.

| customer | rep1 | rep2 | rep3 | counts |
|---|---|---|---|---|
| PUB-01 | pass | pass | pass | yes |
| PUB-02 | pass | pass | pass | yes |
| PUB-03 | pass | pass | pass | yes |
| PUB-04 | pass | pass | pass | yes |
| PUB-05 | pass | pass | pass | yes |
| PUB-06 | pass | pass | pass | yes |
| PUB-07 | pass | pass | pass | yes |
| PUB-08 | pass | pass | pass | yes |
| PUB-09 | pass | FAIL: conversation | pass | no |
| PUB-10 | pass | pass | pass | yes |

**Official: 29/30 runs; 9/10 customers at 3/3. PUB-09 fails rep 2.**

### PUB-09, rep 2: a platform retry, proved from the ledger
* **Call `22a4d604`: the first attempt was correct.** Ledger rows 1–5:
  * dob verified;
  * phone verified;
  * get_account;
  * `transfer_to_agent` restructuring → ok;
  * `close_call` transferred/restructuring → ok.
* **The platform retried the run anyway** (iteration `attempts=3`) on the same practice session. Call `650cc7d4`:
  * Ledger rows 6–9: verify_identity three times, then close_call. Every one was answered by the bank
    `ok:false, "the call is already closed"`.
  * The agent treated the refused answers as unreadable, asked again twice, then closed as identity not verified.
* **The judge saw only the retry** ("transfer_to_agent was never called"). The run stays **FAIL**.
* **Cause:** the same mechanism as candidate 7's PUB-12 rep 2 (platform retry on a persisted session). The
  transfer path does not touch the changed code (read-back and negotiation non-answers).
* **Why the first attempt was retried** is not visible in the records: the iteration keeps only the last call.
* **Also in rep 2:** PUB-06 was retried once (attempt 1) and passed on the retry.

### Comparison with candidate 7 (brief A, default, 3 reps)
* Candidate 7: 30/30 runs, 10/10 customers.
* Candidate 8: 29/30 runs, 9/10 customers.
* The one difference is the platform retry above, not a behaviour change. Nothing in the candidate-8 runs shows a
  regression attributable to the change.

## Targeted check: a completed plan, non-answers at the read-back, then an explicit yes
* **Case:** `eval/targeted/confirm-delay.json`, PUB-01 with a changed persona script.
* **Run:** simulation `05f640a2`, agent `0a63e696`. **pass**, judge and ledger.
* **The persona did what the check needs** (transcript):
  1. **Plan:** the customer agrees to "the full amount today". The agent reads back "420 dollars on Wednesday
     14 October. Do you confirm?".
  2. **First non-answer:** "It's quite cloudy outside today, isn't it?" (extracted unclear, not cut). The agent asks
     "Do you confirm?".
  3. **Second non-answer:** "Well, I was just thinking that ─" (extracted cut). The agent says "Sorry, please go on."
  4. **Explicit yes:** "Yes, I confirm." Only now `create_promise` p1 420 2026-10-14 is called, exactly once.
  5. **Close:** text-message sentence, then `close_call` promise.
* **Shown:** the plan was kept, and nothing was written before the explicit yes.
* **Not shown:** the 12-turn stall close was not reached (two non-answers only). Its evidence stays local.

## Decision (unchanged)
**Candidate 8 stays selected; candidate 7 (`3d62e44`) is the rollback.** On the platform, candidate 8 has:
* B default 9/9;
* PUB-13 talkative pass;
* A default 29/30, the one failure a proven platform retry;
* the targeted read-back check passed.

## Decision against the agreed criteria (first validation)
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
