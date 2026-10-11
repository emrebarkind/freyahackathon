# Extra check type for the robustness packages: `conversation`

All types of eval/packages/CHECKS.md are allowed, plus:

| type | input | expect |
|---|---|---|
| `conversation` | `now`; `products` (the get_account product records exactly as the API returns them, 1-3); `script` (customer turns, see below); optional `faults` ({"create_promise": n} = the first n create_promise calls fail with a server error; same for other tools) | what the bank's ledger must hold at the end: `{"outcome", "reason", "promises": [[product_id, amount, "YYYY-MM-DD"]...], "notes": [[product_id, note_reason]...], "transfers": [queue...]}`; `amount` is the value sent to create_promise in the API's own unit; lists in any order; a key you leave out is not checked |

The call starts after the customer confirmed who they are and passed the identity check (the harness does that).
The agent then states the debt and asks whether the customer can pay everything in full today. Each script turn is
one customer answer, in order:

- `{"k": "yes"}`: agrees to what was just proposed / confirms the read-back
- `{"k": "no"}`: flat refusal, no date, no amount
- `{"k": "proposes", "date": "YYYY-MM-DD", "amount": 120.0, "product": "<product type>|all"}`: names a date and/or an
  amount (either may be omitted), optionally for one product type or for all
- `{"k": "too_much"}`: says the full amount is too much
- `{"k": "hardship"}`, `{"k": "restructure"}`, `{"k": "human"}`
- `{"k": "dispute", "product": "<type>"}`, `{"k": "already_paid", "product": "<type>"}`

If the agent needs more turns than the script has, the customer goes silent (the call ends there). Write scripts
that end the call as the brief says (e.g. a final `yes` to the read-back). Expected values must follow from the brief
and the tool API only.
