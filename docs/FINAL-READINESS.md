# Final readiness (prepared 2026-10-11, 14:58–15:45 UTC; candidate 9 added 16:05 UTC)

## Update 16:05 UTC: candidate 9 selected (`cbe10e8ed1801ff4509276c1de9a3f9db4bb4a5a`), candidate 8 (`9cb2300`) is the rollback
* **Fixed customer sentences.** Each was first seen breaking candidate 8.

  | Customer sentence | Candidate 8 | Candidate 9 |
  |---|---|---|
  | "three hundred and" / "fifty dollars" | read as 50, lost | joined to 350 |
  | "700..." / "50" | took the last piece | asks once for the full amount; neither piece taken alone |
  | "...700" / "No, sorry, 800" | 800 | 800 (correction kept) |
  | "Yes... no, Friday does not work." | read back Friday; a plain "Yes." recorded Friday | the day is rejected (whatever the intent label); asks "which day"; "Yes." accepts nothing |
  | Same question asked again | third time counted as a refusal (an attempt used) | answered again; no attempt used |
  | Questions alternating with fragments | reset the non-progress count (unbounded) | counted as non-progress; close only by the brief's non-answer rule |

* **Identity digits in two pieces** ("44..." + "71") were already joined, and still are.
* **build.py:** the tool API is found by content (`paths`); a second JSON file (a code list) is read as material.
  Non-UTF-8 and binary input are reported in the trace.
* **Local evidence:**
  * 225 tests pass;
  * 6 new tests fail on candidate 8 and pass on candidate 9, while 5 normal and real-correction tests pass on both;
  * 26 stored specs score the same on p1–p3 and h2;
  * the stress set stays 50/50;
  * engine code 85,478 bytes (+2,001).
* **Platform evidence (chat route, real extraction and real practice bank)** for each changed path:
  * `32d8fc9`: "300..." + "50 on Friday" → clarifying question → 300.50 written once after the yes; "three hundred
    and" + "fifty" → 350.
  * `cbe10e8`: rejected day → "Which day would work for you instead?" → "Yes." accepts nothing → 20 Oct written after
    the yes.
  * `cbe10e8`: "Which account is this about?" ×3 (labelled `details`) → answered three times, no attempt used →
    promise.
* **Not run on candidate 9:** A and B default simulations. The candidate-8 platform results are not carried over.
* **Correction to section 2.** "Two hidden briefs" comes from the published page. Your newer message says the final
  is one brand-new case that may contain several files; the final e-mail decides the exact file layout. When the
  files arrive, check which file is the OpenAPI and which are material (a code list or table must not be summarised
  by hand). The builder now separates them by content.


## 1. Selected candidate and rollback
* **Selected: candidate 8**, builder commit **`9cb2300d9ada3449fbf88a5968fcd8df9cb8d6d8`**.
  `builder/`, `eval/score.py` and `freya.py` are unchanged from it to HEAD.
* **Rollback: candidate 7**, commit **`3d62e449c85ae97ddf17366d1fc249fc460820ad`**.
* **Repositories:** both commits are ancestors of `hack/main` (github.com/emrebarkind/freyahackathon, verified with
  `git merge-base --is-ancestor`). Git tags could not be pushed (403), so the rollback is identified by its hash.
* **Official command:**
  ```
  set -a; source env.sh; set +a
  python3 builder/build.py briefs/hidden-1.md briefs/hidden-1.openapi.json 2>&1 | tee traces/hidden-1.log
  # or, the helper that also checks for secrets and the export:
  scripts/final_run.sh hidden-1 briefs/hidden-1.md briefs/hidden-1.openapi.json
  ```
* **Outputs:** `submission/<slot>.workflow.json` (export), `submission/<slot>.spec.json`, `traces/<slot>.log`,
  `traces/<slot>.trace.log`.
* **Dependencies:**
  * Python 3.13;
  * `pip install -r requirements.txt` (`claude-agent-sdk==0.2.159`, `pydantic==2.13.5`);
  * the model runs through the Agent SDK's own login (no ANTHROPIC_API_KEY in env.sh).
* **Access checked without printing secrets:**
  * the model answered a schema call in 4.5 s;
  * Freya `GET /api/v2/simulations` answered;
  * FREYA_API_KEY, FREYA_API_URL and FREYA_BANK_TEAM_KEY are set.
* **Candidate-8 builds** (sha256 of outputs in each `record.json`):
  * brief A, `eval/clean-runs/cand8-a`:
    * workflow `fc33755b371debd3…`, trace `d24b4965871db98f…`;
    * agent `0a63e696`;
    * COMPLETE in about 170 s.
  * briefs A+B, `eval/clean-runs/cand8-ab`:
    * workflow `e102b1eb1e18ed03…`, trace `21b6b6154497e34b…`;
    * agent `3578abe5`;
    * COMPLETE in 180.7 s, $1.04.

**Official results on candidate 8 (unchanged; infrastructure failures stay failures):**

