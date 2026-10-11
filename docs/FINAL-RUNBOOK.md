# Final runbook (prepared 2026-10-11 16:10 UTC)

## Fixed facts (from the published page; the final e-mail overrides them)
* **The case arrives at 17:00 UTC**; the form is due before 20:00 UTC.
* **The page says** two hidden briefs, each with its own tool API file. **Your newer message says** one brand-new case
  that may contain several files. **The e-mail decides the layout.**
* **Per brief:** run the builder, keep everything it prints, submit one phone agent with the trace of the run that
  made it. Do not edit a phone agent after its run.
* **Commit the exported workflow files and the traces.** The organisers load the export into their own workspace.
* **The top ten are cloned at the submitted commit and the builder is re-run.** The run must be reproducible from
  that commit.
* **Time limit:** 30 minutes per builder run, including the builder's own tests. Our earlier measurements were
  170–275 s. That is not a guarantee: watch the START and END lines of each run.

## Before 17:00
1. Freeze the candidate (decided after the candidate-9 A×1 / B×1 check).
2. **Rehearsal from a clean checkout of the frozen commit, with the code unchanged:**
   `scripts/clean_run.sh <commit> rehearsal kit/build-the-builder/briefs/brief-a.md kit/build-the-builder/tools/openapi.json`
3. Check `env.sh` (FREYA_API_KEY, FREYA_API_URL) and model access (one schema call). Never print the values.

## When the files arrive
1. Put the files unchanged under `briefs/` (names as given or `hidden-1.*`). **Do not summarise, retype or clean any
   document.**
2. **Identify the tool API.** The builder takes the JSON file that has `paths` as the OpenAPI document; every other
   file, a JSON code list included, is read as material. Check this by hand too:
   `python3 -c "import json,sys; [print(f, 'paths' in json.load(open(f))) for f in sys.argv[1:]]" briefs/*.json`
3. **Check what test means the e-mail provides** (a practice bank, test customers). Use them if they exist. If not,
   the report must say that validation rests on local evidence (self-test, oracle, spec review).
4. **Run:**
   ```
   set -a; source env.sh; set +a
   scripts/final_run.sh hidden-1 briefs/<files...>
   ```
   This equals the official `python3 builder/build.py <files...> 2>&1 | tee traces/hidden-1.log`, plus a secret scan
   and an export check.
5. **Read the trace:** the RESULT line, "not carried", unsupported rules, "unspecified" policies, oracle
   disagreements, UTF-8 or binary warnings, and the START/END total seconds.

## A clean trace is not enough: compare the critical obligations
Fill this table from the brief (quote) against `submission/hidden-1.spec.json` and the self-test or simulation
behaviour. **Never edit the spec.** If something is wrong, fix the builder in a general way, re-run, and submit that
run.

| Obligation | Brief says (quote) | Spec / behaviour | OK? |
|---|---|---|---|
| Identity: fields, order, format, wrong-answer limit | | | |
| Amounts and units (API in/out, rounding, floors per product) | | | |
| Dates: bands, deadlines, holidays, non-business-day moves, dated changes | | | |
| Attempts: what counts (opening, non-answer, skipped repeat), limit per band | | | |
| Products: order, per-product rules, one date for all, effects across products | | | |
| Outcome / reason / note / queue codes, including dated code changes | | | |
| Transfers, callbacks, hardship, dispute, paid | | | |
| Required sentences (read-back, SMS line, disclosures) | | | |

## Known gaps to check on the final (candidate 9)
* **Bank record completeness, not only COMPLETE.** For the chosen agent, every promise path must end with
  `close_call` after the SMS sentence and goodbye. The open risk: a customer who hangs up after "Is there anything
  else?" leaves no `close_call` (1 in 60 calls). Check whether the final brief requires or forbids a closing question
  and post-promise requests (like A rule 36 and B rule 10).
* **Document precedence.** If the case has documents that change each other, check in the trace's assumptions that
  the stated precedence (later, amending, "replaces") was applied. Investigate an INCOMPLETE note about it; do not
  ignore it.
* **Stale `_kind`/`_cut` after chained calls** (the platform rejects clearing enum variables): watch transcripts for
  a turn the agent treats as answered when the customer said nothing new.

## Submission (local template: the agent and commit are filled in only after the chosen final run)
```json
{
  "team": "<team name from the kit e-mail>",
  "repo": "https://github.com/emrebarkind/freyahackathon",
  "commit": "<commit that contains the builder used + the committed export and trace>",
  "run_command": "python3 builder/build.py {brief_path} {tool_api_path}",
  "workflows": {"hidden-1": "submission/hidden-1.workflow.json"},
  "traces": {"hidden-1": "traces/hidden-1.log"}
}
```

**For each chosen run, record together:**
* the builder commit;
* the agent id and workflow id (from the trace);
* `submission/<slot>.workflow.json` and its sha256;
* `traces/<slot>.log` and `traces/<slot>.trace.log` with their sha256.

**Re-submission:** check the e-mail for whether a later form replaces an earlier one. Target 19:00 UTC; submit
earlier if the last verified output is ready.

## Rollback
* **Candidate 8 (`9cb2300`)** is the rollback.
* **If candidate 9 regresses,** first separate the cause. Candidate 8 has known defects of its own. If a small,
  verifiable fix exists, consider it; if the fix cannot be verified, go back to candidate 8.
