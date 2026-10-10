Before writing the spec, list every rule the brief states. Then check that a spec field carries each one, with the exact arithmetic and counting the brief uses.

Pitfalls seen in past specs:

1. Rounding and minimums. Copy each rounding instruction literally:
   - Say which direction (up or down), to what unit (whole currency unit or cent), and when it happens.
   - "Rounded down to the whole unit" means no cents in the result.
   - "Already whole" means no further rounding.
   - Apply the order the brief gives: compute, then round, then apply the floor or minimum, then any cap. For example, "never less than X; if the debt is below X, the full debt" must appear as an explicit clamp.
   - Every place an amount is derived from the floor must use the clamped floor.
2. Comparisons inside the ladder. If the brief says "if the floor is higher, propose the floor instead", write it as max(derived amount, floor). Do this after rounding.
3. What counts toward attempt totals. If an opening ask or first demand "counts as attempt 1":
   - Proposals that follow = total − 1.
   - The offers list holds only the follow-on proposals. Never repeat the opening ask in it, and never offer it again dated today.
   - Watch for any rule that forbids repeating an identical offer.
4. Dates:
   - "Nth business day after today" never includes today.
   - Note any per-product or per-band changes to the latest date.
   - "Deadline" or "latest date" means the band's or product's value, not a generic one.
5. Overrides. Exceptions and later clauses (e.g. "is now…", product-specific notes, footnotes) take precedence over the general table. Search for them before you finalise.

Before finalising, run each rule through one or two sample cases by hand. Include a borderline case near every threshold: below the minimum, an exactly whole amount, and band edges.