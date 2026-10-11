# Ferncliff Lending: collections pack for the phone agent

Ferncliff Lending Ltd is fictional. All customers, balances and dates are synthetic. Amounts are in pounds (GBP).
The pack has four parts, pasted as received. **Order of authority:** the memo FL-OPS-26-11 (part 4) wins over
everything else; the policy extract (part 2) and the code list (part 3) win over the email (part 1). Where the memo
gives a start date, the earlier text still applies to calls before that date.

---

## Part 1. Email

> **From:** Dana Whitcombe (Collections Ops) **To:** Voice project **Date:** 5 Oct 2026
> **Subject:** RE: RE: what the bot needs to know
>
> Hi all, quick brain dump before the policy people send the official bits. Customers can have an overdraft, a
> credit card and a personal loan with us, sometimes all three. We always deal with the overdraft first, then the
> card, then the loan. Don't follow whatever order the system spits them out in, the agents never do.
> Security is postcode and then year of birth, same as the branches. I think they get three goes? Check the policy.
> If someone tells you they're struggling (lost job, illness, can't afford food, that kind of thing) please don't
> try to squeeze a payment out of them, put them straight through to the Care team.
> Restructuring / payment plan requests go to the Plans desk. Anybody who just wants a person goes to General.
> Cheers, Dana. PS the loan team says their floor is "the monthly instalment, full stop" — not quite, see policy.

---

## Part 2. Policy extract COL-POL-07 (version 4, issued 1 Sep 2026)

**2.1 Identity.** Ask for the postcode first, then the year of birth. Send the postcode in capital letters with
exactly one space before the last three characters (for example `LS6 2QT`). Send the year of birth as four digits.
The identity check has failed at the second wrong answer in total, across both questions. Nothing about the
account may be discussed before both answers are verified.

**2.2 Business days.** Promises may only fall on a business day: Monday to Friday, except Ferncliff closure days
2026-11-13, 2026-12-24, 2026-12-25, 2026-12-28, 2026-12-31 and 2027-01-01. A promise may be for today if today is a
business day. "The Nth business day after today" never counts today itself.

**2.3 Bands and deadlines.** The band of each product comes from its own `days_overdue`.

| Band | days_overdue | Latest promise date (deadline) | Attempt limit |
|---|---|---|---|
| A | 1 to 20 | the 7th business day after today | 3 |
| B | 21 to 60 | the last business day of the current calendar month | 4 |
| C | 61 or more | the 2nd business day after today | 3 |

Band B: if today is itself the last business day of the month (or later), the deadline is the last business day
of the following month.

**2.4 Floors** (lowest amount that may be accepted for one product):
- Credit card: 15% of the arrears, rounded up to the next whole multiple of £5 (an exact multiple stays as it is),
  with a minimum of £30. The floor is never more than the arrears; if the formula gives more, use the arrears.
- Overdraft: 25% of the arrears, rounded up to the next whole multiple of £10, minimum £50, never more than the arrears.
- Personal loan: the monthly instalment in bands A and B. In band C the floor is the full arrears.

**2.5 The conversation.** State each late product in one sentence, then ask once whether the customer can pay
everything in full today. If not, take the products one at a time in the order overdraft, card, loan. If a
customer has two products of the same type, the one with the larger arrears goes first.

**2.6 Persuasion ladder** (per product). Offer these steps in order until the customer agrees:
1. the full arrears, on the 2nd business day after today;
2. the full arrears, on the deadline;
3. the floor, on the deadline.

Any step whose date is after the product's deadline uses the deadline instead.
Counting: the opening "everything today" question counts as attempt 1 for every product, even though it is asked
only once. Each step offered is one more attempt. A step that would repeat, with the same amount and the same date,
an offer already made for that product is not said out loud, but it **still uses up one attempt**. When the
attempt limit of the band is reached, or the steps run out, the product ends without a promise and gets a refusal note.

**2.7 Customer proposals.** If the customer names an amount and date for a product, accept it when the amount is at
least the floor and the date is a business day no later than the deadline; otherwise explain the limit and go on
with the next step. "It's too much" counts as a refusal of the step on the table.

**2.8 Disputes and "already paid".** These end that product only: write the note and carry on with the remaining
products. For products still to come, the opening question counts as already refused.

**2.9 Hardship.** Transfer to the Care queue at once, whatever has been agreed so far. Agreed promises not yet
recorded are dropped. Write no notes when a call is transferred, for any reason.

**2.10 Read-back.** Read all agreed promises back together and ask for one confirmation, then record one promise
per product. Every product that ends without a promise gets one note.

**2.11 Closing.** At least one promise recorded: `promise_taken`. No promise and every product noted as paid:
`claims_paid`. Otherwise `no_promise` with the reason of the first product (in handling order) whose note is not a
paid note: `refused` or `dispute`. Transfers close as `handed_over` with reason `hardship`, `plans` or `general`.
Identity failure closes as `id_not_passed` / `failed`; refusing the questions, `id_not_passed` / `declined`.

---

## Part 3. Code list for add_note (CL-12)

| Situation | Overdraft | Credit card | Personal loan |
|---|---|---|---|
| refused after ladder | NO-REF | NC-REF | NL-REF |
| dispute | NO-DSP | NC-DSP | NL-DSP |
| says already paid | NO-PD | NC-PD | NL-PD |

System failure on any product (a tool fails twice): `N-SYS`.

---

## Part 4. Memo FL-OPS-26-11

> **Date:** 30 October 2026 **From:** Head of Collections **To:** All collections staff and the voice project
> This memo overrides COL-POL-07 and CL-12 where they differ. Items 1, 2 and 4 apply from today.
>
> 1. Band A deadline is now the 5th business day after today (it was the 7th).
> 2. Closure days: 2026-11-13 is no longer a closure day (the office move is postponed). 2026-11-30 (Monday) is
>    added as a closure day for the year-end systems switch.
> 3. From 18 November 2026 (calls on that day included), the overdraft and credit card dispute codes NO-DSP and
>    NC-DSP are retired and both are replaced by `NX-QRY`. The loan code NL-DSP does not change.
> 4. Overdraft floor: 20% of the arrears instead of 25%. Rounding and minimum are unchanged.
>
> Nothing else in COL-POL-07 changes.
