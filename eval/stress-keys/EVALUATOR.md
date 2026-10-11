# Independent evaluation of the stress answer keys

Evaluator: an independent agent with read-only access. Date: 2026-10-11.
Inputs read: `eval/stress/{s1-docs,s2-money,s3-conv}/{brief.md,openapi.json}`, `eval/stress-keys/*/key.json`,
`eval/packages/CHECKS.md`, `eval/heldout/h2/key.json`, `eval/robust/CHECKS-conversation.md`, and the list-comparison lines of
`eval/score.py`. I did not open builder/, clean-runs, submission/, traces/ or any *.spec.json. I read the NOTES.md files
only after I had worked out every value myself.

Method: I worked out every expected value from the brief and the openapi only. For dates and floors I used Python's
`datetime` and integer-cent arithmetic: N-th business day after today (today never counted), the last business day of
the month and of the week, each package's holiday list, and ceiling rounding in cents to avoid float noise.

## Summary

| Package | Checks | AGREE | DISAGREE | AMBIGUOUS | Source-quote flags (minor) |
|---|---|---|---|---|---|
| s1-docs | 17 | 17 | 0 | 0 | 1 (C4) |
| s2-money | 18 | 18 | 0 | 0 | 2 (C11, C12) |
| s3-conv | 15 | 15 | 0 | 0 | 2 (C11, C12) |
| **Total** | **50** | **50** | **0** | **0** | 5 |

No check is DISAGREE or AMBIGUOUS. Each source-quote flag marks a check where the quoted text leaves out a sentence
needed to compute the value, but that sentence is elsewhere in the same brief. The value is still correct.
Below the tables is a list of rules in the briefs that are ambiguous but that no current check tests.

## s1-docs (Harbourline)

| Check | Type | Key | My value | Verdict | Derivation / note |
|---|---|---|---|---|---|
| C1 | deadline | 2026-11-13 | 2026-11-13 | AGREE | Thu 29 Oct is before AM-2 starts, so §2.4 applies: 10th bd. 11-11 is a holiday: 30,2,3,4,5,6,9,10,12,13. |
| C2 | deadline | 2026-11-09 | 2026-11-09 | AGREE | AM-2 covers calls on 2 Nov: card, early band, 5th bd: 3,4,5,6,9. |
| C3 | deadline | 2026-11-17 | 2026-11-17 | AGREE | AM-2 does not cover early-band loans, so 10th bd. |
| C4 | deadline | 2026-12-31 | 2026-12-31 | AGREE | Mon 30 Nov is the last bd of Nov, so the deadline rolls to the last bd of Dec. Thu 31 Dec is not a holiday in s1. Source flag: the quote leaves out the §2.3 holiday list, which is needed to confirm 12-31. |
| C5 | floor | 310.25 | 310.25 | AGREE | The email is withdrawn in full, so the floor is the instalment. |
| C6 | floor | 45.0 | 45.0 | AGREE | minimum_payment. |
| C7 | business_day | true | true | AGREE | The memo makes 12-24 a normal business day. |
| C8 | business_day | false | false | AGREE | 11-27 is a holiday. |
| C9 | offers | [[298.3,11-06],[38,11-13]] | same | AGREE | Thu 5 Nov: the last bd of this week is Fri 6. The AM-2 deadline is 11-13. |
| C10 | offers | [[880,11-25],[220,11-30]] | same | AGREE | Fri 20 Nov is the last bd of the week, so step 1 uses next week: 26 and 27 Nov are holidays, giving Wed 25. The late-band deadline is Mon 30 Nov. |
| C11 | attempts | 2 | 2 | AGREE | The opening ask is not an attempt. The early band allows 2. |
| C12 | identity_fields | [phone_last4, date_of_birth] | same | AGREE | §2.2. |
| C13 | identity_max_wrong | 3 | 3 | AGREE | §2.2, and the openapi agrees. |
| C14 | note | NP-REF | NP-REF | AGREE | Table N-4. |
| C15 | note | DSP | DSP | AGREE | DISP is retired. The openapi still accepts it, but N-4 says not to send it. |
| C16 | transfer | restructuring | restructuring | AGREE | The email is withdrawn, so §2.8 applies. |
| C17 | close | paid / "" | paid / "" | AGREE | Table N-4. |

