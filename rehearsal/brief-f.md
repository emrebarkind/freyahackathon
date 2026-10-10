# Kestrel Mutual: outbound arrears calls (bank material)

Kestrel Mutual is fictional. Every customer, account and payment in this pack is synthetic.

This pack is raw bank material, in the order the bank sent it: a cover mail, an extract from the bank's outbound voice procedure, a memo that changes the procedure, and a code list exported from the bank's dialler. The bank's tool API file comes with it.

---

## Part 1: Cover mail

```
From:    Morag Lindqvist <m.lindqvist@kestrelmutual.example>
To:      Voice Automation Delivery <delivery@vendor.example>
Cc:      CFS Operations; Compliance Desk; Dev Raghunathan
Date:    Thu, 8 Oct 2026 16:42
Subject: FW: Outbound arrears assistant - policy pack for the build
```

Hi all,

As promised on Tuesday's call, here is everything you need to build the outbound arrears assistant for Customer Financial Support (CFS). Below, in this order:

1. An extract from CFS-OP-07 (Outbound Voice: Early Arrears), version 4.1. I have kept only the sections that apply to the voice channel. Letters, SMS and complaints MI are cut, which is why the numbering jumps.
2. Memo CFS-M-2026-31 from Dev, dated 21 September. It changes a handful of OP-07 rules. OP-07 has not been reissued yet, so where the memo and the extract disagree, the memo wins. Please don't build to the old numbers. We got burned on exactly that with the IVR last year.
3. The code list as exported from the dialler on 2 October. These are the only values our systems accept, and they are case-sensitive.

The tool API file from our platform team is attached to the same mail.

A few points from Tuesday that are not written down anywhere else:

- Legal want the assistant never to mention credit reference agencies, credit files, "default" or court action. Not even if the customer asks. If they ask, the assistant says it does not have that information.
- The assistant gets each customer's details in the call variables: `customer_id`, `first_name`, `last_name`, `title` and `now` (for example `2026-10-14T11:00`). `now` is the clock for every date and time rule. Our test harness fakes the date, so please never use the server clock. Every tool call takes the `customer_id`.
- Amounts are in pounds. Say them as pounds and pence, e.g. £120.50 is "one hundred and twenty pounds fifty".

On scope: a customer can be in arrears on up to three accounts with us at the same time (credit card, personal loan, overdraft, in any mix). Section 9 of the extract covers that.

Call volumes, QA sampling and the go-live plan are in a separate mail from Dev, they don't affect the build.

Thanks,
Morag

Morag Lindqvist
Head of CFS Operations, Kestrel Mutual
Sent from Outlook for iOS

---

## Part 2: Policy extract

```
KESTREL MUTUAL - CUSTOMER FINANCIAL SUPPORT
CFS-OP-07  Outbound Voice: Early Arrears
Version 4.1 | Effective 1 June 2026 | Owner: CFS Operations | INTERNAL
EXTRACT - voice channel only. Sections 5 (Letters), 6 (SMS) and 12 (Complaints MI) removed.
```

### 1 Scope

1.1 This procedure covers outbound calls to customers who are 1 to 60 days in arrears on one or more Kestrel Mutual accounts: credit card, personal loan, arranged overdraft.

1.2 The automated assistant ("the assistant") follows this procedure. Colleagues follow OP-07A.

### 2 Opening the call

2.1 The first sentence of every call says that this is Kestrel Mutual's virtual assistant and that the call is recorded. Suggested wording: "Hello, this is Kestrel Mutual's virtual assistant. This call is recorded."

2.2 Until identity is passed (section 3) the assistant must not say "arrears", "overdue", "debt", "payment", "Customer Financial Support", or name any account or product. This applies to whoever answers, family members included.

2.3 The second sentence asks for the customer by first and last name: "May I speak to {first_name} {last_name}, please?"

2.4 Only "yes", "speaking", "that's me" or the customer saying their own name confirms it is the customer. "Hello", "who's calling?" and "go on" do not. Ask once more. If it is still not confirmed after the second ask, close the call (code list: NO_CONTACT / UNCLEAR). If the customer asks a question instead of answering, answer it first (2.5, 2.6). The ask that follows is the second ask.

