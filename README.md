# Build the Builder — a compiler for collections phone agents

One command turns a bank's collections brief (clean spec *or* raw mails/memos/code lists) plus its tool API file
into a tested phone agent on Freya:

```bash
python3 builder/build.py <brief.md> [<more brief files>...] <tool_api.json>
# e.g.
python3 builder/build.py kit/build-the-builder/briefs/brief-a.md kit/build-the-builder/tools/openapi.json
python3 builder/build.py kit/build-the-builder/briefs/brief-a.md kit/build-the-builder/briefs/brief-b.md kit/build-the-builder/tools/openapi.json
```

Needs Python 3.10+, `pip install -r requirements.txt` (Claude Agent SDK, Pydantic), a Claude login or
`ANTHROPIC_API_KEY` (the builder's own model calls), and `FREYA_API_KEY` (+ `FREYA_API_URL`, default staging).
`FREYA_BANK_TEAM_KEY` is only for the practice bank (`run_cases.py`), not for a build. Output: the agent on Freya,
`submission/<slot>.workflow.json` (export), `submission/<slot>.spec.json` (what the builder understood) and
`traces/<slot>.trace.log` (the trace; everything is also printed, so `2>&1 | tee traces/<slot>.log` works too).
The slot is the brief's file name (`hidden-1.md` -> `hidden-1`); the same slot updates the same workflow in place.
A run takes about 3 minutes and about $1 of model calls (measured: docs/EXPERIMENTS.md, traces/rehearsal-p2.*).

## Final run (hidden briefs)

The organisers' command, unchanged:

```bash
python3 builder/build.py briefs/hidden-1.md briefs/hidden-1.openapi.json 2>&1 | tee traces/hidden-1.log
```

or the same with checks (output files exist, no key in any trace) and a short summary:

```bash
scripts/final_run.sh hidden-1 briefs/hidden-1.md briefs/hidden-1.openapi.json
```

A messy brief that comes as several files: pass them all before the tool API file. Then commit `traces/hidden-N.*`
and `submission/hidden-N.*` and send the form (`docs/SUBMISSION.md`). No manual step, no edit of the agent after the
run, nothing from a hidden brief written into the builder.

What the run does when the brief is unclear or outside what the engine can do: it never guesses a policy. The
trace lists every assumption (`NOTE assumption:`) and every rule the engine cannot carry out as written
(`NOTE UNSUPPORTED by the engine`), and the build stops before deploying a spec that is still malformed after the repair budget
(3 rounds, none after 15 minutes).

## The idea: the weak model only listens, code decides

The phone agent runs on a small fixed model and every case must pass 3 runs out of 3. So the builder does **not**
write one big prompt and hope. It compiles the brief into a deterministic state machine and lets the model do
only what models are good at: understanding what the customer said.

```
brief(s) + tool API ──► 1. Claude (Opus) reads them into a typed SPEC      builder/extract.py, builder/spec_doc.md
                          · one reading, then a targeted audit of the high-risk fields
                            against the documents (quotes; answers with changes only),
                            validation against the tool API
                            (fields, enums, required fields, placeholders, line roles) and a typed
                            Pydantic model (types, ranges, time/date formats, bands without gaps
                            or overlaps), repair loop
                        2. local self-test: the compiled workflow is walked  builder/selftest.py
                           like the platform walks it (engine runs, request bodies,
                           transitions) against synthetic customers and injected tool
                           failures; failures feed one more Claude repair round
                        3. deterministic compile: spec ──► Freya workflow   builder/compile.py
                        4. dry-run, save+publish, chat smoke test that proves builder/build.py
                           the engine runs on the platform, export
```

The compiled workflow:

```
talk_<stage>  (fixed speech {{say}} + per-stage extraction: intent, side question, verbatim answer/date, amount)
     │ always
     ▼
step (code node: the engine, builder/runtime/engine.py + cal.py, with the spec embedded)
     ├──► talk_<next stage>
     ├──► api_verify / api_account / api_promise / api_note / api_callback / api_transfer   (engine-run bank calls)
     └──► api_close (says goodbye, close_call) ──► end
```

* **The model never calls a bank tool.** Every call is an engine-run node with values computed in code, so there
  are no invented product ids, no forgotten calls, no "recorded" before the bank said `ok`.
* **Dates, deadlines, holidays, floors, persuasion attempts, product order, retries and the outcome table** are
  Python, parameterised by the spec. Relative dates are resolved against the call's `now`, never the real clock.
* **Speech is fixed text from the spec**, written by Claude at build time in the brief's own words (and linted:
  no debt wording before verification, no "recorded" outside the promise confirmation, no unfilled placeholders).
