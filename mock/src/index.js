// Freya Bank voice services mock (Cloudflare Worker), from the service contract (sources/documents/
// 2026-10-01-service-contract.md, sections 3-6) and test-environment/test-customers.json.
// Every answer for a test customer is served exactly as the JSON gives it (status code and body); a customer, card or
// week without an entry gets the contract's 404 for that service, or a 400 INVALID_ARGUMENTS_ERROR where the service
// has no 404. Token, headers, `call` and `aiFlow` are not checked (as in the bank's test environment).
import DATA from "./test-customers.json";

const CUSTOMERS = {};
for (const c of DATA.customers) CUSTOMERS[String(c.customerNo)] = c;

const CARD_INDEX = {};   // masked card number (cards.list form) -> customer
for (const c of DATA.customers) {
  for (const svc of ["cards.balance", "statement.week.get", "statement.week.decide", "statement.week.change"]) {
    for (const card of Object.keys((c.services || {})[svc] || {})) CARD_INDEX[card] = c;
  }
}

const NOT_FOUND = {
  "cards.list": ["FB_IVR_CHANNEL_102", "Müşteriye ait geçerli kart bilgisi bulunamadı."],
  "cards.balance": ["FB_IVR_CHANNEL_120", "Kart bakiye servisi hatası: kart bulunamadı"],
  "statement.week.get": ["FB_IVR_CHANNEL_121", "Ekstre hafta servisi hatası: kart bulunamadı"],
  "statement.pdf.send": ["FB_IVR_CHANNEL_107", "Pdf dokümanı bulunamadı"],
};
const REQUIRED = {
  "cards.list": ["customerNo"],
  "cards.balance": ["cardNumber"],
  "statement.week.get": ["cardNumber"],
  "statement.week.decide": ["cardNumber", "newStatementWeek", "statementDay"],
  "statement.week.change": ["cardNumber", "newStatementWeek", "statementDay"],
  "contact.email.get": ["customerNo", "intAddressInfoType"],
  "statement.pdf.send": ["customerNo", "cardNumber", "currencyType", "statementDate", "emailAddress"],
};
const FIELD_TEXT = {
  customerNo: "customer number", cardNumber: "card number", newStatementWeek: "newStatementWeek",
  statementDay: "statementDay", intAddressInfoType: "intAddressInfoType", currencyType: "currencyType",
  statementDate: "statementDate", emailAddress: "emailAddress",
};

let seq = 0;
function guid() {
  seq += 1;
  const hex = (Date.now().toString(16) + seq.toString(16)).padStart(32, "0").slice(-32);
  return hex;
}
function errorBody(http, code, message, type, rootCause) {
  const g = guid();
  return [http, { result: { guid: g, returnCode: code, messageText: message, code, message, type,
    details: { guid: g, rootCause, errorOrigin: "freyahackathon-mock:ivr-channel-v0" } } }];
}
function notFound(svc) {
  if (NOT_FOUND[svc]) return errorBody(404, NOT_FOUND[svc][0], NOT_FOUND[svc][1], "WARNING", "NotFoundException");
  return errorBody(400, "INVALID_ARGUMENTS_ERROR", "no test data for this request", "ERROR", "InvalidArgumentsException");
}
function isTemplate(v) {
  return typeof v === "string" && (v.startsWith("{{") || v.startsWith("%7B%7B"));
}
function blank(v) {
  return v === undefined || v === null || (typeof v === "string" && v.trim() === "");
}
function entry(e) {      // {http, response, delaySeconds?}
  return e && typeof e === "object" && "http" in e && "response" in e ? e : null;
}

function lookup(svc, d) {
  for (const f of REQUIRED[svc] || []) {
    if (blank(d[f])) return [errorBody(400, "INVALID_ARGUMENTS_ERROR", `${FIELD_TEXT[f] || f} cannot be empty`, "ERROR", "InvalidArgumentsException"), 0];
  }
  const custNo = d.customerNo === undefined ? undefined : String(d.customerNo).trim();
  const card = d.cardNumber === undefined ? undefined : String(d.cardNumber).trim();
  const week = d.newStatementWeek === undefined ? undefined : String(d.newStatementWeek).trim();
  let e = null;
  if (svc === "cards.list" || svc === "contact.email.get" || svc === "statement.pdf.send") {
    const c = CUSTOMERS[custNo];
    e = c ? entry((c.services || {})[svc]) : null;
  } else {
    const c = CARD_INDEX[card];
    const byCard = c ? ((c.services || {})[svc] || {})[card] : null;
    if (svc === "statement.week.decide" || svc === "statement.week.change") e = byCard ? entry(byCard[week]) : null;
    else e = entry(byCard);
  }
  if (!e) return [notFound(svc), 0];
  return [[e.http, e.response], Number(e.delaySeconds || 0)];
}

function json(status, body) {
  return new Response(JSON.stringify(body), { status, headers: {
    "content-type": "application/json; charset=utf-8", "Access-Control-Allow-Origin": "*" } });
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: { "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS", "Access-Control-Allow-Headers": "*" } });
    }
    if (url.pathname === "/health") return json(200, { ok: true, service: "freya-bank-mock", customers: DATA.customers.length });
    if (url.pathname === "/oauth2/token" && request.method === "POST") {
      return json(200, { access_token: "test-token", token_type: "Bearer", expires_in: 1800 });
    }
    const m = url.pathname.match(/^(?:\/voice\/v1)?\/([a-z.]+)$/);
    const svc = m && m[1];
    if (!svc || !REQUIRED[svc]) return json(404, { error: "not_found", path: url.pathname });
    if (request.method !== "POST") return json(405, { error: "method_not_allowed" });
    let body = null;
    try { body = await request.json(); } catch { body = null; }
    const d = (body && typeof body === "object" && body.data && typeof body.data === "object") ? body.data : {};
    // The panel's "Test API Request" sends {{variables}} unfilled: answer with the first test customer's record.
    if (Object.values(d).some(isTemplate)) {
      const first = DATA.customers[0];
      const fd = { customerNo: first.customerNo, intAddressInfoType: "E", currencyType: "TL", statementDate: "x", emailAddress: "x",
                   cardNumber: Object.keys((first.services || {})["cards.balance"] || {})[0], newStatementWeek: "2", statementDay: 5 };
      const [[s, b]] = lookup(svc, fd);
      return json(s, b);
    }
    const [[status, resp], delay] = lookup(svc, d);
    if (delay > 0) await new Promise((r) => setTimeout(r, delay * 1000));
    return json(status, resp);
  },
};
