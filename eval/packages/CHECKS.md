# Expected-results key format (eval/packages/<pkg>/key.json)

A key states what a correct phone agent MUST do under the brief, as observable behaviour. It never names any
internal spec field. Every check belongs to a rule (`rule`: short id) and quotes the sentence(s) of the brief or
tool API that decide it (`source`). Answers are computed by hand / with Python's datetime from the documents only.

```json
{"package": "p1", "rules": {"R1": "plain-English statement of the rule", ...},
 "checks": [ {"id": "C1", "rule": "R1", "type": "...", "input": {...}, "expect": ..., "source": "quote"} ]}
```

Check types (input -> expect):

| type | input | expect |
|---|---|---|
| `deadline` | `now` (YYYY-MM-DDTHH:MM), `product` (one product record exactly as get_account returns it) | latest allowed promise date for that product, YYYY-MM-DD |
| `floor` | `now`, `product` | lowest amount (in currency units, e.g. 120.5) the agent may accept for that product |
| `attempts` | `now`, `product` | how many payment proposals the agent makes for that product AFTER the customer flatly refuses the opening "full amount today" ask, refusing each one flatly (0 = none) |
| `offers` | `now`, `product` | ordered list of `[amount, "YYYY-MM-DD"]` proposals the agent makes after the opening ask, if the customer flatly refuses each one (no counter-offer, no "too much"). The opening ask itself is never listed, even when a brief counts it as attempt 1 |
| `business_day` | `date` | true / false: may a promise fall on this date |
| `callback_ok` | `now`, `date`, `time` (HH:MM) | true / false: may the agent book a callback (for a third party who answered) at that date and time |
| `close` | `situation` (one of the list below) | `{"outcome": ..., "reason": ...}` sent to close_call ("" when the brief gives no reason) |
| `note` | `situation` | reason code sent to add_note for that situation, or null when no note is written |
| `transfer` | `situation` | queue sent to transfer_to_agent, or null when no transfer happens |
| `identity_fields` | {} | ordered list of verify_identity field values the agent asks for, as the tool API names them |
| `identity_max_wrong` | {} | the number of wrong answers after which identity check has failed (the Nth wrong answer ends the check) |
| `id_answer` | `field`, `value` (the answer as normal data, e.g. date "1984-03-07", postcode "SW1A1AA") | exact string sent as the answer to verify_identity |
| `promise_amount` | `amount` (agreed amount in currency units) | value sent as the amount to create_promise |

Situations (`close`, `note`, `transfer`):
promise (customer makes a valid promise), paid (says already paid), dispute (disputes the debt), hardship
(financial hardship), refused (refuses to pay after persuasion), transfer_human (asks for a human),
transfer_restructuring (wants restructuring / payment plan), service_error (bank system failure), id_failed
(identity check failed), id_declined (refuses identity questions), callback (third party answered, callback
booked), no_callback (third party answered, no callback booked), wrong_number, deceased, unclear (call could not
be resolved).
Only include a situation when the brief decides it.
