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

## Platform results on candidate 7 (brief B, A+B agent)
Official rule: a run passes only if the ledger is right **and** the judge passes the conversation.

| Run | Simulation | Official | Notes |
|---|---|---|---|
| B default rep 1 | `f341aeb7` | 3/3 read live; **platform now shows PUB-11 and PUB-12 "inconclusive", attempts 4** | See below |
| B default rep 2 | `0e827e31` | **2/3: PUB-12 FAIL** | Persona/judge (harness) mismatch, see below |
| B default rep 3 | `ac4f7173` | 3/3 | Recovered from the platform, not re-run |
| B talkative rep 1 | `614f8dec` | **1/3** | PUB-12: bank API infrastructure error. PUB-13: persona output truncation |
| B talkative rep 2 | `574a77dc` | pending | Recovered with `scripts/recover_sim.py` when it ends |

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
  * **Classification:** a persona-simulator artifact, not a misread brief. The agent's behaviour (wait twice, then
    re-ask, then count a non-answer) is bounded.
  * **No change made** to keep candidate 7 fixed. A possible mitigation, untested: re-ask the pending question instead
    of "please go on", so the persona does not have to reason about its own cut message.

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
