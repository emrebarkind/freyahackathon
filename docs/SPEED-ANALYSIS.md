# Speed analysis (2026-10-11, candidate 9 `cbe10e8`)

## Build (the 30-minute limit and the "shorter build time" tie-break)
Measured from the traces of the clean builds:

| Step | cand8-a | cand8-ab | long input (73k tokens) | cand9b-a |
|---|---|---|---|---|
| spec reading ∥ oracle reading (2 model calls, parallel) | 105 s | 105 s | 224 s | — |
| audit of high-risk fields (1 model call, after the reading) | 55 s | 62 s | 48 s | — |
| local checks + self-test (14 scenarios) | 1 s | 1 s | 1 s | 1 s |
| compile + validate + publish | 2 s | 2 s | — | — |
| chat smoke test on Freya | 6 s | 9 s | — | — |
| export | 1 s | 1 s | — | — |
| **total** | **170 s, $1.00** | **181 s, $1.04** | **274 s, $3.18** (no deploy) | **180 s, $0.80** |

* **About 97% of build time is model time.** The code around it (parsing, validation, compile, self-test) costs
  about 1 s.
* **Repair rounds:** none ran in these builds. Each one adds about one model call (60–100 s). The budget caps them
  (`Budget(REPAIRS, REPAIR_SECONDS)`).
* **No extra code block slows the build.** The only serial model call that is not essential to correctness is the
  audit, on the critical path after the reading.

## Phone agent at run time (customer patience, max call duration 430 s)
From `scripts/latency.py` on candidate-7 simulations:
* **Customer message → first node entry: 85–91% of a turn**, median 6–19 s by run. This is the platform's
  extraction and routing model plus its queue; the records cannot split the two.
* **Engine code node: 4–12%** (0.5–1.4 s on the platform). Locally the same code takes 47 ms per turn (decode
  10 ms + exec 37 ms), so almost all of it is the platform's sandbox start, not our code.
* **Bank API: 1–7%.**
* **Reply: about 0** (TTS text is fixed by the engine).

## Ways to go faster, with risk
| Lever | Expected gain | Risk | Status |
|---|---|---|---|
| `truncation_strategy: keep_recent` (window about 8–10) on the talk nodes. Today the default `keep_all` sends the whole history to the extraction model every turn | Shorter extraction prompts late in long (talkative) calls, where turns reached 20–27 s | Extraction loses older context. The engine keeps all state, so the latest agent line plus the reply should suffice | **Not tested.** Needs one platform A/B on talkative runs |
| Fewer or shorter extraction fields per talk node (7–9 today; `*_text` copies the whole message) | Fewer output tokens per turn | `*_text` feeds cut detection, rejected-day and amount-piece logic. Removing it breaks the fixes | Do not remove `*_text`; descriptions could be shortened |
| Audit call at effort "medium", or skipped when the oracle agrees fully | −25 to −55 s per build (about −15 to −30%) | The audit catches unsupported policy values; skipping it loses that check | Not tested; quality risk |
| Extraction at effort "medium" | Maybe −40 s | Quality of the main reading | Not recommended before the final |
| Smaller engine code (strip unused paths) | <0.1 s per turn | Breakage | Not worth it |

## Score for this hackathon (our judgement, not a measurement against other teams)
* **Build speed: 8/10.** 170–180 s against a 1,800 s limit, 3 model calls, about $1 per brief. Long inputs scale to
  about 275 s. The tie-break position against other teams is unknown.
* **Run-time speed: 5/10.** Turns are dominated by the platform's model (6–19 s median, 27 s worst). Customers hung
  up in slow runs. The one lever we control (history truncation) is untested.
* **Overall readiness on speed: 6.5/10.** The build is comfortably inside the limit. The run-time risk is
  platform-side and only partly in our hands.
