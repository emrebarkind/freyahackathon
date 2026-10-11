# Experiments (Oct 10)

All extraction numbers are on three frozen packages (`eval/packages/p1-p3`, hashes in `FROZEN.md`): written by blind
authors, keys re-derived by a second blind reader (90/90 agree), frozen before the comparison. 30 behaviour checks per
package, scored by running the engine on the extracted spec (`eval/score.py`). 2 runs per mode and package.

## Extraction: two readings + adjudication (A) vs one reading + targeted audit (B) — promptfoo

| round | mode | accuracy | missed rules | seconds | cost |
|---|---|---|---|---|---|
| 1 (old engine, rescored) | A | 0.856 | 2.50 | 256 | $1.30 |
| 1 | B, reading at max effort | 0.894 | 2.00 | 888 | $2.73 |
| 2 (fixed engine) | A | 0.944 | 0.67 | 201 | $1.24 |
| 2 | B, reading at high effort (equal effort) | 0.944 | 0.67 | 187 | $0.83 |
| 3 | A + GEPA guidance | 0.961 | 0.50 | 233 | $1.44 |
| 3 | **B (high) + GEPA guidance — new default** | **0.961** | 0.50 | 209 | **$0.88** |

- At equal effort A and B are equally accurate; B is ~40% cheaper and a little faster. B at max effort was more
  accurate in round 1 only because it thought longer (3x time, 2x cost) — not within the same budget.
- Most of the gain came from the engine, not the extractor: round 1 failures included rules no spec could express.
  Fixed: separate create_promise unit (`promise_scale`), percentage floor rounding (30% of 333.34 gave 100, not 101),
  floors capped at the amount owed, `later_of`/`earlier_of`, per-type deadlines, `roll_if_not_after_today`,
  per-weekday callback windows.
- Remaining miss (both modes): a brief that counts the opening ask as attempt 1 (p2) — GEPA guidance fixed it in half
  of the runs.

## GEPA (reading guidance)

Search on separate dev packages only (`eval/dev/d1-d3`, blind keys, 78/78 second-reader agreement): 21 min, $7.52,
dev score 0.885 -> 0.949 (noisy: the same guidance scored d2 1.0 and 0.81 in different runs). On the frozen packages
0.944 -> 0.961 for both modes. The guidance (`builder/extract_guidance.md`) names no bank, value or code. Kept as the
default; `BUILDER_EXTRACT_GUIDANCE=""` turns it off. Caveat: the dev packages were written after the round-1 failure
analysis, so they cover the same kinds of rule.

## mutmut (narrow, separate branch)

Six critical engine functions (API success, identity limits, date/amount bounds, per-product refusal, callback window):
killed mutants 50% -> 71% after adding `tests/test_success_flags.py` and `tests/test_mutation_gaps.py` (775 mutants).
No engine bug found; the gaps were untested edges (inclusive bounds, spec success flags, identity pass values,
answers-left, unreadable answers). Most remaining survivors are equivalent (`.get(key, default)` variants).

## openapi-core

~330 request bodies from the self-test on 6 contracts, plus 48 seeded faults: `extract.validate` caught 41, openapi-core
38, openapi-core alone 0 (the 7 caught by neither were not violations). Not added. Side note: an `integer` body field is
declared `number` on the node, so the simulator sends `300.0`; what the platform sends is unverified.

## pyinstrument

A local build without model calls takes ~3.5 s (engine minify + LZW ~1.5-2 s, Agent SDK import ~1.3 s). No bottleneck
worth changing; build time is model time.

## Holdout q1: opening ask counted toward the limit (Oct 11)

A new small package (`eval/holdout/q1`, blind author, second reader 16/16 agree, frozen before extraction): four bands
with limits 1-4 proposals, the first ask included, worded differently from p2. Two extractions with the default:
both set `rules.opening_is_attempt`, wrote the brief's totals (1/2/3/4) and a ladder whose step 1 is the opening ask;
15/16 checks each (264-267 s, $1.41-1.44, 3 repair rounds each).
- The miss (C5, both runs) is an engine limit, not a reading: the ladder date "last business day of this week"
  moves to next week when today is that day (brief A's rule). q1 says such a step repeats the opening ask and is
  skipped. Not expressible in the spec today; recorded, not added before the final.
- The repair rounds came from two builder issues, both fixed: a null `identity.date_order` (allowed by the spec doc,
  rejected by the typed model) and an `identity.response.hint` naming a field the API lacks (now dropped, it was
  never read).
