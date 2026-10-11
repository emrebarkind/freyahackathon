# Variant relations to f1

Base: /home/user/oop/eval/fresh/f1 (20 checks C1-C20). Each variant directory holds brief.md, openapi.json, key.json; every `source` is a verbatim quote (whitespace-normalised, " / " separates fragments) of that variant's brief, checked by script. Weekdays verified with Python datetime (2026-10-15 Thu, 2026-11-15 Sun -> 2026-11-16 Mon, 2026-12-15 Tue, 2026-11-04 Wed, 2026-11-05 Thu, 2026-11-06 Fri).

## eq1

Semantically equivalent rewrite of f1: sections reordered (Scope, Amounts, Proposals, Tiers/dates, Verification, Reaching the customer, Special situations, Closing codes; memo kept last), every policy sentence reworded, clause labels renumbered. openapi.json identical. All expected values identical; only `source` quotes differ.

Changed checks: none.
Must stay identical to f1: C1, C2, C3, C4, C5, C6, C7, C8, C9, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20

## c_skip

F.3: a skipped (repeated) step is not said but now COUNTS towards the persuasion limit.

Changed checks (old -> new):
- C9 (offers): [[307.0, "2026-10-15"], [45.0, "2026-10-15"]] -> [[307.0, "2026-10-15"]]
- C10 (attempts): 2 -> 1
Must stay identical to f1: C1, C2, C3, C4, C5, C6, C7, C8, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20

## c_open

F.1: the opening "full amount today" ask does NOT count towards the limit; a ladder step identical to it is still skipped (stated in F.1), and a skipped step still does not count (F.3 unchanged).

Changed checks (old -> new):
- C8 (offers): [[612.5, "2026-10-15"], [307.0, "2026-10-15"]] -> [[612.5, "2026-10-15"], [307.0, "2026-10-15"], [45.0, "2026-10-15"]]
- C11 (offers): [[410.0, "2026-10-28"]] -> [[410.0, "2026-10-28"], [205.0, "2026-10-28"]]
- C13 (offers): [[333.33, "2026-12-15"], [167.0, "2026-12-15"]] -> [[333.33, "2026-12-15"], [167.0, "2026-12-15"], [84.0, "2026-12-15"]]
Must stay identical to f1: C1, C2, C3, C4, C5, C6, C7, C9, C10, C12, C14, C15, C16, C17, C18, C19, C20

## c_roll

D.3: the Tier 2 rollover happens when the 15th is today or earlier (on the 15th itself the deadline is next month's 15th, then business-day forward move).

Changed checks (old -> new):
- C2 (deadline): "2026-10-15" -> "2026-11-16"
- C9 (offers): [[307.0, "2026-10-15"], [45.0, "2026-10-15"]] -> [[612.5, "2026-11-16"], [307.0, "2026-11-16"]]
- C12 (offers): [] -> [[72.4, "2026-11-16"]]
Must stay identical to f1: C1, C3, C4, C5, C6, C7, C8, C10, C11, C13, C14, C15, C16, C17, C18, C19, C20

## c_units

E.1 overdraft floor: quarter rounded UP to the next multiple of EUR 5 (under EUR 100 still = full overdue, unrounded). E.3 + openapi: create_promise amount in whole euros (integer); an amount with cents is rounded up to the next whole euro. Offers lists are unaffected (half/floor values in the checks are not changed by the 5-euro rounding).

Changed checks (old -> new):
- C6 (floor): 84.0 -> 85.0
- C20 (promise_amount): 12995 -> 130
Must stay identical to f1: C1, C2, C3, C4, C5, C7, C8, C9, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19

## c_code

Memo: effective 2026-11-05 (not 11-04) and it replaces close reason `dispute` with `contested` (hardship untouched). C15-C19 are redefined on dispute situations, with C18 (hardship close) as the unaffected control.

Changed checks (old -> new):
- C15 REDEFINED: was close {"situation": "hardship", "now": "2026-11-03T15:00"} = {"outcome": "no_promise", "reason": "hardship"}; now close {"situation": "dispute", "now": "2026-11-04T15:00"} = {"outcome": "no_promise", "reason": "dispute"}
- C16 REDEFINED: was close {"situation": "hardship", "now": "2026-11-04T09:00"} = {"outcome": "no_promise", "reason": "financial_difficulty"}; now close {"situation": "dispute", "now": "2026-11-05T09:00"} = {"outcome": "no_promise", "reason": "contested"}
- C17 REDEFINED: was close {"situation": "hardship", "now": "2026-11-05T11:30"} = {"outcome": "no_promise", "reason": "financial_difficulty"}; now close {"situation": "dispute", "now": "2026-11-06T11:30"} = {"outcome": "no_promise", "reason": "contested"}
- C18 REDEFINED: was close {"situation": "dispute", "now": "2026-11-05T11:30"} = {"outcome": "no_promise", "reason": "dispute"}; now close {"situation": "hardship", "now": "2026-11-05T11:30"} = {"outcome": "no_promise", "reason": "hardship"}
- C19 REDEFINED: was note {"situation": "hardship", "now": "2026-11-05T11:30"} = "hardship"; now note {"situation": "dispute", "now": "2026-11-05T11:30"} = "dispute"
Must stay identical to f1: C1, C2, C3, C4, C5, C6, C7, C8, C9, C10, C11, C12, C13, C14, C20

## c_transfer

G.3: hardship -> one sentence of sympathy, note `hardship` on each remaining product, transfer straight away to queue `support` without asking, close transferred/support (H table: no_promise/hardship row removed, support added to transferred). Since close reason `hardship` no longer exists, the dated memo was moved to another event: from 2026-11-04 close reason `service_error` -> `system_unavailable` (C17 on/after, C21 before).

Changed checks (old -> new):
- C15 REDEFINED: was close {"situation": "hardship", "now": "2026-11-03T15:00"} = {"outcome": "no_promise", "reason": "hardship"}; now transfer {"situation": "hardship"} = "support"
- C16 REDEFINED: was close {"situation": "hardship", "now": "2026-11-04T09:00"} = {"outcome": "no_promise", "reason": "financial_difficulty"}; now close {"situation": "hardship", "now": "2026-11-05T11:30"} = {"outcome": "transferred", "reason": "support"}
- C17 REDEFINED: was close {"situation": "hardship", "now": "2026-11-05T11:30"} = {"outcome": "no_promise", "reason": "financial_difficulty"}; now close {"situation": "service_error", "now": "2026-11-04T09:00"} = {"outcome": "no_promise", "reason": "system_unavailable"}
- C21 ADDED: close {"situation": "service_error", "now": "2026-11-03T15:00"} = {"outcome": "no_promise", "reason": "service_error"}
Must stay identical to f1: C1, C2, C3, C4, C5, C6, C7, C8, C9, C10, C11, C12, C13, C14, C18, C19, C20

## c_transfer_ask

G.3: hardship -> note `hardship`, OFFER a transfer to queue `support`; accepted -> transferred/support; declined -> no_promise/hardship, with the f1 memo (hardship -> financial_difficulty from 2026-11-04) unchanged. `close` hardship checks use the DECLINED path, hence C15-C17 keep f1 values; new C21 `transfer` hardship = support (accepted path).

Changed checks: none.
- C21 ADDED: transfer {"situation": "hardship"} = "support"
Must stay identical to f1: C1, C2, C3, C4, C5, C6, C7, C8, C9, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20