| Run | Result |
|---|---|
| A default ×3 | 29/30 runs, 9/10 customers at 3/3. PUB-09 rep 2 FAIL (platform retry on a closed session, see `docs/RETRY-EVIDENCE.md`) |
| B default ×3 | 9/9 runs, 3/3 customers at 3/3 |
| PUB-13 talkative | pass (one run) |
| Targeted read-back (two non-answers, then an explicit yes) | pass |

## 2. Confirmed requirements vs preparation hypotheses
**Confirmed** by the official page (`docs/hackathon/page.txt`) and the kit README:
* two hidden briefs, one clean and one "raw bank material: a mail, a policy extract, a memo that changes it, a code
  list";
* each brief has its own tool API: the 7 tool names are fixed, the fields and allowed values may change;
* customers give "a number said in two parts ('463...' then '51'), corrections, talk about other things, a question
  back, amounts and dates in words";
* at most 30 minutes per build, a trace is required, one unattended run;
* after the briefs open, only builder bugs may be fixed; nothing from a brief may be written into the builder.

| Hypothesis | Status |
|---|---|
| Long, multi-document brief | Partly confirmed (mail + policy + memo + code list). Length unknown |
| Scanned / copied text with noise | Not stated. Copied mail is likely; scans are a hypothesis |
| Conflicting mails, tables, amendments, dated overrides | Confirmed for memo-over-policy and a code list. Dated overrides are a hypothesis |
| Rules scoped to products, bands, dates | Hypothesis (consistent with brief B) |
| Renamed API fields, different money units | Fields and values: confirmed. Units: hypothesis |
| Incomplete, irrelevant, contradictory, fragmented answers | Confirmed: two-part numbers, corrections, off-topic, questions back, words |

None of the hypotheses is written into the builder.

## 3. Synthetic stress set: first attempt, unaltered
* **Packages:** `eval/stress/` (s1-docs, s2-money, s3-conv). Keys are in a separate tree, `eval/stress-keys/`.
* **Frozen before any build.** The builder received only `brief.md` and `openapi.json`.
* **Independent evaluator:** re-derived every check from the documents alone, 50/50 AGREE (`eval/stress-keys/EVALUATOR.md`).

| Package | Build | Score (first attempt) | Time / cost |
|---|---|---|---|
| s1-docs (policy, scoped dated amendment, withdrawn mail, code table, noise) | INCOMPLETE: flags `deadline_adjust` as not supported by a passage (true: the brief does not say which way a non-business deadline moves) | **17/17** | 158.9 s / $0.97 |
| s2-money (renamed fields, cents in and out, rounding boundaries, per-type values) | COMPLETE | **18/18** | 190.4 s / $1.04 |
| s3-conv (3 products, product order, corrections, refusals, partial answers, confirmation) | COMPLETE | **15/15** | 141.7 s / $0.89 |

* **No package was used to guide a fix;** there are no retests.
* **Limits of this set:**
  * its author read `builder/spec_doc.md` to stay inside supported behaviour, so it tests coverage of supported types,
    not unseen ones;
  * the conversation check format has no turn kind for unclear or garbled answers;
  * rule 15 (write order) is not tested;
  * the evaluator lists brief rules nobody could compute (weekend calls, mixed-outcome reason in s2), none of them
    tested.

## 4. Ambiguous customer messages
**Engine level** (`eval/ambiguity/engine_probe.py`): extraction values supplied by hand, so this proves engine
behaviour only. Specs are candidate 8's A and A+B builds.

| Case | Result |
|---|---|
| Filler ×30 ("uh…", "aaa…", "hmm…"), brief counts non-answers | No value invented; 4 "go on"; closes `no_promise/refused` after 12 empty turns (brief A rule 30/31) |
| Filler ×30, brief silent | Nothing written, no close, no refusal (by design) |
| Leaked persona reasoning ("thought\n…") ×20 | Treated as unclear and malformed; nothing written |
| "my salary…" then a date | Promise on the date after the yes |
| Date split over messages | Correct |
| Amount split, extraction gives 300 then 350 | Correct (350) |
| Unrelated sentence plus a date | Correct (20 Oct) |
| Switching products while a proposal is pending | Correct (card 30 Oct, loan 23 Oct) |
| Unclear ×3 at the read-back, then yes | One promise, after the yes |
| Unclear ×3 at the read-back, then no | Nothing written; plan refused; next offer (brief rule) |
| Incomplete forever after a plan, brief counts / silent | No promise without a yes. Counts: closes refused with notes after 12. Silent: plan kept, no close |
| **Same question ×4, brief silent** | **Bug (silent policy):** the third identical line turns the question into "no" and uses an attempt (the same-line guard in `run_turn`). Not fixed |
| **Question alternating with fragments ×20** | **Limit:** each question resets the empty-turn counter, so the 12-turn bound never fires (44 turns, no close). No false write |

**Real extraction path** (platform chat route, candidate-8 A workflow `d7c2b95f`, real practice bank,
`eval/ambiguity/chat_probe_cand8a.json`). The first try was misaligned and is kept as `…first-misaligned.json`.

