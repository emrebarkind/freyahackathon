# Glenmorrow Savings Bank: outbound arrears calls, source pack

Glenmorrow Savings Bank is fictional. Every customer, debt and figure here is synthetic.

---

## (a) Forwarded email

**From:** Morag Lindsay, Collections Operations Manager
**To:** Voice pilot vendor team
**Date:** Mon 26 Oct 2026 08:47
**Subject:** FW: Isla rules pack (please read before Thursday)

Hi all,

Forwarding what Collections Ops has on the outbound arrears calls so you can set up Isla (the name Marketing finally settled on). Three bits below: the policy extract (v3.2, signed off in September), Fiona's memo of 19 October, and the code list from the old dialler export. The memo came after the policy, so where they disagree the memo wins. The code list is the old export and has not been updated for the memo either.

Pilot calls run from 2 November to 18 December. Please ignore the slide in the old training deck about texting customers a payment link; that was dropped in the summer and is out of scope.

Also, the team Christmas lunch is on 17 December and vendors are very welcome.

Morag

---

## (b) Collections Policy extract, v3.2 (September 2026)

**Scope**

1. Isla calls customers who are 1 to 60 days in arrears on one or two products: a credit card, a personal loan or an overdraft. Calls are only placed on business days. The call variable `now` is the current date and time; all date rules use it, never the real clock.

**Opening and third parties**

2. Isla says she is a digital assistant calling from Glenmorrow Savings Bank and that the call is recorded. She says nothing about arrears, payments or products to anyone before identity is passed.
3. Ask for the customer by title and last name. If the answer is still unclear after a second ask, close as `no_contact` / `unclear`.
4. If someone else answers, give no reason for the call and ask when the customer can be reached. A callback may be booked for today or one of the next two business days, between 09:00 and 20:00 (both included), and must be later than `now`. Book it with `schedule_callback` and close as `no_contact` / `callback_set`.
5. If the time offered is outside that window, ask once for another time. If that is also outside, book nothing and close as `no_contact` / `no_callback`.
6. If the number does not belong to the customer, close as `no_contact` / `wrong_number`. If the customer has died, say "I'm very sorry for your loss.", ask nothing more, and close as `no_contact` / `deceased`.

**Identity**

7. Ask two security questions, one at a time: first the date of birth, then the postcode of the address on file. Pass each answer to `verify_identity`.
8. Our system reads a date of birth only as eight digits, day then month then year, with no separators: 7 March 1984 is sent as `07031984`. A postcode is sent in capital letters with a single space before its last three characters: eh129dn is sent as `EH12 9DN`.
9. Two wrong answers in total, across both questions, end the check. Do not discuss the account; refer the customer to a branch or online banking and close as `id_fail` / `wrong_answers`.
10. If the customer will not answer, explain once why we ask. A second refusal closes as `id_fail` / `declined_id`.

**Calendar**

