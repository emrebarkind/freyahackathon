# Freshness of extraction results (branch `claude/keen-fermat-t25udu-freshness`, commit `f021fc5`)

**Invariant.** An extraction result from an earlier customer turn is never used as a new answer, above all not as an
acceptance, refusal or confirmation that authorises a write.

## Root cause (candidate 9, `cbe10e8`)
* **The step node can run again without a new customer message.** This happens when a chained bank call fails back
  to the step (recovery), or on a result path.
* **What the engine does with used values:**
  * after using a turn, `take_input` resets the stage variables to platform-valid values (`_kind` "none", `_cut`
    "no", `_side` "none", text/date "", amount 0);
  * `chain_plan`, however, cleared `_kind`/`_cut` with "", which the platform rejects for enum variables (the
    observed `validation_errors`).
* **The `heard` check in `chain_step`** then saw "none"/"no" (non-empty strings) and treated a turn nobody spoke as
  answered.
* **Consequence:** any value still in a variable could be used again, e.g. an earlier "yes" that could not be
  cleared.
* **Fields affected:** `_kind`, `_cut`, `_side`, `_text`, `_date`, `_amount`, `_for` and `id_norm`. Dates and
  amounts have the same freshness dependency, because they are read in the same `take_input` call.

## Mechanism
* **The platform's own counters.** `<node>.total_turns` exists for every talk node and appears in every call
  snapshot; `vars` holds the workflow variables.
* **The engine stores the call's customer-turn count:**
  * when it uses an answer (`turns_seen`);
  * when it plans a chain (`turns_at_plan`).
* **A step with no new customer turn uses nothing:** it says the last line again, with no state change, no attempt
  and no write.
* **Without visible counters,** only a non-reset value counts as an answer.
* **Resets are platform-valid.** Accumulated partial answers (held amount pieces, agreed plans) live in the engine
  state, not in these variables, and are untouched.

## Evidence
**Local, with the simulator now faithful to the platform** (it rejects code writes outside an enum and counts turns
like the platform). `tests/test_freshness.py`:

| Test | Candidate 9 | f021fc5 |
|---|---|---|
| No new message after a used answer is not a customer turn | FAIL | pass |
| An old yes left in the variable never authorises a write | **FAIL (went to api_promise)** | pass |
| An old no left in the variable uses no attempt | FAIL | pass |
| An old cut flag does not make a new fragment | FAIL | pass |
| A genuine new identical answer is taken, written once | pass | pass |
| Without the counters, a reset value is still not an answer | pass | pass |

**Regression gate:**
* 231 tests pass, also with the counters hidden;
* 26 stored specs score the same on p1–p3 and h2;
* the stress set stays 50/50;
* engine code 86,117 bytes;
* no new workflow variables.

**Platform** (clean build of `f021fc5`, agent workflow `0d7201f4`, chat route, real practice bank):
* **Counters reach the code node.** The engine's `turns_seen` followed the platform's turn count at every turn
  (2, 3, 4, 5, 6, 7) in call `ce202ae8`.
* **Re-entry without a customer message** (PUB-10 session: the first create_promise returns 500): the step ran
  again from the failed chain; one retry; exactly one successful promise; then close_call.
* **Rejected schema writes in the call: 0** (candidate 9: after_kind / after_cut rejected).
* **A rejected-day conversation** gave the same result as before.

**Not obtained on the platform:** the forced stale-yes trigger.
* The method was to inject an engine state with `confirm_kind="yes"` as chat call variables.
* Every injected first message returned 504, on both candidate 9 and the fix, while plain chat messages worked at
  the same time.
* So "an old yes with no new message does not write" is proven locally only (faithful simulator), not on the
  platform.

## Decision
Candidate 9 stays selected. `f021fc5` is ready on its branch. Its mechanism is verified on the platform (counter
visibility, re-entry path, zero rejected writes). The specific stale-yes trigger is not reproduced there.
**Remaining check:** reproduce the stale-yes trigger on the platform. The chat API refused injected state, so this
needs another method.
