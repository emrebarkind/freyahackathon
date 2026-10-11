// Exhaustive check of the mock against test-customers.json: every entry, exact status and body; plus not-found and
// empty-field cases. Usage: node verify.mjs <bundled worker.js | base URL>
import fs from "node:fs";
const target = process.argv[2];
const DATA = JSON.parse(fs.readFileSync(new URL("./src/test-customers.json", import.meta.url)));
let call;
if (target.startsWith("http")) {
  call = async (path, data) => {
    const r = await fetch(target.replace(/\/$/, "") + path, { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ data, call: { ani: "5000000000", lang: "tr" } }) });
    return [r.status, await r.json()];
  };
} else {
  const mod = await import(target);
  call = async (path, data) => {
    const r = await mod.default.fetch(new Request("https://x" + path, { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ data, call: { ani: "5000000000", lang: "tr" } }) }));
    return [r.status, await r.json()];
  };
}
let ok = 0, bad = 0, delayed = 0;
const fail = (m) => { bad++; if (bad <= 15) console.log("FAIL", m); };
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
for (const c of DATA.customers) {
  const s = c.services || {};
  const reqs = [];
  if (s["cards.list"]) reqs.push(["cards.list", { customerNo: c.customerNo, aiFlow: "CardOps" }, s["cards.list"]]);
  if (s["contact.email.get"]) reqs.push(["contact.email.get", { customerNo: Number(c.customerNo), intAddressInfoType: "E" }, s["contact.email.get"]]);
  for (const [card, e] of Object.entries(s["cards.balance"] || {})) reqs.push(["cards.balance", { cardNumber: card }, e]);
  for (const [card, e] of Object.entries(s["statement.week.get"] || {})) reqs.push(["statement.week.get", { cardNumber: card }, e]);
  for (const svc of ["statement.week.decide", "statement.week.change"])
    for (const [card, weeks] of Object.entries(s[svc] || {}))
      for (const [w, e] of Object.entries(weeks)) reqs.push([svc, { cardNumber: card, newStatementWeek: Number(w), statementDay: 5 }, e]);
  const firstCard = Object.keys(s["cards.balance"] || {})[0] || "540000******0000";
  if (s["statement.pdf.send"]) reqs.push(["statement.pdf.send", { customerNo: c.customerNo, cardNumber: firstCard, currencyType: "TL", statementDate: "05.10.2026", emailAddress: "a@b.example" }, s["statement.pdf.send"]]);
  for (const [svc, data, e] of reqs) {
    if (e.delaySeconds) { delayed++; if (!target.startsWith("http")) continue; }
    const [st, body] = await call("/voice/v1/" + svc, data);
    if (st === e.http && same(body, e.response)) ok++; else fail(`${c.customerNo} ${svc} ${JSON.stringify(data)} -> ${st}, expected ${e.http}`);
  }
}
// not found / empty
const nf = [["cards.list", { customerNo: "11111111" }, 404, "FB_IVR_CHANNEL_102"], ["cards.balance", { cardNumber: "999999******0000" }, 404, "FB_IVR_CHANNEL_120"],
  ["statement.week.get", { cardNumber: "999999******0000" }, 404, "FB_IVR_CHANNEL_121"], ["statement.week.decide", { cardNumber: "999999******0000", newStatementWeek: 2, statementDay: 5 }, 400, "INVALID_ARGUMENTS_ERROR"],
  ["contact.email.get", { customerNo: "11111111", intAddressInfoType: "E" }, 400, "INVALID_ARGUMENTS_ERROR"], ["contact.email.get", { customerNo: "90000001", intAddressInfoType: "" }, 400, "INVALID_ARGUMENTS_ERROR"],
  ["cards.balance", { cardNumber: "" }, 400, "INVALID_ARGUMENTS_ERROR"], ["statement.pdf.send", { customerNo: "11111111", cardNumber: "x", currencyType: "TL", statementDate: "x", emailAddress: "x" }, 404, "FB_IVR_CHANNEL_107"]];
for (const [svc, data, st0, code] of nf) {
  const [st, body] = await call("/voice/v1/" + svc, data);
  if (st === st0 && body.result && body.result.code === code && !("data" in body)) ok++; else fail(`${svc} ${JSON.stringify(data)} -> ${st} ${JSON.stringify(body).slice(0, 120)}`);
}
console.log(`ok ${ok}, failed ${bad}, delayed entries ${delayed}${target.startsWith("http") ? "" : " (skipped locally)"}`);
process.exit(bad ? 1 : 0);