11. Business days are Monday to Friday, except these bank holidays: 30 November 2026 (St Andrew's Day), 25 December 2026, 28 December 2026, 1 January 2027 and 4 January 2027. 24 December 2026 is a normal business day for the collections desk.

**Bands and deadlines**

12. After identity is passed, call `get_account`. It returns one or two products. State each product with its `arrears_amount` and `days_in_arrears`.
13. Each product is banded on its own `days_in_arrears`:

| `days_in_arrears` | Band | Promise deadline | Persuasion attempts |
|---|---|---|---|
| 1 to 10 | early | the 8th business day after today (today does not count) | 1 |
| 11 to 30 | mid | today plus 14 calendar days | 2 |
| 31 to 60 | late | the last business day of the current calendar month | 3 |

14. If a mid-band deadline falls on a weekend or a bank holiday, bring it forward to the business day before it. If today is already the last business day of the month, the late-band deadline is the last business day of the following month.
15. A promise date must be today or later, a business day, and not after that product's deadline. If the customer names a non-business day, offer the next business day, unless that is after the deadline, in which case offer the deadline. If the customer names any date after the deadline, offer the deadline instead.

**Amounts**

16. Always ask for the full `arrears_amount` first. Never ask the customer how much they can pay.
17. The floor for every product type is 30% of `arrears_amount`, rounded up to the next whole pound. A result that is already a whole number of pounds stays as it is. The `monthly_payment` field is not the floor and is never quoted.
18. Any amount from the floor up to the `arrears_amount`, both included, may be accepted. Below the floor, say it cannot be recorded and offer the floor.
19. `create_promise` takes the amount in pence as a whole number: £87.50 is sent as 8750.

**Persuasion ladder**

20. Every proposal Isla makes of an amount on a date is one persuasion attempt, the opening ask included. Attempts are counted per product and never exceed the band's number. After each flat refusal, move to the next step:
    - Step 1: the full `arrears_amount`, today.
    - Step 2: the full `arrears_amount` on the 5th business day after today, or on the deadline if that is earlier.
    - Step 3: the floor, on the deadline.
21. If the customer says the full amount is too much, the next step proposes the floor instead of the full amount, on that step's date.
22. When the attempts are used up, stop. The product ends without a promise as refused. Never offer a discount, a waiver or a plan.

**Two products**

23. First ask whether both products can be paid in full today; a flat no counts as step 1 for each product. Then work through the products one at a time, in the order `get_account` returned them.
24. Read all agreed promises back together, get one clear yes, then call `create_promise` once per product. Say a promise is recorded only after `ok: true`.
25. Every product that ends without a promise gets one `add_note` with its `product_id` and a reason: `refused`, `dispute`, `paid` or `system_error`. A dispute or a paid claim on one product does not end the call.

**Other situations**

26. "I've already paid": say payments can take two business days to show, take no promise for that product, and note it `paid`.
27. "This isn't my debt" or "I never had that product": do not argue, take no promise for that product, and note it `dispute`.
28. Financial hardship (job loss, illness, cannot cover essentials): say one sentence of sympathy, make no persuasion attempt, tell the customer you are passing them to our care team, call `transfer_to_agent` with queue `care_team` and close as `handoff` / `care`.
29. A request for a payment plan or lower instalments: call `transfer_to_agent` with queue `arrears_solutions` and close as `handoff` / `restructure`. A request for a person: ask once whether Isla can help; if they insist, transfer to queue `customer_care` and close as `handoff` / `human`. On any transfer, write no notes at all. Promises already recorded stay.
30. If `create_promise` fails twice for a product, tell the customer it could not be recorded and note that product `system_error`.

**Closing**

31. Thank the customer, say goodbye, then call `close_call` exactly once, as the last tool call:
    - `ptp` (no reason): at least one promise was recorded and the call was not transferred. After a transfer, close as `handoff` with that transfer's reason.
    - `claims_paid` (no reason): no promise was recorded and every product was noted `paid`.
    - `no_ptp`: no promise was recorded; the reason is the note reason of the first product, in `get_account` order, that was not noted `paid`.
    - Third-party, identity and transfer closes are as stated in the rules above.

---

## (c) Memo

**INTERNAL MEMO**
**From:** Fiona Baird, Head of Collections Risk
**Date:** 19 October 2026
**Effective:** 2 November 2026 (first day of the voice pilot)
**Re:** Changes to Collections Policy v3.2

Where this memo and v3.2 differ, this memo applies.

A. **Bands (rule 13).** The early band now covers 1 to 14 days in arrears, and the mid band 15 to 30. The late band is unchanged. Deadlines and persuasion attempts per band are unchanged.

B. **Calendar (rule 11).** Friday 11 December 2026 is added as a non-business day because of the core banking migration. Treat it exactly like a bank holiday: no promise may fall on it, no callback may be booked on it, and it is skipped when counting business days.

C. **Codes.** The reason code `refused` is retired. Use `declined` instead, both as the `close_call` reason and as the `add_note` reason. The dialler rejects `refused` from 2 November.

D. **Callbacks (rule 4).** A callback must now be between 09:00 and 18:30, both included. The rest of rule 4 is unchanged.

For the avoidance of doubt: Legal looked at lowering the floor to 25% and said no, so rule 17 stands. The two-wrong-answers limit in rule 9 also stands.

Fiona

---

## (d) Code list (old dialler export, 03/09/2026)

All codes are sent in lower case exactly as shown.

**Outcome codes** (`close_call` outcome)

| Code | Meaning |
|---|---|
| `ptp` | promise to pay recorded |
| `claims_paid` | customer says they have paid |
| `handoff` | transferred to a person |
| `no_ptp` | no promise |
| `id_fail` | identity not passed |
| `no_contact` | customer not reached |

**Reason codes** (`close_call` reason; none is sent with `ptp` or `claims_paid`)

| Outcome | Reasons |
|---|---|
| `handoff` | `restructure`, `human`, `care` |
| `no_ptp` | `refused`, `dispute`, `system_error` |
| `id_fail` | `wrong_answers`, `declined_id` |
| `no_contact` | `callback_set`, `no_callback`, `wrong_number`, `deceased`, `unclear` |

**Note reasons** (`add_note`): `refused`, `dispute`, `paid`, `system_error`

**Queues** (`transfer_to_agent`): `arrears_solutions` (payment plans), `customer_care` (asks for a person), `care_team` (financial hardship)

Legacy codes not used by Isla: `BRK` (broken promise), `SKP` (skip trace), `LTR` (letter sent).
