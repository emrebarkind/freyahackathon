From: Priya Raman <p.raman@harbourbank.example>
To: Vendor onboarding
Subject: FW: arrears calling - what your bot needs to know
Date: 2 October 2026

Hi team,

Forwarding the bits of our policy that matter for the arrears calls, plus the memo from last week that changed a
couple of things (the memo wins where they disagree). Code list at the bottom, please use those exact codes, our
MI reporting breaks otherwise. Customers are behind on one product only, never more.

Shout if anything is unclear.
Priya

-----------------------------------------------------------------
EXTRACT: Harbour Bank Retail Collections Policy v4.2, section 7 (Outbound arrears contact)

7.1 The caller identifies itself as "Harbour Bank's virtual assistant" in the first sentence and states that the call
    is recorded. No reference to arrears, balances, products or payment may be made until the customer has passed
    security. This applies equally to third parties.
7.2 Confirm the customer by asking "Is this {title} {last_name}?". Only an explicit confirmation counts. Ask a
    maximum of two times; if still unconfirmed, end the call (code NC-UNC).
7.3 Security consists of: (a) date of birth, then (b) the first line of the postcode... [superseded, see memo]
7.4 Three failed security answers in total end the call. Direct the customer to online banking. Code SEC-FAIL.
    Customers who will not answer after one explanation: code SEC-REF.
7.5 Third parties: give no information. Offer a callback on the same day only, 12:00 to 20:00, strictly after the
    current time (code NC-CB). If no suitable time after asking twice in total: code NC-NOCB. Wrong number: NC-WN.
    Deceased: express condolences, code NC-DEC.
7.6 After security, call the account service, state that the call is about a missed payment, name the product and
    the arrears amount and how many days it is late.
7.7 Promise dates: business days only (Mon-Fri, excluding bank holidays 2026-10-12, 2026-11-09, 2026-12-25,
    2026-12-28), no earlier than today, no later than 14 calendar days after today.
7.8 The customer is always asked for the full arrears first. If they cannot, the minimum acceptable is the
    contractual monthly payment held on the account (field monthly_payment). Below that: decline politely and
    offer the minimum once.
7.9 One persuasion attempt: offer the full arrears on the latest allowed date. If refused, close (code NP-REF).
7.10 Read back product, amount and date and ask "Shall I go ahead and log that?". Record only on a clear yes.
7.11 Confirm only after the system accepts the promise; then say "You'll get an email confirmation shortly." If the
     system fails twice: apologise, code NP-SYS.
7.12 Already paid: explain payments can take up to three working days, code PD. Dispute: code NP-DIS, no promise.
     Financial difficulty (job loss, illness, bereavement): show empathy, offer the Customer Care team (queue
     "care"); accepted: code TR-CARE; declined: code NP-HARD. Requests for a reduced plan: queue "plans", code
     TR-PLAN. Requests for a person: ask once if you can help, then queue "agents", code TR-AGT.

-----------------------------------------------------------------
MEMO   Collections Operations   25 September 2026
Re: changes to section 7 effective immediately

1. Security question (b) is now the LAST FOUR DIGITS OF THE MOBILE NUMBER on file, not the postcode.
2. Failed security: TWO wrong answers in total now end the call (was three).
3. Promise window shortened: no later than the 10th BUSINESS day after today (replaces 14 calendar days).
4. Customers more than 30 days late get a second persuasion attempt: the minimum amount on the latest allowed date.
   Customers 30 days late or less keep one attempt.
5. Callbacks: also allowed on the next business day, same hours.

-----------------------------------------------------------------
CODE LIST (close_call outcome / reason)
PROMISE        outcome=ptp            reason=(none)
PD             outcome=paid           reason=(none)
TR-CARE        outcome=transferred    reason=care
TR-PLAN        outcome=transferred    reason=plan
TR-AGT         outcome=transferred    reason=agent
NP-REF         outcome=no_ptp         reason=refused
NP-HARD        outcome=no_ptp         reason=hardship
NP-DIS         outcome=no_ptp         reason=dispute
NP-SYS         outcome=no_ptp         reason=system
SEC-FAIL       outcome=security_fail  reason=failed
SEC-REF        outcome=security_fail  reason=refused
NC-CB          outcome=no_contact     reason=callback
NC-NOCB        outcome=no_contact     reason=no_callback
NC-WN          outcome=no_contact     reason=wrong_number
NC-DEC         outcome=no_contact     reason=deceased
NC-UNC         outcome=no_contact     reason=unclear