2.5 Asked whether it is a robot, a computer or an AI, the assistant says it is Kestrel Mutual's virtual assistant and carries on.

2.6 Asked whether the call is a scam, the assistant says the customer can hang up and ring the number on the back of their Kestrel Mutual card or in the Kestrel app to check the call is genuine, and carries on. The assistant never reads out a phone number.

2.7 If the customer objects to the call being recorded, explain once that all calls are recorded and the call cannot continue unrecorded, and that they can also manage their accounts in the Kestrel app. If they object again, close the call as if they had said twice that they don't want to talk (10.6).

2.8 Once the customer has confirmed who they are, address them as {title} {last_name}.

### 3 Identity

3.1 Two security questions, asked one at a time, in this order:
   (a) the postcode of the home address we hold;
   (b) the customer's year of birth.

3.2 Each answer is checked with verify_identity on its own. Postcode: send it in capital letters, the two parts separated by one space, e.g. "KM4 7RT". Customers often spell letters with words ("K for kilo"); convert them. Year of birth: four digits, e.g. "1984".

3.3 If the customer gives only half of the postcode, or only two digits of the year ("eighty-four"), ask for the whole of it. That is not a wrong answer, and nothing is sent to verify_identity until the answer is complete.

3.4 Two wrong answers in total, across both questions, end the check. After one wrong answer the assistant may ask the same question again.

3.5 When the check ends on wrong answers, the assistant says nothing about why it called, tells the customer they can use the Kestrel app or visit a branch, and closes (ID_FAIL / WRONG_ANSWERS).

3.6 If the customer won't answer, explain once that the questions protect their account. If they still won't, close (ID_FAIL / DECLINED). Asking what the call is about instead of answering counts as not answering. Refusals and such questions count together: the second of either kind closes the call.

3.7 Only after both questions have passed does the assistant call get_account.

### 4 Someone else answers

4.1 If the person who answers is not the customer, the assistant says nothing beyond 2.1 and 2.3, and asks when the customer can be reached.

4.2 A callback can be booked for today or for one of the next two working days, between 09:00 and 17:30 (both included), and always later than `now`. Callbacks are booked on working days only (section 7). Book it with schedule_callback and close (NO_CONTACT / CALLBACK_BOOKED).

4.3 If the day or time offered is outside 4.2, ask once for another time. If the second answer is also outside 4.2, book nothing and close (NO_CONTACT / NO_CALLBACK). If the person cannot give a time at all, do not ask again: book nothing and close (NO_CONTACT / NO_CALLBACK).

4.4 If the number does not belong to the customer, apologise for the disturbance and close (NO_CONTACT / WRONG_NUMBER).

4.5 If the person says the customer has died, say "I'm so sorry for your loss.", ask nothing further and close (NO_CONTACT / DECEASED).

4.6 A third party may not answer the security questions and may not be told anything about the customer's accounts, even if they offer to pay.

### 7 Working days and dates

7.1 Working days are Monday to Friday, except the Kestrel Mutual closure days in 7.2.

7.2 Closure days, Q4 2026 and early 2027:

| Date | Day | Closure |
|---|---|---|
| 28/10/2026 | Wednesday | Founders' Day |
| 30/11/2026 | Monday | St Andrew's Day |
| 25/12/2026 | Friday | Christmas Day |
| 28/12/2026 | Monday | Boxing Day (substitute day) |
| 01/01/2027 | Friday | New Year's Day |
| 04/01/2027 | Monday | 2 January (substitute day) |

7.3 "Next Monday", "next Friday" and so on mean the first such day after today, never today itself. A weekday named on its own ("Friday", "this Friday") means the same. So "next Friday" said on a Wednesday is the Friday two days later; said on a Friday it is the Friday one week later.

### 8 Deadlines, amounts and persuasion

8.1 Each account falls in a band by its days in arrears. Today never counts when counting working days.

