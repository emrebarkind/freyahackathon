# Submission (send before Sun Oct 11, 20:00 UTC)

Hidden briefs arrive at 17:00 UTC. Steps:

1. Save the files as `briefs/hidden-1.md` + `briefs/hidden-1.openapi.json` (and `hidden-2`). A brief that comes as
   several files: keep each file, pass all of them before the tool API file.
2. Load the keys from the environment (never into the repository): `set -a; source env.sh; set +a`.
3. Run once per brief, no manual step:
   `scripts/final_run.sh hidden-1 briefs/hidden-1.md briefs/hidden-1.openapi.json`
   (same as `python3 builder/build.py briefs/hidden-1.md briefs/hidden-1.openapi.json 2>&1 | tee traces/hidden-1.log`,
   plus a check that the export exists and no key is in a trace).
4. Read the summary: `local checks` line, any `UNSUPPORTED` or `STOP` note, the Freya workflow/agent ids, `END`.
   A run may be repeated; submit the agent of one run with that run's trace. Never edit the agent.
5. Commit `briefs/hidden-*`, `traces/hidden-*`, `submission/hidden-*`; push; put that commit in the form.

Two commits are recorded, and they must agree on the builder:

* **builder source commit**: the commit the final runs were made from (`git rev-parse HEAD` before step 3, with a
  clean working tree; write it into `docs/CANDIDATE.md`).
* **submission commit**: the commit that adds the hidden-brief traces and exports on top of it (the form's `commit`).

Before sending: `git diff <builder source commit> <submission commit> -- builder requirements.txt scripts kit`
must print nothing, so the organisers' clone at the submission commit runs exactly the builder that made the agents.

Form (the fields the hackathon page asks for):

```json
{
  "team": "<team name: from the registration / kit email, not in this repository>",
  "repo": "https://github.com/emrebarkind/freyahackathon",
  "commit": "<commit that holds the hidden-brief traces and exports>",
  "run_command": "python3 builder/build.py {brief_path} {tool_api_path}",
  "workflows": {
    "hidden-1": "submission/hidden-1.workflow.json",
    "hidden-2": "submission/hidden-2.workflow.json"
  },
  "traces": {
    "hidden-1": "traces/hidden-1.log",
    "hidden-2": "traces/hidden-2.log"
  }
}
```

`traces/hidden-N.log` is everything the run printed; `traces/hidden-N.trace.log` is the builder's own trace (same
content without third-party output). Both hold start/end time, every model call (model + one-line purpose),
the Freya workflow id, agent id, node and call counts, and every test the builder ran on its agent.

## For the organisers' re-run (top ten)

* `git clone <repo> && git checkout <commit> && pip install -r requirements.txt`
* Environment: `FREYA_API_KEY` (+ `FREYA_API_URL` if not staging) and a Claude login or `ANTHROPIC_API_KEY` for the
  builder's own calls (Claude Opus via the Claude Agent SDK, ~$1 per brief). Nothing else; no key is in the repository.
  The hackathon page says teams pay for their builder's model calls and that the top ten are re-run by the
  organisers; it does not say whose model key that re-run uses. Not confirmed: ask in the support channel; if they
  need ours, a key can be passed as `ANTHROPIC_API_KEY` only, never committed.
* `python3 builder/build.py <brief files...> <tool api file>`; a run takes about 3 minutes. It creates one workflow
  per brief file name in the workspace it runs in (updated in place on a re-run) and exports it to `submission/`.
* The extraction is a model reading, so two runs can differ in wording; the policy values are checked against the
  documents (audit with quotes, validation against the tool API, typed model, local self-test) before deploying.

Keys stay in `env.sh` (git-ignored). Every trace is scrubbed of `fak_…` and `sk-ant-…` before it is written, and
`final_run.sh` refuses a trace that still contains one.

## Platform rules of thumb (organisers, 11 Oct)

1. Check the parts one by one: a 504 from `/api/v2/chat/message` does not mean simulations are down.
2. See what runs in the workspace: `python3 scripts/sims.py` (GET /api/v2/simulations?limit=10). Only one
   simulation runs at a time.
3. Never stop `run_cases.py` on our side: the simulation keeps running on Freya and the next test waits for it.
4. A simulation stuck in "running" can be cancelled: `python3 scripts/sims.py cancel <id>`.
5. 5xx answers are retried: `kit/build-the-builder/freya.py` now waits 10 s and tries up to 3 times.
6. No tool call for any customer and a 0 s agent turn is an outage, not our agent: `run_cases.py` reports
   "OUTAGE", waits 5 minutes and repeats the run once. Never "fix" the workflow after such a run.
7. If the build stops with "DEPLOY FAILED (platform)", the extraction is already saved. Rerun the command the trace
   prints (`--spec submission/<slot>.spec.json`): it compiles and deploys the same spec without new model calls.