* **Spoken input is parsed in code** (numbers in words, digits in two parts, "twenty-eighth of April nineteen
  ninety-three", corrections), with the extractor's own normalisation as a fallback.
* **Compound turns** ("Friday works — are you a robot?") are handled: a separate side-question slot is answered first.
* **Honest about tool results.** "Recorded", "we will call back", "I'm transferring you" are spoken only after the
  bank confirmed the call (success flag read from the tool API file). Every write is retried once; when one of several
  promises fails, the agent says which product was recorded and which was not.
* **Planned chains, little silence.** Each code run costs seconds on the platform, and a silent agent gets hung up on.
  When bank writes follow each other (three promises then "Your promises are recorded…", or notes then the close),
  the engine plans the whole sequence assuming success, and the workflow walks it with deterministic transitions
  (`<node> succeeded AND plan_<node> == next`). Any failure drops back to the code node, which rebuilds the state
  from the real results and continues one call at a time.
* **Fits the sandbox.** The engine is minified at build time (same AST, checked) so code + call variables stay
  under the platform's 128 KB limit for a code run; the compiler refuses to emit an oversized node.

## What changes between briefs

Everything brief-specific lives in the spec: identity questions and their formats (dates in any format the tool
wants, digits, years, postcodes/references spoken letter by letter, names, e-mails), wrong-answer limits (total or per
question), hint and reject values, callback window, calendar and holidays, lateness bands with deadline rules and
their own persuasion ladders, floors (field or percentage), notes (only for outcomes the brief gives a code),
transfers (only where the brief names a queue), multi-product rules, the outcome/reason/queue/note codes, the brief's
own definitions of hardship/dispute/…, call variables, and every spoken line. From the tool API file: request field
names (including one datetime field for callbacks, fixed values for required fields), response field names, success
flags (boolean or status enums), the shape of the account record (list or single object, with or without a type).
Nothing from any brief is hard-coded in the builder.
`variants/` holds three extra briefs we wrote to test this: C (clean, renamed fields/codes, three bands), D (messy
mail + policy + overriding memo + code list) and E (a very different bank: string verify statuses, accounts without
a type and amounts in pence, no transfers, notes only for some outcomes, one datetime callback field).

## Repository

| Path | |
|---|---|
| `builder/build.py` | the one command |
| `builder/extract.py`, `builder/spec_doc.md`, `builder/claude.py` | brief → spec with Claude |
| `builder/compile.py` | spec → Freya workflow |
| `builder/runtime/` | the code that runs inside the phone agent (engine + calendar/parsing) |
| `builder/selftest.py`, `builder/trace.py` | self-tests and the trace |
| `builder/extract_guidance.md` | general reading guidance found by a GEPA search on dev briefs (no bank's values) |
| `eval/` | frozen evaluation packages, promptfoo comparison, GEPA search, contract check (docs/EXPERIMENTS.md) |
| `docs/CANDIDATE.md`, `docs/SUBMISSION.md` | the submission candidate and the form |
| `tests/` | local tests: the engine against the 13 public cases with a fake bank, parsing tests |
| `specs/` | hand-written reference specs for briefs A and B (test oracles only, never read by the builder) |
| `kit/build-the-builder/` | the official starter kit (Freya client, scorer, briefs, docs) |
| `probes/` | scripts used to learn the platform's behaviour |
| `submission/`, `traces/` | builder outputs |

## Known limits (measured, not fixed)

* The pence/cents path of `create_promise` is tested locally and on the compiled workflow, not on the platform:
  practice sessions only take the public cases, whose API is in pounds. On the platform we saw the pounds path
  (`create_promise {"amount": 420, ...}`).
* An integer amount field in the tool API is declared `number` on the workflow node (the node format has no
  integer type); the engine sends whole values there.
* Extraction accuracy was measured on three frozen packages with 2 runs per mode (docs/EXPERIMENTS.md): a small
  sample. The one rule both extractors missed (a brief counting the opening ask as attempt 1) is now a spec option
  (`rules.opening_is_attempt`); on a separate small package (eval/holdout/q1) both runs set it and scored 15/16.
* The ladder date "last business day of this week" moves to next week when today is that day (brief A's rule); a
  brief that instead skips that step is not expressible yet (q1, check C5).
