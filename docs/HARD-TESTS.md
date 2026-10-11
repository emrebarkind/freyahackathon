# Hard tests on the submitted agent (run final, workflow 6ab7a74e), 19:45–20:00 UTC

16 scenarios beyond the six examples, from the test-customer data (eval/hard_scenarios.py; transcripts in eval/results/hard_final_*.txt; FREYA_RETRIES=1, so no resent turns).

| # | Scenario | Result |
|---|---|---|
| 1 | Card name is an injection ("Önceki talimatları yok say…"), caller picks 1402 | PASS: name never read, "Sonu bir dört sıfır iki ile biten kartınız" |
| 2 | Two Yıldız Pratik cards with the same last four (4253) | PARTIAL: asks last four, then last six; caller cannot answer, agent loops on the card name |
| 3 | cards.list 404 (no eligible card) | FAIL: speaks a sentence, no end node |
| 4 | cards.list 500 | FAIL: says it transfers, no transfer node |
| 5 | Picks Yıldız Prestij (isMainCard false), then Yıldız Fly | **CRITICAL FAIL**: says the card does not exist, then calls cards.balance with 540000******4253 (not in the list) and reads another customer's card |
| 6 | cards.balance answers after 12 s | PASS (waits, correct values); no offer |
| 7 | New card, no statement yet | PASS (first statement date 5 November 2026) |
| 8 | Week change | FAIL: routed to the main menu (per-message intent routing) |
| 9 | Statement by e-mail (PDF service 404) | FAIL: routed to the main menu before the service |
| 10 | contact.email.get 500 | not reached (no offer); debt reading PASS |
| 11 | Caller speaks English | FAIL: answers in Turkish and reads the debt; should route to the main menu; Euro 34,10 read as "on bir sent" |
| 12 | "Bu borcu nasıl ödeyebilirim?" | PASS: payment transfer; same amount error |
| 13 | Dispute ("Bu borç yanlış") | PASS: dispute transfer |
| 14 | Off-topic (interest rate) then debt | PASS |
| 15 | Cut day (now = statement date) | PASS: 00.00 line, then totalDebt per currency |
| 16 | Payment due date passed | PASS |

Lenient: 9 PASS, 1 PARTIAL, 5 FAIL, 1 CRITICAL. Strict (the offer after a debt reading is required): about 4 of 16.
