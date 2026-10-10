# Build the Builder: Hackathon Plan

## Context
Freya × YC "Build the Builder" (first place → YC interview).
- **What we write:** `python3 builder/build.py <brief> <tool_api.json>` turns a brief into a phone agent (a workflow) on Freya, with no manual step.
- **Score:** 60 hidden cases (2 hidden briefs × 30 customers). Each case runs **3 times**, and passes only if all 3 runs pass. No partial credit.
- **One run passes when:**
  - the bank ledger is exactly right (outcome/reason, promise product/amount/date, notes, callbacks, transfers, `close_call` as the last call), **and**
  - a judge model finds the policy and honesty checks satisfied in the transcript.
- **The phone agent runs on a weak model:** `experimental-5` handles dialogue, routing and extraction.
- **The bank API does not enforce the rules.** Holidays, floors and deadlines are entirely the agent's job.
- **Hidden briefs:** one is clean, the other is messy (mail + policy extract + overriding memo + code list). Identity questions, limits, deadlines, outcome table, calendar and tool fields/enums can change. Only the 7 tool names stay fixed.
- **Customer behaviour:** gives numbers in two parts, corrects themselves, chats, asks back, says numbers in words.
- **Limits:**
  - 30 minutes per brief, self-tests included
  - 1 simulation at a time per workspace
  - a trace is mandatory
  - anything from the hidden brief written into code or prompts is forbidden
  - the top 10 are cloned and re-run

The kit is in `kit/build-the-builder/` (briefs, openapi, 13 practice cases, docs, `freya.py`, `run_cases.py`). The old `builder/` skeleton was built for a single-prompt agent and will be reworked.

## Main decision: the weak model only *understands and phrases*; code decides
1. **Rule A: the phone agent's model never sees a bank tool.** Every bank call is an engine-run `api_request` node, with fields baked from variables code computed. This removes:
   - invented product_ids
   - forgotten tool calls
   - silence after a tool result
   - saying "recorded" before the result
2. **Rule B: one state machine.** A Python code node runs after every customer turn and decides the next step: persuasion steps, floor, deadline, product order, counters, outcome/reason. The model gets one instruction, `{{next_say}}`, to say naturally.
3. **Rule C: dates are not extracted as `type:"date"`.** That type uses the real clock, not `now`. Instead we extract the parts (day, month, weekday, relative enum) and resolve them in Python against `now`, applying the brief's own "this/next weekday" rule.

