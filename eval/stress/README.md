# Stress packages (synthetic)

Created 2026-10-11, before any builder run on them. Three small stress-test packages for the brief -> phone
collections agent builder, each with `brief.md` and `openapi.json` (kit tool names kept; fields/enums changed):

- `s1-docs`  - document interpretation: policy + scoped, dated amendment + withdrawn email instruction + code table, with formatting noise.
- `s2-money` - API and money: renamed request/response fields, integer-cents API vs dollar brief, floor rounding boundaries, product-specific floors and deadlines.
- `s3-conv`  - conversation state: 2-3 products per customer, product order, refusals, partial answers, corrections and confirmation (conversation checks).

The answer keys are NOT in this tree. They live in `eval/stress-keys/<name>/key.json` (CHECKS.md format) with a
short `NOTES.md` per package. Keep them out of anything the builder reads.
