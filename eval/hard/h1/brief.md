# Brackenridge Finance: collections voice assistant, source pack

Brackenridge Finance is fictional. Every person, customer, debt and payment here is synthetic.

This is the pack the Brackenridge collections team sent us, pasted as received: a forwarded email thread, an extract from the collections policy, two memos and the code list. Read the documents in date order. A later document overrides an earlier one only on the points it explicitly addresses; everything else in the earlier document stands.

---

## Part A. Forwarded email thread

```
---------- Forwarded message ----------
From:    Moira Lennox <m.lennox@brackenridge.example>  (Head of Collections Operations)
Date:    Mon 19 Oct 2026 09:12
To:      Voice project
Subject: Voice assistant - what you need from us
```

Hi all,

As promised, the pack for the voice build. The policy extract, the two memos (the second one lands next week, I'll forward it) and the code list are further down. A few things are not in the extract because they live in team procedures, so here they are.

Identity. Two security questions, one at a time: date of birth first, then the postcode of the home address. The date of birth goes into the system as eight digits, day then month then year, with no separators, so 7 March 1984 is 07031984. If a customer gives a date only as numbers, read it as day, month, year. The postcode goes in as capital letters with the space removed (eh6 7qr is EH67QR). Hamish will send you the wrong-answer limit.

Callbacks. When someone other than the customer answers, we can book a callback for today or the next business day, and never for a time earlier than the current time. Hamish has the hours.

Failed promises. If create_promise fails, for whatever reason, do NOT try it again. The ledger sometimes records a promise even when the call comes back with an error, and a duplicate sends the customer two direct-debit letters. Note that product with N-SYS and carry on with the rest of the call as normal. The promises that did go through stay.

Thanks, Moira

> ```
> From:    Hamish Doig <h.doig@brackenridge.example>  (Team Leader, Outbound)
> Date:    Tue 20 Oct 2026 16:40
> Subject: RE: Voice assistant - what you need from us
> ```
>
> Numbers as requested:
>
> - Wrong answers: two wrong answers and the identity check has failed.
> - Card floor: 10% of the arrears, rounded up to the next whole £5, minimum £20.
> - Callback window: Monday to Thursday 09:00 to 20:00, Friday 09:00 to 17:00. Both ends included.
>
> Cheers, H
>
> > ```
> > From:    Priya Raman <p.raman@brackenridge.example>  (Credit Risk & Compliance)
> > Date:    Thu 22 Oct 2026 11:05
> > Subject: RE: RE: Voice assistant - what you need from us
> > ```
> >
> > Hamish, some of those are from the 2025 handbook. Corrections below; build to these.
> >
> > - Wrong answers: the third wrong answer ends it, whichever question it was on. A first or second wrong answer may be asked again.
> > - Card floor: 12% of the arrears, not 10%, and the minimum is £25, not £20. The £5 step is right: always round up to the next whole multiple of £5, and a figure that is already a multiple of £5 stays as it is. The minimum applies after rounding. The card floor is never more than the arrears: if the formula gives more than the arrears, the floor is the arrears.
> > - Callback window: Monday to Thursday is right. Friday closes at 16:00, not 17:00 (16:00 itself is fine).
> >
> > Everything else Hamish wrote stands.
> >
> > Priya

---

## Part B. Collections Policy v4, section 7 (extract). Effective 1 October 2026.

7.1 Scope. The assistant calls customers who are 1 to 90 days late on up to three products. There are three product types: credit card (`CARD`), personal loan (`PLOAN`) and motor finance (`MOTOR`). `get_account` returns the late products in the order in which they are to be worked.

7.2 Business days. Business days are Monday to Friday, except Brackenridge holidays: 2026-11-30, 2026-12-25, 2026-12-28, 2027-01-01 and 2027-01-04. Calls are only made on business days. A promise date must be a business day, today or later, and not after that product's deadline.

7.3 Counting. "The Nth business day after today" counts business days after today only. Today is never counted, even when it is a business day.

7.4 Bands. Band, deadline and attempts are set per product, from that product's `days_overdue`. Two products of one customer can have different deadlines.

| Band | `days_overdue` | Deadline | Attempts |
|---|---|---|---|
| 1 | 1 to 14 | the 8th business day after today | 1 |
| 2 | 15 to 44 | the 5th business day after today | 2 |
| 3 | 45 to 90 | the 2nd business day after today | 3 |

7.5 Floors. The floor is the lowest amount the assistant may accept for a product.
(a) `CARD`: the percentage of the arrears set by Credit Risk, with the rounding step and the minimum that Credit Risk sets. Credit Risk notifies the team of these by email.
(b) `PLOAN`: the contractual monthly payment, in every band.
(c) `MOTOR`: the contractual monthly payment in bands 1 and 2. In band 3 the floor is the full arrears.

7.6 Opening ask. State every late product, one sentence each, then ask once whether the customer can pay the full arrears on all of them today. The opening ask is not an attempt. If the customer does not agree, work through the products one by one, in `get_account` order, and do not ask about today again.

7.7 The ladder. For each product, the assistant offers ladder steps in order, one step per attempt, and moves to the next step only after a flat refusal. A flat refusal is a no with no date and no amount. Each flat refusal of a step uses one attempt on the product being discussed. Every product starts at step 1.

- Step 1: the full arrears on the last business day of this week.
- Step 2: the floor on the last business day of this week.
- Step 3: the floor on the deadline.

"This week" is Monday to Sunday of the week containing today. If today is the last business day of this week, steps 1 and 2 use the last business day of next week instead. If a step's date is after the product's deadline, the step uses the deadline. A step that would repeat an offer already made for that product, with the same amount and the same date, is skipped. A skipped step does not use an attempt: go straight to the next step. When the product's attempts are used up, or no steps are left, stop: the product ends without a promise and is noted N-REF.

7.8 "Too much". If the customer says the full amount is too much, that is not a refusal and uses no attempt. Offer the same step again with the floor in place of the full arrears. From then on, every step for that product uses the floor in place of the full arrears. Said in answer to the opening ask, it applies to every product, and each product starts at step 1 with the floor.

7.9 Customer proposals. A date or an amount the customer names is never a refusal and uses no attempt. An answer that names no product is about the product being discussed.
(a) An amount with no date takes the date of the offer on the table (today, for the opening ask). A date with no amount takes the amount of the offer on the table (the full arrears, for the opening ask).
(b) An amount from the floor up to the full arrears, both included, on a valid date, is accepted.
(c) An amount below the floor: say it cannot be recorded and offer the floor on that date.
(d) A weekend day or a holiday that is not after the deadline: offer the next business day.
(e) A date after the deadline: say the latest date you can record is the deadline and offer the deadline, with the amount the customer named (or the amount on the table if they named none). If they refuse it, that is a flat refusal under 7.7.
(f) One date for all products: each product takes that date, except that a product whose deadline is earlier takes its own deadline. Say so in the read-back; no separate yes is needed for it.
(g) An answer about a product other than the one being discussed: handle it for that product under this rule, then repeat the offer that was on the table for the product being discussed. That repetition is not a new step and uses no attempt. When the assistant reaches a product that is already agreed, it moves on.

7.10 Read-back. When every product has been dealt with, read all agreed promises back together and ask for one confirmation. If the customer changes a date or an amount at this point, apply 7.9 to the change and then read everything back again. After a clear yes, call `create_promise` once per agreed product, in `get_account` order.

7.11 Other answers.
(a) "Already paid" on a product: payments can take a business day to show. Note that product N-PAID and continue with the others.
(b) A dispute on a product ("not mine", "closed years ago"): do not argue. Note that product with the dispute note code and continue with the others.
(c) Financial hardship (illness, bereavement, job loss): one sentence of sympathy, then transfer to the Customer Care queue. Do not ask further questions.
(d) A request for a payment plan or reduced payments: transfer to the restructuring queue.
(e) A request for a person: ask once whether you can help. If they insist, transfer to the general queue.
(f) On any transfer: promises already recorded stay; promises agreed but not yet recorded are not recorded; write no notes at all, before or after the transfer.

7.12 Closing. Every call ends with exactly one `close_call`, the last tool call. With at least one promise recorded and no transfer, close as a promise. With no promise recorded: if every product was noted N-PAID, close with the paid outcome and no reason; otherwise close as no promise, with the reason that matches the note of the first product, in `get_account` order, whose note is not N-PAID (N-REF gives REFUSED, N-DISP gives DISPUTE, N-SYS gives SYSTEM). A transfer closes with that transfer's reason, even after a recorded promise.

7.13 Identity and contact. A failed identity check closes as IDFAIL / WRONG; a customer who declines the questions twice closes as IDFAIL / DECLINED. When someone else answers: callback booked, NOCONTACT / CB; no callback booked, NOCONTACT / NOCB; wrong number, NOCONTACT / WRONGNO; customer deceased, NOCONTACT / DECEASED; still unclear who answered after two asks, NOCONTACT / UNCLEAR.

---

## Part C. Memos

### Memo CO-26-14

```
From:  Collections Policy Committee
Date:  21 October 2026
Re:    Motor finance deadlines; ledger migration closures
```

1. Motor finance, band 2: the deadline becomes the 3rd business day after today (it was the 5th). Bands 1 and 3 for motor finance, and all bands for credit cards and personal loans, are unchanged. The number of attempts is unchanged.
2. Ledger migration: 2026-11-27 (Friday) and 2026-12-07 (Monday) are added to the Brackenridge holidays.

### Memo CO-26-15

```
From:  Collections Policy Committee
Date:  28 October 2026
Re:    Amendments to CO-26-14; outcome code change
```

1. Item 2 of CO-26-14 is withdrawn for 2026-12-07 only. The second migration weekend has been moved, and 7 December 2026 is a normal business day. 2026-11-27 remains a Brackenridge holiday.
2. Item 1 of CO-26-14 stands.
3. For calls closed from 2 November 2026, the outcome code PAID is replaced by CLAIMED_PAID. The ledger rejects PAID from that date. No other code changes.

---

## Part D. Collections code list (issue 9, 15 September 2026)

Outcome codes (`close_call` `result`):

| Code | Meaning | Reason codes (`result_reason`) |
|---|---|---|
| PTP | at least one promise recorded | none |
| PAID | every product claimed as already paid | none |
| XFER | call transferred | RESTR (restructuring), HUMAN (asked for a person), CARE (hardship) |
| NOPTP | no promise recorded | REFUSED, DISPUTE, SYSTEM |
| IDFAIL | identity not passed | WRONG, DECLINED |
| NOCONTACT | customer not reached | CB, NOCB, WRONGNO, DECEASED, UNCLEAR |

Note codes (`add_note` `note_code`), one per product that ends without a promise:

| Code | Meaning |
|---|---|
| N-REF | refused after the ladder |
| N-DISP | customer disputes the product |
| N-PAID | customer says already paid |
| N-SYS | promise agreed but the system failed to record it |
| N-HARD | hardship, customer declined Care (human agents only; the assistant transfers instead) |
| N-DSP | dispute (old code). DEPRECATED from 1 September 2026: the ledger still accepts it but reporting drops it. Use N-DISP. |

Queue codes (`transfer_to_agent` `queue_code`):

| Code | Queue |
|---|---|
| Q-RESTR | Restructuring |
| Q-GEN | General enquiries (a person) |
| Q-VULN | Customer Care (hardship and vulnerability) |