## s2-money (Pinecrest)

| Check | Type | Key | My value | Verdict | Derivation / note |
|---|---|---|---|---|---|
| C1 | deadline | 2026-11-17 | 2026-11-17 | AGREE | CARD band 1: 7th bd from Thu 5 Nov, skipping 11-11. |
| C2 | deadline | 2026-11-30 | 2026-11-30 | AGREE | AUTO band 1: 3rd bd from Tue 24 Nov: 25, 27, 30 (26 is a holiday). |
| C3 | deadline | 2027-01-29 | 2027-01-29 | AGREE | Thu 31 Dec is the last bd of Dec, so the deadline is the last bd of Jan. 31 Jan is a Sunday, so Fri 29. |
| C4 | deadline | 2026-12-28 | 2026-12-28 | AGREE | AUTO band 2: 2nd bd: 24, 28. |
| C5 | floor | 50.0 | 50.0 | AGREE | 12% of $412.50 is $49.50, rounded up to $50. |
| C6 | floor | 36.0 | 36.0 | AGREE | 12% of $291.67 is $35.0004, rounded up to $36. |
| C7 | floor | 60.0 | 60.0 | AGREE | 12% of $500 is exactly $60, so it stays. |
| C8 | floor | 28.75 | 28.75 | AGREE | The debt is under $35, so the floor is the whole debt. |
| C9 | floor | 389.0 | 389.0 | AGREE | AUTO band 1: the monthly payment of 38900 cents, in dollars. |
| C10 | floor | 1120.45 | 1120.45 | AGREE | AUTO band 2: the whole overdue amount. |
| C11 | offers | [[412.5,12-31],[50,12-31]] | same | AGREE | Mon 28 Dec: the CARD band 2 deadline is Thu 31 Dec, which is not a holiday in s2. Source flag: the quote leaves out rule 7 (holidays) and the cents-to-dollars rule. |
| C12 | offers | [[1120.45,12-28]] | same | AGREE | Step 2 is the same amount on the same date, so it is skipped (rule 15). Source flag: the quote leaves out the AUTO band-2 deadline calendar (25 Dec is a holiday). |
| C13 | attempts | 1 | 1 | AGREE | Rule 15: a skipped step is not a proposal. |
| C14 | promise_amount | 19483 | 19483 | AGREE | Rule 18. |
| C15 | promise_amount | 123457 | 123457 | AGREE | Exact conversion to cents. |
| C16 | id_answer | "02139" | "02139" | AGREE | Rule 5: the leading zero is kept. |
| C17 | transfer | LOAN_MODS | LOAN_MODS | AGREE | Rule 23. |
| C18 | close | NO_PTP / system | NO_PTP / system | AGREE | Rule 19, assuming no other promise was recorded. That is the natural reading of the single-situation check. |

## s3-conv (Northgate)