## Builder architecture (3 layers)
1. **Normalize + spec extraction (Claude `claude-opus-5-5`, structured output)**
   - For a messy brief: a normalization pass that applies memo > policy > mail precedence and writes every override to the trace.
   - **Event-based spec schema:** a fixed internal event list (CONFIRMED, THIRD_PARTY_CALLBACK, NO_CALLBACK, WRONG_NUMBER, DECEASED, UNCLEAR, ID_FAILED, ID_DECLINED, PROMISE, PAID, DISPUTE, HARDSHIP_ACCEPT/DECLINE, RESTRUCTURE, HUMAN, REFUSED, SERVICE_ERROR). The spec maps each event to the brief's outcome/reason/queue/note code, its required sentences and its forbidden actions.
   - **Typed modules:**

     | Module | Contents |
     |---|---|
     | identity | Ordered fields, format (date/digits-n/year/alnum), wrong-answer limit and how it is counted, hint semantics, openapi response field map |
     | deadline | Chosen from a fixed set: nth business day, n calendar days, end of month… plus a band table |
     | floor | A product field or a % of past_due |
     | persuasion | A list of steps |
     | calendar | Working days and holidays |
     | multi-product | Rules for customers with several products |
     | special intents | trigger → sentence → event |

   - **Escape hatches:** `custom_python` (Claude writes the function plus asserts from the brief's examples, run locally) and `residual_rules` (verbatim rule text attached to stage prompts).
   - **Reliability:** run the extraction 3 times in parallel and vote field by field. Disagreements go to an adjudicator call that must quote the source. Then a spot-check: "deadline for days_late=X on date Y?" compared with the library's result.
   - **Tool schema:** fields and enums are read from the openapi file automatically. Nothing is typed by hand.
2. **Deterministic compiler (our Python): spec → workflow JSON.** The generic stage graph:
   - `setup`(code: calendar, windows, sentinels) → `opening`(tts opening + extraction enum) ⇄ `opening_step`(code)
   - third party: `third_party` → `cb_step`(code: window check) → `cb_call`(api: schedule_callback)
   - identity, per field: `id_ask`(extraction + regex) → `id_step`(code: normalise, words→digits, D/M/Y) → `id_call`(api: verify_identity) → `id_eval`(code: route on the response field map)
   - account: `acct`(api: get_account) → `facts`(code: product wording, band, deadline, floor, persuasion plan)
   - negotiation: `disclose`(tts) → `nego`(extraction: reply_kind, date parts, amount) ⇄ `nego_step`(code policy engine → `next_say`)
   - recording: `confirm`(code-built read-back, extract yes/change/no) → `rec_i`(api: create_promise, maxRetries 0) → `rec_eval`(code: 1 retry, then service_error) → `note_i`(api: add_note)
   - closing: `post_lines`(tts: required sentences) → `close_calc`(code: event → outcome/reason) → `bye` → `close`(api: close_call) → `end_call`
   - transfers: engine api nodes. Robot/scam/human are values of the enum, not global nodes, because an `always` self-transition stops global nodes from firing.
   - **Fallback compiler:** if the spec fails validation, build a thin graph from code-computed facts plus the brief text, so we always have something to submit.
3. **Self-test + trace (within 30 min):**
   - **Self-test:** dry-run validate, graph lint (every path reaches end_call, passthrough nodes have `always`), local asserts on the code nodes (the `nego_step` engine run in a local Python simulator with Claude-generated synthetic cases), then 1 smoke simulation or chat-route test.
   - **Trace** (`traces/<brief>.log`): start/end times, every model call (model plus a one-line purpose), workflow/agent id, node and tool counts, test results. API keys are scrubbed.

## Files (new public repo; see "Repo" below)
- `builder/build.py`: CLI, timing, trace, orchestration
- `builder/normalize.py`, `builder/extract.py`: Claude calls (reuses `builder/llm.py`)
- `builder/spec.py`: the event-based spec schema (replaces the current `spec.py`)
- `builder/compile.py`: spec → workflow JSON (node and tool generators, hook and code templates)
- `builder/runtime/*.py`: Python embedded in code nodes (calendar, date resolver, number words, `nego_step`, `id_eval`). It is tested locally and placed into the code nodes as text, with `{{`/`}}` removed.
- `builder/selftest.py`, `builder/trace.py`
- `freya.py`, `tools/run_cases.py`, `tools/score.py`: copied from the kit (`AGENT_LLM` is not changed)
- `tests/`: runtime unit tests (expected dates and amounts for all 13 public cases, plus variant briefs)
- `variants/`: our synthetic hidden-like briefs and openapis (for generalisation tests)
- `submission/`, `traces/`: final outputs

## Schedule (Istanbul time)

| Time | Work |
|---|---|
| **Sat 13:00–15:30** | Set up keys. Run the minimal builder 3 times on A for a baseline. A probe script (chat route + 1 simulation) answers the platform unknowns below. |
| **15:30–20:00** | Hand-write spec_A.json (only as the gold test target for the extractor). Write `runtime/` + the compiler. `nego_step` unit tests on 13 cases. Goal: A ≥ 8/10. |
| **20:00–24:00** | Brief B (product loop, notes, single read-back). Simulations with every `--style`. |
| **Overnight** | `--reps 3` runs back to back (the user starts them, I analyse in the morning). |
| **Sun 09:00–12:00** | Claude extractor + voting: it must reproduce the hand-written specs exactly (field diff). Messy normalisation pass. |
| **12:00–15:00** | 3 variant briefs (different ID fields such as postcode/birth_year/company_number, holidays, bands, codes, enums, a mail+memo version, a changed openapi). End-to-end tests. |
| **15:00–18:00** | Trace, bounded self-test, fallback compiler, `--reps 3` reliability fixes. |
| **18:00–19:45** | Timed full run (A, B, variant, ≤20 min each). Code freeze, submission script. |
| **20:00–22:30** | Hidden briefs open. Run the builder, read the spec and trace. **Generic bug fixes only.** Export, commit. |
| **Before 23:00** | Fill in the form and submit. |

## Platform unknowns to test on day 1
1. Are extracted variables overwritten or kept when nothing is found? Can code clear a variable? Does `is_set` treat `""` as set?
2. Does `on_enter` run every time a node is re-entered? How much latency does a conversation → code → conversation hop add?
3. Can transitions use `{{now}}` in an extraction prompt, or `<node>.total_turns`?
4. Is a tts line on a passthrough node spoken before its pre_action runs (goodbye → close_call order)?
5. Can pre_process_code stop a call? Does post-hook `vars` reach routing in the same turn?
6. Can practice sessions take a custom case body (custom products/identity)? This is critical for self-testing.
7. Does the chat route run code nodes? Can chat + a Claude customer be used for self-tests?
8. Is a `code_exec` tool allowed? Which Python modules are available?
9. Where does a pre_actions result land (`data.*` mapping, `<node>_failure_count` on HTTP 500)?
10. Turn latency and node-turn caps with 12+ nodes.

## Blockers needing action from the user
- **Anthropic API key (BLOCKER):** the builder needs Claude at runtime to read the brief. Get a key from console.anthropic.com and put it in `.env`. Expected cost for the weekend is a few tens of dollars.
- **Ask in the support channel:** in the top-10 re-run, will the organisers use our model key or theirs? If theirs, we provide an environment variable.
- **Freya key + team key:** fill in `env.sh` from the kit's `env.example` (the team key is a made-up secret of 16+ characters).
- **Repo:** the user creates a new public GitHub repo. I add it to the session (`add_repo`) and push there. Until then we develop on `claude/keen-fermat-t25udu`.
- **Overnight:** the user starts the `--reps 3` runs. On Sunday at 20:00 they forward the hidden briefs, and they fill in the form.

## Verification
- `pytest tests/`: runtime engine, expected dates and amounts for 13 public cases plus variants (bands, holidays, this/next weekday, floor, multi-product deadlines)
- `python3 builder/build.py kit/.../brief-a.md kit/.../openapi.json` → dry-run passes, graph lint is clean, the trace is produced, and it finishes in ≤20 min
- `python3 tools/run_cases.py <agent_id> --brief A --reps 3`, then with each `--style`. Targets: A 10/10, B 3/3 (3 reps)
- Extractor test: spec field diff against the hand-written specs = 0. Variant briefs build without errors and their runtime asserts pass
- Final: `freya.export_workflow` → `submission/*.workflow.json`, `traces/*.log` committed with no keys inside
