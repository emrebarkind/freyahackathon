# s2-money notes
- Stresses API/units: renamed body fields everywhere (question/response, acct_ref, amount_cents, pay_on, note_code, destination, result/result_reason), get_account amounts in integer cents (overdue_cents, monthly_payment_cents) while the brief and all floor/offer expectations are in dollars; create_promise in cents.
- Rounding boundaries for the CARD floor (12%, round up to whole dollar, min $35): 41250c -> $50 (49.50 up), 29167c -> $36 (35.0004 up, float-noise trap), 50000c -> $60 (exact stays), 2875c -> $28.75 (debt below minimum).
- Product-specific values: CARD vs AUTO deadlines per band; AUTO band 2 floor = whole debt, so ladder step 2 duplicates step 1 and is skipped and not counted (C12, C13 -> 1 proposal).
- Borderline: C13 (attempts = 1 for a band that allows 2) depends on rule 15 "a skipped step is not a proposal". C15 (1234.57 -> 123457) is a float-precision trap, not a policy question. C16 zip leading zero kept.
