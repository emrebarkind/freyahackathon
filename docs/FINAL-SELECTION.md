# Final selection (19:08 UTC): run final2

Both runs were tested on the six example conversations over the chat route, against the live mock (one run each; final2 Ex3/Ex4 run twice).

| Ex | final (builder 3ca4aac, wf 6ab7a74e) | final2 (builder ab4d4a5, wf fa622670) |
|---|---|---|
| 1 | FAIL: no offer after the debt reading; 34.1 EUR read as "otuz dört Euro on bir sent" | FAIL: offer present; same amount error (34.1 → "on bir sent") |
| 2 | FAIL: "Hesap kesim tarihimi değiştirmek istiyorum" matched a main-menu intent; no week change | Behaviour PASS (get → decide 16.11/26.11 → explicit yes → change once → result → main menu); contract slip: statement.week.change sent statementDay 1, not the current 9 |
| 3 | PASS (1101 Yıldız Premium, 22.500 / 9.000) | FAIL 2/2: balance called with card numbers not in cards.list (1003, 1234, 4253 — the example numbers of the design text) |
| 4 | FAIL (minor): address read and confirmed, sent; call ended before "gönderildi" | FAIL 2/2: address confirmation question skipped (first run also used a wrong address) |
| 5 | FAIL: week change called twice | Behaviour PASS (vague "Olur herhalde" re-asked, change once, spouse refused); same statementDay slip |
| 6 | PASS | PASS (only the last four digits; first 12/6 refused) |

Last four digits were introduced correctly in every reading of both runs.

Why final2: it fixes the builder's structural cause (per-message intent routing ended calls; the turn rule made the offer impossible), which matters for the organisers' re-run of the builder; behaviour passes 3/6 against 2/6; the old run makes a transaction twice (Ex5). Known open defects of final2: Ex3 invented card numbers when a value from an earlier turn's tool result is needed; Ex4 skips the address confirmation; amount 34.1 read as "on bir"; statementDay 1 in the change request.

The old package stays at commit 074a588 (submission/final.workflow.json, traces/final.session.jsonl).
