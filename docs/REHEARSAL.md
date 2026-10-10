# Clean-clone rehearsal (10 Oct 2026)

Fresh clone of the public repo into an empty directory, a new virtualenv with only `requirements.txt`, keys passed as
environment variables (no local state files), then the official command.

| Step | Result |
|---|---|
| `git clone` | 1 s |
| `python3 -m venv` + `pip install -r requirements.txt` | 12 s |
| `pytest tests` in the clone (`requirements-dev.txt` added) | 102 passed |
| `build.py rehearsal/brief-f.md rehearsal/brief-f.openapi.json` (unseen messy brief, renamed tool API) | 97 s, 2 model calls, readings agree, structural 0 / tool API 0, self-test 13/13, repair budget 0/3, deployed, exported, no secret in the trace |
| `build.py kit/.../brief-a.md kit/.../openapi.json` | 212 s, deployed, exported |
| Practice customers on the agent built from the clean clone (`run_cases.py --brief A`) | 10 / 10 |

The chat smoke test reported 503 from the platform's chat endpoint during the whole window (the same on older
workflows); it is informative only and does not gate the build.

Values the builder extracted from brief F were graded field by field against an answer key written by two
independent readers: every value matched. Structural validity alone (the Pydantic model) does not show that values
match a brief; that is what the two readings, the adjudication and this key comparison measure.
