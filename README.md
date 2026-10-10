# Build the Builder — a compiler for collections phone agents

One command turns a bank's collections brief (clean spec *or* raw mails/memos/code lists) plus its tool API file
into a tested phone agent on Freya:

```bash
python3 builder/build.py <brief.md> [<more brief files>...] <tool_api.json>
# e.g.
python3 builder/build.py kit/build-the-builder/briefs/brief-a.md kit/build-the-builder/tools/openapi.json
python3 builder/build.py kit/build-the-builder/briefs/brief-a.md kit/build-the-builder/briefs/brief-b.md kit/build-the-builder/tools/openapi.json
```

Needs Python 3.10+, `pip install -r requirements.txt` (Claude Agent SDK), a Claude login or `ANTHROPIC_API_KEY`,
and `FREYA_API_KEY` (+ `FREYA_API_URL`). Output: the agent on Freya, `submission/<slot>.workflow.json` (export),
`submission/<slot>.spec.json` (what the builder understood) and `traces/<slot>.log` (the trace). A run takes
about 1–3 minutes.

## The idea: the weak model only listens, code decides

The phone agent runs on a small fixed model and every case must pass 3 runs out of 3. So the builder does **not**
write one big prompt and hope. It compiles the brief into a deterministic state machine and lets the model do
only what models are good at: understanding what the customer said.

```
brief(s) + tool API ──► 1. Claude (Opus) reads them into a typed SPEC      builder/extract.py, builder/spec_doc.md
                          · two independent readings, field-by-field diff,
                            adjudication with quotes, schema/enum validation, repair loop
                        2. local self-test: the in-agent engine is run      builder/selftest.py
                           against synthetic customers derived from the spec
                        3. deterministic compile: spec ──► Freya workflow   builder/compile.py
                        4. dry-run, save+publish, chat smoke test, export   builder/build.py
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

## What changes between briefs

Everything brief-specific lives in the spec: identity questions and their formats, wrong-answer limits, hint
handling, callback window, calendar and holidays, lateness bands with deadline rules, floors (field or
percentage), persuasion ladder, notes, multi-product rules, the outcome/reason/queue/note codes, tool field names
(read from the tool API file) and every spoken line. Nothing from any brief is hard-coded in the builder.
`variants/` holds two extra briefs we wrote to test this (a clean one with renamed fields/codes and three bands,
and a messy mail + policy + overriding memo + code list), with their own tool API files.

## Repository

| Path | |
|---|---|
| `builder/build.py` | the one command |
| `builder/extract.py`, `builder/spec_doc.md`, `builder/claude.py` | brief → spec with Claude |
| `builder/compile.py` | spec → Freya workflow |
| `builder/runtime/` | the code that runs inside the phone agent (engine + calendar/parsing) |
| `builder/selftest.py`, `builder/trace.py` | self-tests and the trace |
| `tests/` | local tests: the engine against the 13 public cases with a fake bank, parsing tests |
| `specs/` | hand-written reference specs for briefs A and B (test oracles only, never read by the builder) |
| `kit/build-the-builder/` | the official starter kit (Freya client, scorer, briefs, docs) |
| `probes/` | scripts used to learn the platform's behaviour |
| `submission/`, `traces/` | builder outputs |
