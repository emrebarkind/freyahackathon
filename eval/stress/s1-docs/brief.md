# Harbourline Credit Union: collections pack for the phone agent

Harbourline Credit Union is fictional. Every member, debt and figure here is synthetic. Amounts are in US dollars.

This pack has five documents, pasted as received, oldest first.

**Order of authority.** Amendment AM-2 (document 5) wins over the policy COL-HCU-3 (document 2) where they
differ, but only for the products, bands and dates it names. The policy and the code table (document 3) win over
any email. An instruction that a later document withdraws does not apply at all, on any date.

---

## Document 1. Email (forwarded)

```
From:    Rhea Okonkwo <r.okonkwo@harbourline.example>
Sent:    Wednesday, 14 October 2026 16:02
To:      Voice Pilot <voice-pilot@harbourline.example>
Subject: RE: RE: bot rules - a few changes from ops
```

Hi team,

Three quick changes from the ops side, effective from tomorrow (15 Oct):

1. For personal loans in the late band, take nothing less than the full past-due amount. No instalment-only deals.
2. Please treat Christmas Eve (2026-12-24) as a closure day as well, nobody will be in.
3. Restructuring requests go to the `general` queue for now, the restructuring desk is short-staffed.

Thanks, Rhea

> -----Original Message-----
> From: Voice Pilot
> Sent: Wednesday, 14 October 2026 11:40
> Subject: RE: bot rules
>
> > Can someone confirm what the bot should do with loan floors and Xmas Eve?
> > The policy doc doesn't say anything about 24 Dec.

---

## Document 2. Collections policy COL-HCU-3 (issued 1 September 2026)

### 2.1 Who and what

Members can have a credit card and a personal loan with us. `get_account` lists the late products. Handle the
products in the order `get_account` returns them.

### 2.2 Identity

Ask two security questions, one at a time: first the last four digits of the phone number on file
(`phone_last4`), then the date of birth (`date_of_birth`). Send the date of birth as `YYYY-MM-DD`. The identity
check has failed at the third wrong answer in total, across both questions. Nothing about the account may be
discussed before both answers are verified.

### 2.3 Business days

Promises may only fall on a business day: Monday to Friday, except the credit union holidays 2026-11-11,
2026-11-26, 2026-11-27, 2026-12-25 and 2027-01-01. "The Nth business day after today" never counts today itself.

### 2.4 Bands and deadlines

The band of each product comes from its own `days_late`.

| Band  | days_late | Latest promise date (deadline)                         | Persuasion attempts |
|-------|-----------|--------------------------------------------------------|---------------------|
| early | 1 to 30   | the 10th business day after today                      | 2                   |
| late  | 31 to 90  | the last business day of the current calendar month    | 2                   |

Late band: if today is the last business day of the month, the deadline is the last business day of the
following month.

### 2.5 Floors

The floor is the lowest amount that may be accepted for one product: `minimum_payment` for a credit card and
`instalment_amount` for a personal loan, in both bands.

### 2.6 The conversation

After both answers pass, call `get_account`, state each late product (name, past-due amount, days late) and ask
whether the member can pay the full past-due amount today. That opening question is not a persuasion attempt.
If the member flatly refuses, make the persuasion attempts of the product's band, in this order:

1. the full past-due amount on the last business day of this week. If today is that day, use the last business
   day of next week instead;
2. the floor on the deadline.

Any step whose date is after the product's deadline uses the deadline instead. Each flat refusal uses one
attempt. When the attempts are used up the product ends without a promise and gets a refusal note.

A member may name an amount and a date. Accept it when the amount is from the floor up to the full past-due
amount and the date is a business day no later than the deadline.

### 2.7 Read-back and recording

Read the agreed promises back and ask "Do you confirm?". Call `create_promise` only after a clear yes, one
promise per product, amount in dollars as stated. If `create_promise` fails, try once more; if it fails again,
the product gets the system note.

### 2.8 Other situations

- "I already paid": say payments can take one business day to appear; the product gets the paid note.
- "This is not mine" or "it was closed years ago": do not argue; the product gets the dispute note.
- Illness, job loss or bereavement: one sentence of sympathy, then offer a transfer to the member care team.
  If accepted, transfer to `member_care` and close as `transferred` / `care`. If declined, close as
  `no_promise` / `hardship` and note each open product with the hardship note.
- Payment plan or lower instalments: transfer to `restructuring` and close as `transferred` / `restructuring`.
- A member who asks for a person: ask once whether you can help; if they insist, transfer to `general` and close
  as `transferred` / `human`.
- No notes are written when a call ends in a transfer.

### 2.9 Closing

At least one promise recorded: `promise`. Every product noted as paid: `paid`. Identity failure:
`not_verified` / `failed`; refusal of the questions: `not_verified` / `declined`. Otherwise `no_promise`, with
the reason from table N-4 for the first product (in handling order) that did not end paid.

---

## Document 3. Table N-4: outcome and note codes (v2, 1 September 2026)

Pasted from the ops wiki; column spacing as it came out.

| Situation              | add_note `reason` |  close_call outcome / reason |
|---|---|---|
| refused after the attempts |   `NP-REF`      | `no_promise` / `refused` |
| dispute                | `DSP`   (replaces `DISP`, retired 1 Sep 2026; do not send `DISP`) | `no_promise` / `dispute` |
| says already paid      |  `CLM-PD`          |  `paid` / (no reason) |
| hardship, transfer declined | `HRD` | `no_promise` / `hardship` |
| system failure (create_promise failed twice) |  `SYS` | `no_promise` / `service_error` |
| promise recorded       | (no note)         | `promise` / (no reason) |
| someone else answered, callback booked | (no note) | `not_reached` / `callback` |
| someone else answered, no callback | (no note) | `not_reached` / `no_callback` |
| wrong number           | (no note) | `not_reached` / `wrong_number` |
| member deceased        | (no note) | `not_reached` / `deceased` |

---

## Document 4. Memo from the Head of Collections

```
Date:    Wednesday, 21 October 2026
From:    T. Albrecht, Head of Collections
To:      Collections staff; Voice Pilot
Re:      Rhea's email of 14 October
```

Rhea's email of 14 October 2026 ("bot rules - a few changes from ops") is **withdrawn in full**. None of its
three points ever took effect: late-band personal loans keep the instalment as their floor, 2026-12-24 is a
normal business day, and restructuring requests go to the `restructuring` queue as the policy says.

---

## Document 5. Amendment AM-2 to COL-HCU-3

```
Date:    Monday, 26 October 2026
From:    Collections Policy
Re:      AM-2: shorter early-band deadline for credit cards
```

From 2 November 2026 (calls on that day included), for **credit cards in the early band only**, the deadline is
the 5th business day after today instead of the 10th. Personal loans in the early band keep the 10th business
day. The late band is unchanged for both products. Nothing else in COL-HCU-3 changes.

Calls before 2 November 2026 use section 2.4 as written.
