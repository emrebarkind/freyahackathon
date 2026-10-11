"""Where each critical policy value comes from, and which codes the materials allow.

Every critical policy (amounts and rounding, attempt counting, transfers, dates, outcome codes) has an effective
value, the spec's own or the engine default, and a record in spec["policy"]:

  explicit     {"kind": "explicit", "quotes": ["<sentence>"]}                         the materials state the value
  derived      {"kind": "derived", "quotes": [...], "derivation": "<how>"}            it follows from several passages
  unspecified  {"kind": "unspecified", "assumption": "<what the agent does>"}         the materials are silent; the
                                                                                      engine default is used
  unsupported  {"kind": "unsupported", "requirement": "<rule>", "gap": "<why>"}       the spec cannot carry the rule

The old form spec["sources"][path] = "<sentence>" reads as an explicit record. Checks here are deterministic: a
quote must be in the materials, a record must agree with its kind (an unspecified policy keeps the engine default,
an unsupported one is listed in unsupported_rules). Whether a real quote supports the value is the audit's verdict
(extract.AUDIT), which sees the effective value, defaults included. A path with no record is recorded as uncertain,
never as unsupported.
"""
import json
import re

# path -> (engine default, area). The default is what the engine does when the path is unset.
CRITICAL = {
    "rules.skipped_repeat_counts": (True, "attempts"),
    "rules.opening_is_attempt": (False, "attempts"),
    "rules.opening_blocks_repeat": (False, "attempts"),
    "rules.too_much_skips_full": (False, "attempts"),
    "rules.too_much_floor": ("attempt_1", "attempts"),
    "rules.ladder_repeat_last": (False, "attempts"),
    "rules.refuse_deadline_is_refusal": (True, "attempts"),
    "rules.promise_retries": (1, "retries"),
    "rules.hardship_transfer": ("ask_first", "transfers"),
    "rules.notes_before_transfer": (False, "transfers"),
    "rules.deadline_adjust": ("previous_business_day", "dates"),
    "rules.first_ask": ("today", "dates"),
    "rules.week_end_today": ("literal", "dates"),
    "products.floor_pct": (None, "amounts"),
    "products.floor_min": (None, "amounts"),
    "products.floor_full_below": (None, "amounts"),
    "products.floor_round": ("cents", "amounts"),
    "products.step_round": ("cents", "amounts"),
    "products.promise_scale": (1, "amounts"),
    "products.promise_round": (None, "amounts"),
    "multi.outcome_priority": ([], "codes"),
    "event_changes": ([], "codes"),
}
KINDS = ("explicit", "derived", "unspecified", "unsupported")
CODE_FIELDS = (("outcome", "close_call", "c_outcome"), ("reason", "close_call", "c_reason"),
               ("queue", "transfer_to_agent", "t_queue"), ("note", "add_note", "n_reason"))


def get(d, path):
    for k in path.split("."):
        if isinstance(d, list):
            try:
                d = d[int(k)]
            except (ValueError, IndexError):
                return None
        elif isinstance(d, dict):
            d = d.get(k)
        else:
            return None
    return d


def effective(spec, path):
    """(value, is_default)"""
    v = get(spec, path)
    if v in (None, "") or (path in ("event_changes", "multi.outcome_priority") and not v):
        return CRITICAL[path][0], True
    return v, False


def norm(t):
    return re.sub(r"\s+", " ", re.sub(r"[`*_\"“”‘’'|]", "", str(t).lower())).strip()


def quote_found(q, text_n):
    parts = [x.strip() for x in re.split(r"\.\.\.|…|\[\.\.\.\]", norm(q)) if len(x.strip()) >= 12]
    return bool(parts) and all(x in text_n for x in parts)


def records(spec):
    out = {}
    for p, q in (spec.get("sources") or {}).items():          # the older form: one sentence = explicit
        if q:
            out[p] = {"kind": "explicit", "quotes": q if isinstance(q, list) else [q]}
    for p, r in (spec.get("policy") or {}).items():
        if isinstance(r, dict):
            out[p] = r
    return out