| Conversation | Result |
|---|---|
| Unclear ("uh…", "I was thinking…") at the read-back, then yes | Promise 420 today, written once, after the yes. **Correct end-to-end** |
| "Yes... no, Friday does not work." | Extraction: kind=no **and** date=Friday. The agent read back 420 on Friday 16 Oct (the rejected day). Then noise and leaked reasoning got "go on", and "…on the 20th" got a new read-back. Yes → 420 on 20 Oct. **No wrong write, but a rejected date was proposed back** |
| "I can pay three hundred and" / "fifty dollars on Friday." | **Consequential bug:** extraction read the amount as 50 (latest message only). The agent offered the floor 126; a "yes" was taken as accepting it; at the read-back a "no" closed the call `no_promise/refused`. The customer's 350 was lost |

* **Same family as the official example.** `"463..."` then `"51"` also fails at engine level on candidate 8: the
  second piece replaces the first.

## 5. Non-progress termination
* An explicit no is a refusal. A question is answered (but see the same-line bug above).
* An incomplete or irrelevant answer counts only if the brief has `non_answer_counts` (brief A rule 30, explicit
  quote in both candidate-8 specs). A fragment never counts.
* With the brief's rule: 12 empty turns in a row end the call with the brief's close for used-up attempts.
* Without it: no close and no invented code; the call runs until the customer or the platform ends it. **Documented
  limitation:** there is no allowed outcome for "never answered".
* A technical failure (bank errors) goes to `service_error`, as before.
* "please go on" is capped at 4 per call. Re-asks of the substantive question are bounded only through the
  empty-turn counter, which questions reset.
* **The completed plan is preserved while confirmation is unresolved:** local tests, replays, and the platform
  targeted check.

## 6. Long input
**Code path:**
* Every brief file is read whole (`build.py` `read_text`) and wrapped in `<document name=…>`. There is no
  truncation in prompt assembly, and the oracle reads the same materials.
* **Silent-loss points found:**
  1. **Undecodable bytes:** `read_text(errors="ignore")` drops non-UTF-8 bytes without a note.
  2. **A second JSON file is not a brief:** a code list delivered as JSON makes the builder exit with "usage".
  3. **No context-limit check:** an input beyond the model's context fails the extraction twice and the build stops.
     There is no partial reading and no false COMPLETE, but also no fallback agent.
  4. **A partial answer after an SDK error mid-stream is returned:** structured output then fails to parse, so it is
     not silent.

**Controlled test:**
* Input: `eval/longinput/long-brief.md`, 290,598 characters, about 73k tokens. It is brief A inside 90 scanned-looking
  facilities sections, with planted rules at the beginning, middle and end; expectations were frozen in `EXPECT.md`.
* **Result: COMPLETE, 273.6 s, $3.18, oracle 22/22 agree. All three planted rules carried:**
  * holiday 2026-10-23;
  * credit-card floor 40% / up_unit / minimum 50, card only, other types keep their floors;
  * `event_changes` refused → `declined_offer` from 2026-11-02.
* Every other brief-A rule is identical to the plain candidate-8 A spec.

## 7. Changes
* **Candidate 8 is unchanged.** One fix was attempted, on branch `claude/keen-fermat-t25udu-splitamount` (`6a9c4fc`):
  * it joins "X hundred (and)" + "Y" across two messages;
  * failing test before, passing after (`tests/test_split_amount.py`), 212 tests pass;
  * engine code +519 bytes (83,996 of 100,000);
  * clean A build COMPLETE (agent `d6be6cbe`, 226 s, $0.86).
* **Platform validation was blocked** by repeated 504s on the chat route (an infrastructure failure, not a result).
  Its read-back chat passed.
* It does **not** cover the digit form "463..." + "51", where it is ambiguous whether "51" is cents or more digits.
* **It stays on its branch, not selected.**

## 8. Platform-retry evidence
`docs/RETRY-EVIDENCE.md`: PUB-12 and PUB-09, with identifiers, timestamps, ledger rows and judge verdicts. It
contains no secrets and no personal data, and nothing has been sent.

## 9. Remaining risks, in order
1. **Two-part numbers** (official customer behaviour): an amount split over messages is lost (words or digits).
   Fix on branch for the words form only, unvalidated on the platform.
2. **A correction with a date** ("Yes… no, Friday does not work") is read back as a proposal for that date.
3. **A repeated question becomes a refusal** after three identical agent lines, even when the brief is silent.
4. **No bound on alternating questions and fragments.**
5. **Silent rules:**
   * the C21/C22 class (correct fields, missing engine semantics) is still undetectable at build time;
   * the multi-product close rule is unverified;
   * weekend call days are skipped by the self-test.
6. **Long input:** non-UTF-8 bytes dropped silently; a second JSON file rejected; no fallback if the context is
   exceeded.
7. **Platform retries** can fail correct runs.

**Not tested:**
* other customer styles on candidate 8;
* weekend or holiday call dates on the platform;
* a brief silent on non-answers, on the platform;
* PDF or scanned inputs.

**This small synthetic set does not predict the final score.**
