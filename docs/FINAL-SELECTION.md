# Final selection (19:27 UTC): run `final` (builder 3ca4aac, commit 074a588)

Selection by critical violations (sending to an unregistered address, sending without the address confirmation, a card number not in cards.list, statementDay not equal to statement.week.get), from the raw call records, not by pass count.

| Critical check | final (wf 6ab7a74e) | final2 (wf fa622670) | final3 (wf f6b9ee57) |
|---|---|---|---|
| statement.pdf.send address | ece.demir@freyabank.example (registered) | e.demir@freyabank.example in 1 of 2 runs (unregistered) | not reached (card error) |
| Address read and explicit yes before sending | yes: address question 18:36:49, "Evet" 18:36:51, send 18:36:54 | no, 2 of 2 runs: sent on "Tamam, son ekstreyi gönderin" without the address question | not reached |
| Card numbers sent only from cards.list | yes (all calls 540000******NNNN from the list) | no: Ex3 1003, 1234, 4253 (2 of 2 runs) | no: 456789******8500, 491652******1110, 455678******1110 |
| statementDay = statement.week.get value (9) | 9 in decide and change | 1 in change (Ex2, Ex5) | 1 |

Repeated user turns after an ending ("Evet", "Teşekkür ederim" ×3) are the test runner's resends: freya.api retried POST /chat/message after a 502/504 the platform had already processed (10 s apart, after the call was routed). The second statement.week.change (old Ex5, 18:38:21) and the 2nd/3rd statement.pdf.send (old Ex4) answer those resent turns in an already-routed call; not counted as an agent defect.

Known defects of the selected run: no offer after the debt reading (Ex1); "Hesap kesim tarihimi değiştirmek istiyorum" routed to the main menu in Ex2 (per-message intent routing); the result sentence is cut by the early ending in Ex4 ("gönderildi" not said) and Ex5. Euro 34,10 was read correctly in this run ("otuz dört Euro on sent").

final2 and final3 (fixes ab4d4a5 and 05d5888) are kept with their outputs but not submitted: they fix the offer and the week-change route, but break the data-source and confirmation rules above.