| Check | Type | Key | My value | Verdict | Derivation / note |
|---|---|---|---|---|---|
| C1 | deadline | 2026-12-29 | 2026-12-29 | AGREE | Late band, 3rd bd from Tue 22 Dec: 23, 28, 29 (24 and 25 are holidays). |
| C2 | deadline | 2027-01-08 | 2027-01-08 | AGREE | Early band, 7th bd: 29, 30, 4, 5, 6, 7, 8 (31 Dec and 1 Jan are holidays). |
| C3 | floor | 54.0 | 54.0 | AGREE | 25% of 212.40 is 53.10, rounded up to 54. |
| C4 | floor | 25.0 | 25.0 | AGREE | 25% gives 24.01, rounded up to 25. The $25 minimum also gives 25. |
| C5 | floor | 251.0 | 251.0 | AGREE | 25% gives 250.75, rounded up to 251. |
| C6 | offers | [[212.4,11-23],[54,11-23]] | same | AGREE | Early band from Thu 12 Nov: the 7th bd is 11-23. |
| C7 | attempts | 2 | 2 | AGREE | Rule 5 table and rule 8. |
| C8 | identity_fields | [date_of_birth, phone_last4] | same | AGREE | Rule 3. |
| C9 | note | DISPUTED | DISPUTED | AGREE | Rule 12. |
| C10 | transfer | support | support | AGREE | Rule 17. |
| C11 | conversation | promise; cc_302 200@11-16, od_303 54@11-23; pl_301 NO_PAY | same | AGREE | Order is od, cc, pl. For od: no, then yes, giving the floor 54 on 11-23. For cc (late, deadline 11-17): date-only proposal 11-16, with the amount 365.2 taken from the table, agreed at once. For pl: no, no, giving NO_PAY. At the read-back the cc amount is corrected to 200 and the date 11-16 is kept. 200 is at least the floor of 55, so the list is re-read and confirmed. Source flag: the quote leaves out the rule-10 bullet "agreed at once" and the rule-21 close line. |
| C12 | conversation | promise; cc_311 60@11-20, pl_312 600@11-17; od_313 DISPUTED | same | AGREE | od (dispute) is noted DISPUTED, and the opening counts as refused for later products. For cc: 40 is below the floor of 60, so the agent offers 60 on 11-20, and the customer says yes. For pl (late, deadline 11-17): 11-30 is past the deadline, so the agent offers 600 on 11-17, and the customer says yes. Then the read-back is confirmed. Source flag: the quote leaves out the "agreed at once" bullet (minor). |
| C13 | conversation | promise; od_322 300@11-17, od_323 450@11-20, pl_321 510@11-20 | same | AGREE | One date (11-20) for everything. od_322 is late band with deadline 11-17, which is earlier, so it takes 11-17. The others get 11-20, a Friday and a business day. The key lists the promises sorted by id, not in handling order (od_323 first). This is acceptable because CHECKS-conversation.md says "lists in any order" and score.py sorts. As a result, the create_promise order of rule 15 is never checked. |
| C14 | conversation | transferred/support; no promises/notes | same | AGREE | The od offer is agreed but not confirmed. Hardship causes a straight transfer, the unconfirmed promise is dropped, and no notes are written. |
| C15 | conversation | no_promise/refused; cc_341 CLAIMS_PAID, pl_342 NO_PAY | same | AGREE | The card goes first. The first product that did not end paid is pl, which ended refused. |

## Ambiguous rules in the briefs that no current check tests

The current keys do not test any of these. A careful reader could not compute a single answer for them.

**s1-docs**
- §2.4, late band: "if today is the last business day of the month" does not cover a call on a non-business day after
  that day. Example: Sat 31 Oct 2026. Read literally, the deadline is Fri 30 Oct, which is already past. The h2 brief added "(or later)" here; s1 does not.
- §2.6, step 1: "the last business day of this week. If today is that day ..." is undefined for a call on a Saturday or
  Sunday, when this week's last business day has already passed.
- The ladder does not say whether a skipped or repeated step counts. Example: step 1 clamped to the deadline with the
  floor equal to the full amount. s2 and h2 state a rule for this; s1 is silent.

**s2-money**
- Mixed outcomes with no promise are not ranked. Examples: DISPUTED on one account and DECLINED on another, or
  SAYS_PAID on one account and DECLINED on another. Rules 20, 21 and 25 each give a close, but nothing says which wins.
  s1 and s3 settle this with "first product in handling order"; s2 does not.
- Rule 17: "Otherwise explain the limit and offer the floor or the deadline". It does not say which one, or whether
  it is both together, for example when the amount is below the floor and the date is also past the deadline.
- Rule 9 has the same weekend gap as s1: the CARD band-2 deadline when today is after the last business day of the month.
- Rule 6: "refuses the questions twice". It is unclear whether one refusal followed by an answer resets the count.

**s3-conv**
- Rule 10 does not say what happens when the amount is below the floor and the date is also past the deadline.
  The two bullets prescribe different counter-offers.
- Rule 2 does not break a tie between two products of the same type with equal `past_due`.
- Rule 11 (one date for everything) does not cover a named date that is not a business day, or is before today.
- Rule 10 does not say whether rejecting a counter-offer uses an attempt or moves the ladder on. Example: after
  "floor on your date", the customer says no.
- Rules 13 and 14 do not cover a plain "no" at the read-back. The NOTES file acknowledges this.
