# Candidate 7: final measurement record

## Version under test
* Builder commit **`3d62e449c85ae97ddf17366d1fc249fc460820ad`**. `builder/` and `eval/score.py` are unchanged from it to
  HEAD (`git diff 3d62e44 HEAD -- builder eval/score.py` is empty); 204 tests pass.
* Clean builds at that commit (official command, clean checkout):
  * Brief A: COMPLETE, 439.8 s, 3 model calls, $1.07, agent `33a1c6db-e55a-41fc-9060-417c11ee3a6a`
    (`eval/clean-runs/cand7-a/`).
  * Briefs A+B: COMPLETE, 416.3 s, 3 model calls, $1.01, agent `b3b11a55-afbe-4b47-b73c-6328a9b5882e`
    (`eval/clean-runs/cand7-ab/`).
* Changes since candidate 6 (`593635d`), in order:
  * `45d363e` K1–K8 review fixes:
    * audit records stored flat;
    * model tools disabled;
    * an engine crash closes as service_error;
    * no by_type single-entry fallback;
    * quote matching;
    * code size;
    * promise_scale doc;
    * a repair cannot drop code_tables.
  * `7e7d6cf` platform resilience: 5xx retries, never-zero deploy.
  * `d36d1c7`:
    * M1: the opening ask on every first answer, too_much refuse, weekend pay day.
    * M2: product order.
  * `d6849b0` scorer: hardship close and note follow the brief.
  * `13d8d19` deploy and export survive platform 5xx.
  * `0fe5366` independent oracle reading at build time.
  * `0337072` M3 dated value changes (`spec.changes`).
  * `3d62e44` fresh local builds:
    * h2 24/24;
    * f1 20/20;
    * oracle 22/22 agree.

## Per customer, all runs on candidate 7 (from the stored snapshots, `scripts/combine_reps.py`)
Brief A, default style:

| customer | rep1 | rep2 | rep3 | counts |
|---|---|---|---|---|
| PUB-01 … PUB-10 | pass | pass | pass | yes (each of the 10) |

Brief B (agent `b3b11a55`):

| customer | default rep1 | default rep2 | default rep3 | talkative 1 | talkative 2 | counts (default 3) |
|---|---|---|---|---|---|---|
| PUB-11 | no verdict (platform "inconclusive") | pass | pass | pass | pass | not confirmed |
| PUB-12 | no verdict (platform "inconclusive") | FAIL (conversation; harness mismatch) | pass | FAIL (bank API errors) | FAIL (platform stall) | no |
| PUB-13 | pass | pass | pass | FAIL (persona truncation) | FAIL (persona truncation, max duration) | yes |

## Known gaps at candidate 7
Verdicts:
* **fixed + evidence**: the cause is closed and the evidence is named.
* **open**: the gap remains.
* **not measured**: no evidence either way.

The local scores below come from `python3 eval/score.py <spec> eval/heldout/h2` at HEAD.

| Gap | Verdict | Evidence | Caveat |
|---|---|---|---|
| h2 C21/C22: after a dispute, the opening ask counts as refused for the other products | **fixed in the engine (local evidence only)** | Built-in `consume_opening()` (`builder/runtime/engine.py`, d36d1c7). Test `test_state_failures.py::test_a_dispute_on_one_product_at_the_opening_spends_the_opening_for_the_others`. The *same* old spec `h2-retest.spec.json` scored 21/24 at 593635d; today it scores 23/24 with only C24 failing. That shows the fix is in the engine, not in a new reading | h2 has been seen and was used to design the fix, so this is not blind. No h2 build exists at 3d62e44 (m3-h2 was built at 0337072). h2 has never run on the platform |
| Product order (h2 C24) | **fixed (local evidence only)** | `multi.order` (d36d1c7). m3-h2 spec carries `order: by type [overdraft, credit_card, personal_loan], then by amount`. m3-h2 scores 24/24 (C24 passes); the old spec still fails C24. Test `test_products_are_handled_in_the_briefs_order` | Same caveats as above |
| Silent rule loss (a rule dropped and not flagged) | **open / not measured** | Oracle (`builder/oracle.py`) and policy audit exist. Re-run on the old h2 spec, the oracle flags C1 and C9 (dated memo values) but **not C21/C22**: its check types cannot express a multi-product conversation rule. The policy audit checks one field at a time, and in C21/C22 the fields were right but the engine behaviour was not. The docstring's "f1 4/4, h2 3/3" has no stored result file | No unseen brief has been built at 3d62e44. The C21/C22 class (correct fields, missing engine semantics) is still undetectable at build time |
| Multi-product close rule ("no_promise with the reason of the first product in handling order") | **open (unverified)** | The m3-h2 build (0337072) flagged it as "not carried". 3d62e44 only changed `spec_doc.md` to call it built-in | No rebuild has shown the flag gone |
| Weekend coverage | **partly fixed locally; not measured on the platform** | `pay_day()`, `deadline_adjust`, ladder dates moved off non-business days. Tests: `test_yes_today_on_a_saturday_is_recorded_for_the_next_business_day`, `test_multi_weekend_date_for_all_is_adjusted_for_all`, `test_day_of_month_rolls_before_the_weekend_move_only_when_the_brief_says_so`. p3 C20 (offers on a Saturday) passes | The self-test `every_band` **skips non-business call days**. Every platform call so far has `now` = Wednesday 2026-10-14 |
| Blind measurement | **open** | `eval/heldout/` holds only h2, and h2 has been seen | Candidate 7 has no blind score |