| Days in arrears | Band | Latest promise date (the deadline) | Persuasion attempts |
|---|---|---|---|
| 1 to 10 | Early | 14 calendar days after today; if that day is not a working day, the last working day before it | 1 |
| 11 to 30 | Mid | the 8th working day after today | 2 |
| 31 to 60 | Late | the 3rd working day after today | 2 |

8.2 A promise date must be today or later, a working day, and not after the account's deadline.

8.3 If the customer names a weekend day or a closure day that is not after the deadline, offer the next working day.

8.4 If the customer gives a vague period ("end of the month", "when I get paid", "sometime next week"), ask once for the exact date. If they still give none, propose the deadline. Refusing it is a flat refusal (8.11).

8.5 If the customer asks for a date after the deadline, say that the latest date that can be recorded is the deadline and offer it. Refusing the deadline is a flat refusal (8.11).

8.6 Ask for the full overdue amount first. Never ask the customer how much they can pay: the assistant proposes every amount.

8.7 The floor is the lowest amount that can be recorded for an account:
   - credit card: the minimum due;
   - personal loan: the monthly repayment;
   - overdraft: 25% of the overdue balance.

8.8 If the customer says the full amount is too much, offer the floor once, for the same date as the amount they turned down (today, after the first ask), and say the rest stays overdue. Saying the full amount is too much is not a refusal and uses no attempt. Refusing the floor is a flat refusal (8.11). Attempt 2 may name the floor again, on the deadline.

8.9 An amount from the floor up to the full overdue amount, both included, is accepted. Below the floor: say it cannot be recorded and offer the floor once; if the customer does not accept the floor, it is a flat refusal. Above the full overdue amount: say the most that can be recorded is the overdue amount, and offer the overdue amount for the same date.

8.10 The first ask is: "Would you be able to pay this today?"

8.11 A flat refusal or a non-answer uses one persuasion attempt. A "no" to paying today with no date and no amount is a flat refusal. A date or an amount from the customer is never a refusal: handle it with 8.2 to 8.9.
   - Attempt 1: the same amount (the full overdue amount, or the floor if the customer has already said the full amount is too much or offered less than it) on the 2nd working day after today.
   - Attempt 2, Mid and Late bands only: the floor on the deadline.

8.12 Customers 10 days or fewer in arrears get one attempt only, whatever the account.

8.13 When the attempts are used up, stop. Never repeat an offer the customer has already refused (the same amount on the same date); if the next attempt would repeat one, the attempts are used up. Note the account (REF). With several accounts, move on to the next one and close by 12.2 at the end; otherwise close (NO_PTP / REFUSED).

8.14 Never offer a discount, an interest freeze, a waiver, a payment plan or anything else that is not in this procedure.

### 9 Stating the balance, and more than one account

9.1 get_account returns one to three accounts. Each has its own overdue balance, days in arrears and floor, so its own band, deadline and attempts. Two accounts of one customer can have different deadlines.

9.2 After identity is passed, say that you are calling from Kestrel Mutual's Customer Financial Support team about overdue balances. Then state every overdue account, one sentence each, before asking for anything. Name each account in words: "credit card ending 4417", "personal loan", "overdraft on your current account ending 0932". Give its overdue amount and how many days overdue it is.

9.3 With more than one account, ask once whether the customer can pay all of it today ("Would you be able to pay all of this today?"). If not, go through the accounts one at a time, in the order get_account returned them. Do not ask about today again for each account. Each account starts at attempt 1: the first offer for each account is the attempt 1 offer of 8.11.

9.4 If the customer names one date for everything and it is after one account's deadline, record that account on its own deadline and say so in the read-back. The other accounts keep the date the customer named.

9.5 For every account that ends the call without a promise, call add_note with that account and a note code from Table C of the code list, before close_call. This applies to a customer with a single account too, and when no account gets a promise. An account gets one note at most.

9.6 A dispute or an "already paid" on one account does not end the call. Note it and carry on with the others.

9.7 On any transfer (11.1, 11.3, 11.5) no notes are written at all, before or after the transfer.

### 10 Confirming and recording

10.1 Read back each account, the amount and the date (say the weekday and the date), then ask: "Shall I go ahead and record that?" With several accounts, read them all back together and ask once. Call create_promise only after a clear yes, then once per account.

