# Platform retries carry bank-session state into the retried call: two cases (prepared 2026-10-11)

**Summary.** When the simulator retries a run (`settings.maxRetries = 3`), the retry uses the **same practice-bank
session** as the earlier attempt. The judge sees only the last attempt's transcript, but the bank ledger holds the
tool calls of every attempt. In both cases below, the first attempt completed correctly in the bank ledger, and the
retry then failed the conversation check because of state the first attempt had left behind. The official scores
count both runs as **FAIL**; we do not ask for them to be counted as passes.

Shown: simulation, iteration-run and call identifiers, platform timestamps, ledger rows (tool, non-identifying
arguments, bank response), and the judge's verdict. Left out: customer names, dates of birth and phone digits (all
synthetic practice data), and credentials.

## Case 1: PUB-12 (brief B), 11 Oct, simulation `0e827e31-ef75-4920-8843-89c1e43251e9`
* **Agent:** `b3b11a55-afbe-4b47-b73c-6328a9b5882e`.
* **Run kept by the platform:** call `ac5bf4f2-463e-4146-a41b-0d1f0b2fbe8b`, attempts = 1, started
  12:47:49.016Z, ended 12:49:41.707Z, outcome **fail**.
* **Judge:** "the phone question was asked only once …, rather than being 'asked again once' as required. All other
  criteria were met."
* **Earlier attempt:** call `e32887d5…`, created 12:37:34Z. It never ended (platform status 180) and has no
  transcript.

Ledger of the one practice customer:

| # | Attempt | Tool | Bank response |
|---|---|---|---|
| 1 | first | verify_identity date_of_birth | ok, verified true |
| 2 | first | verify_identity phone_last4 (wrong digits, as the persona script says) | ok, **verified false**, 2 left |
| 3 | first | verify_identity phone_last4 (corrected) | ok, verified true, all_verified true |
| 4 | first | get_account | ok |
| 5 | retry | verify_identity date_of_birth | ok, verified true |
| 6 | retry | verify_identity phone_last4 (**the same wrong digits as row 2**) | ok, **verified true** (session already verified) |
| 7 | retry | get_account | ok |
| 8–11 | retry | create_promise p1 510 on 2026-10-15; add_note p2 refused; add_note p3 refused; close_call promise | ok |

* **Effect:** in the retry the bank accepted the wrong phone digits, because the session was already verified. The
  scripted "wrong answer, then asked again once" could not happen in the transcript the judge saw.
* **Official:** FAIL (persona/judge mismatch caused by the carried session).

## Case 2: PUB-09 (brief A), 11 Oct, simulation `6fe2c7fa-1576-4dbf-8f72-d954ed73abef`
* **Agent:** `0a63e696-de73-4f10-ac0a-c63c3afa29ce`.
* **Run kept by the platform:** call `650cc7d4-a345-4055-a5ab-ce0042830f84`, attempts = 3, started
  14:43:10.360Z, ended 14:43:35.560Z, outcome **fail**.
* **Judge:** "The tool 'transfer_to_agent' was never called … The assistant ended the call due to identity
  verification failure."

Ledger of the one practice customer:

| # | Attempt | Tool | Bank response |
|---|---|---|---|
| 1 | earlier | verify_identity date_of_birth | ok, verified true |
| 2 | earlier | verify_identity phone_last4 | ok, verified true, all_verified true |
| 3 | earlier | get_account | ok |
| 4 | earlier | transfer_to_agent restructuring | **ok** |
| 5 | earlier | close_call transferred / restructuring | **ok** |
| 6–8 | last | verify_identity date_of_birth ×3 | **ok:false, "the call is already closed"** |
| 9 | last | close_call not_verified / failed | **ok:false, "the call is already closed"** |

* **Effect:** the earlier attempt completed the required transfer and close. Every call of the retry was refused
  because the session was already closed. The agent read the refusals as unreadable answers and closed as not
  verified.
* **Official:** FAIL.
* **Same simulation, PUB-06:** retried once (attempts = 1); its ledger also holds two identity checks and two
  get_account calls, and it passed.

## What is not known
* **Why the earlier attempts were retried.** The iteration keeps only the last call. For PUB-09 the earlier call's
  identifier is not exposed.
* **Whether the official evaluation retries in the same way, and whether it reuses the bank session.**
* **The retry rate.** We saw 3 retried runs out of about 50 on 11 Oct, but this is not a measured rate.

## Question for the organisers (draft, not sent)
When a simulation run is retried, is the practice-bank session reset? If not, can the judge see the earlier
attempt, or can the ledger of the earlier attempt be ignored for that run?