def check(spec, docs_text):
    """(errors, report). errors go to the repair round. report: path -> one line for the trace (kind, value)."""
    text = norm(docs_text)
    recs = records(spec)
    errs, report = [], {}
    unsup = [str(x) for x in spec.get("unsupported_rules") or []]
    for p, r in recs.items():
        if p not in CRITICAL:
            continue
        val, dflt = effective(spec, p)
        kind = r.get("kind")
        shown = json.dumps(val, ensure_ascii=False) + (" (engine default)" if dflt else "")
        if kind not in KINDS:
            errs.append(f"policy.{p}: kind {kind!r} invalid; use one of {list(KINDS)}")
            continue
        quotes = [q for q in (r.get("quotes") or []) if q]
        if kind in ("explicit", "derived"):
            if not quotes:
                errs.append(f"policy.{p}: an {kind} policy needs the sentence(s) that decide it (quotes)")
            for q in quotes:
                if not quote_found(q, text):
                    errs.append(f"policy.{p}: the quoted passage is not in the materials: {str(q)[:120]!r}")
            if kind == "derived" and not str(r.get("derivation") or "").strip():
                errs.append(f"policy.{p}: a derived policy needs its derivation (how the passages give the value)")
        elif kind == "unspecified":
            if not str(r.get("assumption") or "").strip():
                errs.append(f"policy.{p}: an unspecified policy needs the assumption the agent then follows")
            if not dflt and val != CRITICAL[p][0]:
                errs.append(f"policy.{p}: recorded as unspecified (the materials are silent) but the spec sets "
                            f"{shown} instead of the engine default {json.dumps(CRITICAL[p][0])}; either quote what "
                            f"decides it or leave it unset")
        elif kind == "unsupported":
            req = str(r.get("requirement") or "").strip()
            if not req or not str(r.get("gap") or "").strip():
                errs.append(f"policy.{p}: an unsupported policy needs the original requirement and the gap")
            elif not any(norm(req)[:60] in norm(u) or norm(u)[:60] in norm(req) for u in unsup):
                spec.setdefault("unsupported_rules", []).append(req)      # it must control the verdict
                unsup.append(req)
        report[p] = f"{kind}: {shown}"
    for p in CRITICAL:
        if p in recs:
            continue
        val, dflt = effective(spec, p)
        if dflt and val is None:
            continue                       # nothing set and nothing the engine assumes (an optional rule)
        report[p] = "no evidence recorded: " + json.dumps(val, ensure_ascii=False) + (" (engine default)" if dflt else "")
    return errs, report


def uncertain(report):
    return [f"{p}: {v}" for p, v in report.items() if v.startswith("no evidence recorded")]


def assumptions(spec):
    return [f"{p}: {r.get('assumption')}" for p, r in records(spec).items()
            if p in CRITICAL and r.get("kind") == "unspecified"]


def table(spec):
    """The audit's view: every critical policy with its effective value, defaults made visible."""
    recs = records(spec)
    rows = []
    for p in CRITICAL:
        val, dflt = effective(spec, p)
        if dflt and val is None and p not in recs:
            continue
        rows.append({"path": p, "value": val, "engine_default": dflt, "record": recs.get(p)})
    return rows


# ------------------------------------------------------------------------------------------------- codes

def _tokens(text):
    return set(re.findall(r"[A-Za-z0-9][A-Za-z0-9_\-]*", text))


def check_codes(spec, openapi, docs_text, enum_of_slot):
    """Codes against the API enum (if any) and the brief's code tables (spec["code_tables"], the effective tables
    after any undated amendment). A dated change (event_changes) may bring in a code the base table lacks, if the
    code is in the materials. With neither an enum nor a table for a field nothing is restricted; a code that is in
    no document is then only reported (warnings). Returns (errors, warnings)."""
    errs, warns = [], []
    tables = spec.get("code_tables") or {}
    toks = _tokens(docs_text)
    events = spec.get("events") or {}

    def allowed(field, outcome):
        t = tables.get(field)
        if isinstance(t, dict):
            t = t.get(outcome, t.get("*"))
        return [str(x) for x in t] if isinstance(t, list) else None

    def one(field, value, outcome, where, dated):
        if value in (None, ""):
            return
        en = enum_of_slot(field)
        if en:
            return                         # the API enum is checked in extract.validate
        in_docs = str(value) in toks
        table_ = allowed(field, outcome)
        if table_ is not None:
            if str(value) in table_:
                if not in_docs:
                    errs.append(f"{where}: code '{value}' is in code_tables.{field} but in no supplied document")
                return
            if dated and in_docs:
                return                     # a dated amendment that introduces the code
            what = f"code_tables.{field}" + (f".{outcome}" if isinstance(tables.get(field), dict) else "")
            errs.append(f"{where}: code '{value}' is not defined by the materials ({what} allows {table_})")
        elif not in_docs:
            warns.append(f"{where}: code '{value}' appears in no supplied document and the materials give no code "
                         f"table for {field}")

    for name, e in events.items():
        for field, _, _ in CODE_FIELDS:
            one(field, e.get(field), e.get("outcome"), f"events.{name}.{field}", False)
    for c in spec.get("event_changes") or []:
        if not isinstance(c, dict) or not isinstance(c.get("set"), dict):
            continue
        base = dict(events.get(c.get("event")) or {}, **c["set"])
        for field, _, _ in CODE_FIELDS:
            if field in c["set"]:
                one(field, c["set"][field], base.get("outcome"), f"event_changes.{c.get('event')}.{field}", True)
    for field, t in tables.items():
        if field not in [f for f, _, _ in CODE_FIELDS]:
            errs.append(f"code_tables.{field}: unknown field; use outcome, reason, queue or note")
    return errs, warns