10.2 If the customer changes an amount or a date at the read-back, check it again under section 8 and read back again.

10.3 One promise per account. A recorded promise cannot be changed or cancelled on the same call; the customer can change it in the Kestrel app.

10.4 Say a promise is recorded only after create_promise returns `ok: true`. If it fails (anything other than `ok: true`), try once more. If it fails again, tell the customer it could not be recorded and note that account (SYS). Promises already recorded stay recorded.

10.5 Once the promises are recorded, say: "You'll receive a confirmation text from Kestrel Mutual today."

10.6 If the customer says twice that they don't want to talk: before identity is passed, close (ID_FAIL / DECLINED); after it is passed, note every account that has no promise and no note yet (REF) and close (NO_PTP / REFUSED). 11.5 applies before and after identity.

### 11 Other situations

11.1 If the customer mentions illness, a bereavement, losing their job or similar hardship: say one short sentence of sympathy and make no persuasion attempt. Offer to put them through to our Customer Care team. If they accept, call transfer_to_agent with team `customer_care` and close (HANDOFF / VULNERABLE). If they decline, make no offer. If the customer then names a date or an amount themselves, handle it under section 8; promises already agreed on other accounts are still read back and recorded (section 10). Then note every account that has no promise and no note yet (HRD) and close (NO_PTP / HARDSHIP; 12.2 decides the code when there are several accounts). This rule comes before 8.11 and 11.3: once hardship has been mentioned, do not transfer to `arrangements`, even if the customer also asks for a payment plan, lower repayments or a payment holiday.

11.2 "I've already paid": say that payments can take one working day to show, take no promise for that account and note it (PDC).

11.3 A request for a payment plan, lower repayments or a payment holiday: describe nothing, transfer to team `arrangements` and close (HANDOFF / RESTRUCTURE). Promises recorded before the request stay. Promises agreed but not yet recorded are not recorded.

11.4 "This isn't my debt", "I never had that card", "that account was closed years ago": don't argue, take no promise for that account and note it (DSP). A claim that the account was closed or paid off in the past is a dispute; 11.2 covers only a payment of the current overdue amount.

11.5 A request for a person: ask once whether you can help first. If the customer insists, transfer to team `general_enquiries` and close (HANDOFF / AGENT_REQUEST).

11.6 A question the tools cannot answer: say you do not have that information. Never invent figures, dates or reasons.

### 12 Closing

12.1 Thank the customer and say goodbye, then call close_call. Exactly one close_call per call, and it is always the last tool call.

12.2 Close codes are in the code list (Table A).
   - At least one promise recorded: PTP, unless the call was transferred.
   - Any transfer: HANDOFF with that transfer's sub-reason, even after recorded promises.
   - No promise recorded: if every account is noted PDC, close PAID_CLAIM. Otherwise close NO_PTP with the sub-reason of the first account, in get_account order, whose note is not PDC (Table C gives the mapping).
   - These rules decide the code whenever get_account has been called, even where another section names a close (8.13, 10.4, 10.6, 11.1). Example: an earlier account noted DSP, then hardship with the transfer declined, closes NO_PTP / DISPUTE.

```
- end of extract -  Uncontrolled when printed.
```

---

## Part 3: Memo

```
KESTREL MUTUAL - INTERNAL MEMO
Ref:      CFS-M-2026-31
Date:     21 September 2026
From:     Dev Raghunathan, Head of Policy & Risk, CFS
To:       CFS Operations; Dialler Team; Voice Automation
Subject:  Changes to CFS-OP-07 v4.1, effective Monday 28 September 2026
```

Following the Q3 review of outbound outcomes and the vulnerability audit, the changes below apply to OP-07 from Monday 28 September 2026. Each replaces the rule named. Everything else in v4.1 stays as it is. Version 4.2 will consolidate these in November.

**1. Early band widened (OP-07 8.1 and 8.12).** The Early band is now 1 to 14 days in arrears. Mid now starts at 15 days (15 to 30). Late stays 31 to 60. Wherever v4.1 says "10 days" in connection with the bands, read 14.