## PUB-13 talkative: local replay and a fix on a separate branch
* **Replay:** `scripts/replay_call.py` feeds each recorded customer turn, with the platform's own extraction for it,
  to the engine, against a local bank holding the case's identity and products. No platform is used.
* **At 3d62e44 the replay matches the recordings exactly:** 33/33 agent lines for talkative rep 2, 18/18 for rep 1,
  7/7 for each default run.
* **Concrete defects found:**
  1. **The agreed plan is lost.** After four unanswered read-backs, silence is turned into "no": both products are
     reopened and the agent goes back to the first offer ("Could you pay 300 dollars on Friday 16 October?").
  2. **Content-free turns are unbounded.** "please go on" is said 18 times in one call (10 in rep 1), because its
     counter resets after every other line.
* **Fix**, branch `claude/keen-fermat-t25udu-cutfix`, commit `217e298`. Candidate 7 is **not** changed.
  * **Change:** an unanswered read-back is not a refusal. The plan is kept and read again every third time, and
    "please go on" is capped at 4 per call; after that, a cut-off message gets the question itself again.
  * **Tests:** 2 new tests, both fail on 3d62e44 and pass on the fix; 206 pass in total.
  * **Replays on the fix:**
    * Talkative rep 2: plan kept, no return to the first offer, 4 content-free lines out of 34.
    * Default runs: unchanged (promise p1 300 on 30 Oct, p2 900 on 23 Oct).
* **Not fixed:**
  * In negotiation, three identical unanswered lines still count as a non-answer ("no"). With 20 more cut fragments,
    rep 1 ends as refused with refused notes. This rule predates candidate 7 and is unchanged.
  * A customer who never finishes a sentence cannot pass under any agent policy.
* **The fix is unvalidated on the platform.** It changes behaviour only on cut-off messages.

## Platform results on candidate 7 (brief B, A+B agent)
Official rule: a run passes only if the ledger is right **and** the judge passes the conversation.

| Run | Simulation | Official | Notes |
|---|---|---|---|
| B default rep 1 | `f341aeb7` | 3/3 read live; **platform now shows PUB-11 and PUB-12 "inconclusive", attempts 4** | See below |
| B default rep 2 | `0e827e31` | **2/3: PUB-12 FAIL** | Persona/judge (harness) mismatch, see below |
| B default rep 3 | `ac4f7173` | 3/3 | Recovered from the platform, not re-run |
| B talkative rep 1 | `614f8dec` | **1/3** | PUB-12: bank API infrastructure error. PUB-13: persona output truncation |
| B talkative rep 2 | `574a77dc` | **1/3** (recovered, not re-run) | PUB-12: platform stall. PUB-13: persona truncation, then max call duration |
| A default reps 1–3 | `cd806dc6`, `2575f86e`, `e612640c` | **30/30 runs, 10/10 customers at 3/3** | Agent `33a1c6db`, label `cand7-3d62e44-A-default` |

### Rep 1: unresolved inconsistency
* run_cases printed PASS for all three when the run ended (1727 s, with 502s on the simulation GET).
* Today the platform reports, for the same iteration:
  * attempts=4 for every run;
  * PUB-11 and PUB-12 with outcome "inconclusive" and no reason;
  * PUB-13 pass.
* The calls that are kept (12:26–12:35, all `assistant-ended-call`) are from attempt 4. Their ledgers are complete
  and correct, with one set of tool calls each.
* The earlier attempts left no tool calls.
* Why the verdict changed after the live read is **unknown** from the records.
* Conservative count: 1/3 confirmed by the judge, 3/3 by the ledger.

### PUB-12, rep 2: why the ledger shows verify, verify, get_account, verify, verify, get_account
* **Official: FAIL.**
* The ledger of customer `c_b7a7970f-b8c` holds two calls of the agent.
* **Attempt 1, call `e32887d5`** (12:37:34): never ended, status 180, no transcript. Ledger rows 1–4:
  * dob ok;
  * phone `4401` → verified false;
  * phone `4410` → verified true;
  * get_account.