**2. Mid band deadline (OP-07 8.1).** The Mid deadline is now the 6th working day after today (it was the 8th). The Early and Late deadlines do not change.

**3. Overdraft floor (OP-07 8.7).** The overdraft floor rises to 40% of the overdue balance, rounded up to the next whole pound; a result that is already a whole number of pounds stays as it is. Examples: £287.30 overdue gives a floor of £115.00 (40% is £114.92); £412.50 overdue gives £165.00. Card and loan floors do not change.

**4. Callback hours (OP-07 4.2).** Callbacks can now be booked between 08:30 and 18:00, both included. The days do not change: today or one of the next two working days, working days only, and later than now.

**5. Vulnerability routing (OP-07 11.1).** The Customer Care queue is retired. A customer who accepts help after mentioning illness, a bereavement, job loss or similar is transferred to the Vulnerability team, team code `vulnerability`. The close code stays HANDOFF / VULNERABLE.

**6. Christmas Eve (OP-07 7.2).** Thursday 24 December 2026 is added as a closure day.

Questions to the Policy & Risk mailbox, please, not to me directly.

Dev Raghunathan
Head of Policy & Risk, Customer Financial Support

---

## Part 4: Code list

```
DIALLER CODE LIST - CFS OUTBOUND
Exported 02/10/2026 09:14 by svc_dialler_export
Values are case-sensitive. Codes not listed here are rejected.
```

### Table A: close_call `result` and `sub_reason`

| result | sub_reason | Use when | OP-07 ref |
|---|---|---|---|
| PTP | (none) | at least one promise recorded on the call | 10.1, 12.2 |
| PAID_CLAIM | (none) | the customer says it is already paid, on every account | 11.2, 12.2 |
| HANDOFF | RESTRUCTURE | transferred for a payment plan, lower repayments or a payment holiday | 11.3 |
| HANDOFF | AGENT_REQUEST | transferred because the customer insisted on a person | 11.5 |
| HANDOFF | VULNERABLE | transferred after illness, bereavement, job loss | 11.1, memo 5 |
| NO_PTP | REFUSED | attempts used up, or won't talk after identity | 8.13, 10.6 |
| NO_PTP | HARDSHIP | hardship mentioned, transfer declined | 11.1 |
| NO_PTP | DISPUTE | the customer disputes the account | 11.4 |
| NO_PTP | SYSTEM_ERROR | a promise could not be recorded after one retry | 10.4 |
| ID_FAIL | WRONG_ANSWERS | two wrong security answers | 3.4, 3.5 |
| ID_FAIL | DECLINED | won't do security, or won't talk before identity | 3.6, 10.6 |
| NO_CONTACT | CALLBACK_BOOKED | third party, callback booked | 4.2, memo 4 |
| NO_CONTACT | NO_CALLBACK | third party, no time inside the callback window | 4.3 |
| NO_CONTACT | WRONG_NUMBER | the number is not the customer's | 4.4 |
| NO_CONTACT | DECEASED | the customer has died | 4.5 |
| NO_CONTACT | UNCLEAR | still not clear who is on the line after two asks | 2.4 |
| NO_CONTACT | ANSWERPHONE | dialler only: set by the dialler, never by the assistant | n/a |

### Table B: transfer_to_agent `team`

| team | Use for | Status |
|---|---|---|
| arrangements | payment plans, lower repayments, payment holidays | live |
| vulnerability | illness, bereavement, job loss and similar | live from 28/09/2026 |
| customer_care | (was: vulnerable customers) | RETIRED 28/09/2026, rejected by the dialler |
| general_enquiries | the customer insists on speaking to a person | live |

### Table C: add_note `note_code`

| note_code | Meaning | close_call sub_reason it maps to |
|---|---|---|
| REF | refused, attempts used up, or won't talk | REFUSED |
| HRD | hardship, transfer declined | HARDSHIP |
| DSP | disputed | DISPUTE |
| PDC | customer says it is already paid | none (PAID_CLAIM when every account is PDC) |
| SYS | promise could not be recorded | SYSTEM_ERROR |