* **The platform retried the run, call `ac5bf4f2`** (12:47:49, iteration `attempts=1`, `settings.maxRetries=3`). It
  used the **same practice session**. Rows 5–11:
  * dob;
  * phone `4401` → **verified true**, because the session was already verified in attempt 1;
  * get_account, create_promise, two notes, close_call.
* The judge saw only the retry. In it the phone question was asked once, and the persona's script ("wrong digits
  first, then asked again once") did not happen. So the conversation check failed.
* *Persona/judge (harness) mismatch note:* the transcript shows the agent acting correctly on what the bank
  returned. But a correct bank record does not mean the conversation check passed, and the run stays FAIL.
* **Correction:** the commit message of `c5ac5f0` says "the persona gave the right phone digits at once". That is
  wrong. The persona gave `4401` (wrong), and the bank answered true because of the session that persisted from the
  stuck first attempt.

### Talkative rep 1
* **PUB-12: infrastructure.** The bank API returned HTML errors (function_call_error ×3) and close_call failed.
  The agent said "our system is not responding" and ended the call. Counted as FAIL, not as an agent bug.
* **PUB-13:**
  * **Mechanism:** truncated persona output. After the disclosure, every customer message is the start of a sentence
    ("I've been running around all", "...trying to get these"). The agent waits twice ("Sorry, please go on."), then
    re-asks or moves on.
  * **The customer hung up after about 6 minutes** with no answer ever completed.
  * **Evidence that the truncation is on the persona side** (the persona model's own output, not the agent cutting in):
    * Some customer messages leak the persona model's reasoning: `"thought\nI've been running around all morning"`,
      and in PUB-11 `"thought\nThe user is asking for the last four"` and `'Wait, the rule says "When you give a
      number'`.
    * The truncation also happens after the agent's shortest line, and with a 15–25 s gap before the agent speaks.
  * **Same run, PUB-11:** the same truncation in identity for 8 turns, then a complete answer, then a PASS.
  * **Classification, corrected:** the *fragments* come from the persona simulator, but the agent's response to them
    had two real agent defects, found later by local replay (see "PUB-13 talkative: local replay"). The earlier
    statements "not an agent bug" and "the agent's behaviour is bounded" were **wrong**:
    * after unanswered read-backs, the engine dropped the customer's completed plan;
    * it said "please go on" 18 times in one call.
  * **No change made** to keep candidate 7 fixed. A possible mitigation, untested: re-ask the pending question instead
    of "please go on", so the persona does not have to reason about its own cut message.

### Talkative rep 2
* **PUB-12: platform stall.**
  * The call has the greeting and the customer's first answer.
  * After that there is no node event, no extraction and no agent turn for 60 s, and then the customer hung up.
  * Same signature as an outage. Counted as FAIL.
* **PUB-13: persona truncation again.**
  * The customer's first nego answer came through almost whole ("I cannot pay today, but I want to pay both on the
    30th of Octobe…").
  * The agent read back the right plan: card 300 on 30 October, loan 900 on 23 October.
  * Every answer after that was a cut preamble, sometimes the same words repeated ("My cousin's wedding is", "I have
    been dealing with so many emails this").
  * After three unanswered read-backs the engine counted a non-answer and went back to the offer ladder.
  * The call hit the platform's maximum duration (430 s, exceeded-max-duration) with nothing recorded.
* **Persona truncation** is now seen in:
  * 3 of 6 talkative B calls on candidate 7;
  * 0 of 9 default B calls.

## Latency (where an agent turn's time goes)
* Source: `scripts/latency.py` on 4 candidate-7 simulations, output in `eval/clean-runs/cand7-ab/latency-4sims.txt`.
* Segments per customer turn:

  | Segment | Covers | Share of mean turn |
  |---|---|---|
  | talk | customer message → first node entry | **85–91%** (median 6–19 s, by run) |
  | code | engine code node `step` | 4–12% (median 0.5–1.0 s) |
  | api | bank HTTP | 1–7% |
  | reply | last node → agent text | ~0% |

* The records **cannot** split "talk" into extraction-model time and platform queueing: there is no event between
  the user message and the node entry. That split is **unknown**.
* The same agent's median ranges from 8.5 to 20.6 s across runs, which points to load on the platform's model.
  This is consistent with a platform cause but not proven.

## Results that survive a restart
* `run_cases.py` writes every simulation id to `kit/build-the-builder/results/sim-journal.jsonl` the moment it is
  created ("started", with the case ids, the persona style, the practice customer ids and `RUN_LABEL`). It writes
  "finished" when the run ends.
* After a restart:
  1. `scripts/sims.py` lists what runs on the platform.
  2. `scripts/recover_sim.py <id> --out ...` rebuilds the scored rows from the judge verdicts and the bank ledgers,
     without re-running.
