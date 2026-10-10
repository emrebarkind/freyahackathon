"""Brief(s) + tool API file -> spec (builder/spec_doc.md), with validation, a second independent reading,
and an adjudication pass on disagreements."""
import copy
import json
import pathlib
import re

from . import claude

DOC = (pathlib.Path(__file__).resolve().parent / "spec_doc.md").read_text()

SYSTEM = """You are a meticulous bank-operations analyst. You turn a bank's collections brief (which may be a clean
specification, or raw material: emails, policy extracts, memos that change earlier rules, code lists) and the
bank's tool API file into a precise machine-readable spec for an automated phone agent.

Rules:
- Read every line. Most failures come from one skipped rule.
- When documents conflict, the later or more specific instruction wins (a memo that changes a rule beats the
  policy it changes; a dated change beats an undated one). Record every such resolution in `assumptions`.
- Take every value (dates, numbers, codes, field names, enum values, wording) from the documents given. Never
  reuse values from examples or from your own knowledge.
- Field names and allowed values for tool calls come from the tool API file.
- Answer with the JSON object only."""


def prompt_for(briefs, openapi):
    docs = "\n\n".join(f"<document name=\"{name}\">\n{text}\n</document>" for name, text in briefs)
    return (f"{DOC}\n\n# Tool API file\n<openapi>\n{json.dumps(openapi, indent=1)}\n</openapi>\n\n"
            f"# Bank materials\n{docs}\n\nProduce the spec JSON now.")


# ------------------------------------------------------------------------------------------- validation
LINE_KEYS = [k.strip() for k in DOC.split("Required keys:")[1].split("Meaning")[0].replace("\n", " ").split(",") if k.strip()]
EVENT_KEYS = ["promise", "paid", "transfer_restructuring", "transfer_human", "transfer_support", "refused", "hardship",
              "dispute", "service_error", "id_failed", "id_declined", "callback", "no_callback", "wrong_number",
              "deceased", "unclear"]
SLOTS = {"verify_identity": {"q_field", "q_answer"}, "get_account": set(),
         "create_promise": {"p_product", "p_amount", "p_date"}, "add_note": {"n_product", "n_reason"},
         "schedule_callback": {"cb_date", "cb_time"}, "transfer_to_agent": {"t_queue"},
         "close_call": {"c_outcome", "c_reason"}}


def tool_props(openapi, tool):
    try:
        return openapi["paths"]["/" + tool]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"]
    except KeyError:
        return {}


def enum_of(openapi, tool, param):
    return tool_props(openapi, tool).get(param, {}).get("enum")


def validate(spec, openapi):
    errs = []
    for k in ["calendar", "identity", "products", "bands", "ladder", "events", "tool_bodies", "lines", "callback", "confirm"]:
        if k not in spec:
            errs.append(f"missing key {k}")
    if errs:
        return errs
    for k in LINE_KEYS:
        if k not in spec["lines"]:
            errs.append(f"lines.{k} missing")
    for k in EVENT_KEYS:
        if k not in spec["events"]:
            errs.append(f"events.{k} missing")
    tb = spec["tool_bodies"]
    for tool, slots in SLOTS.items():
        if tool not in tb:
            errs.append(f"tool_bodies.{tool} missing")
            continue
        props = tool_props(openapi, tool)
        got = set(tb[tool].values())
        if not slots <= got and tool != "close_call":
            errs.append(f"tool_bodies.{tool} must map slots {sorted(slots)}; got {tb[tool]}")
        for param in tb[tool]:
            if param not in props:
                errs.append(f"tool_bodies.{tool}: '{param}' is not a field of {tool} in the tool API (fields: {sorted(props)})")
    inv = {tool: {v: k for k, v in m.items()} for tool, m in tb.items()}

    def check_enum(tool, slot, value, where):
        param = inv.get(tool, {}).get(slot)
        en = enum_of(openapi, tool, param) if param else None
        if en and value not in ("", None) and value not in en:
            errs.append(f"{where}: '{value}' is not an allowed {tool}.{param} value {en}")

    for name, e in spec["events"].items():
        check_enum("close_call", "c_outcome", e.get("outcome"), f"events.{name}.outcome")
        check_enum("close_call", "c_reason", e.get("reason"), f"events.{name}.reason")
        if e.get("queue"):
            check_enum("transfer_to_agent", "t_queue", e["queue"], f"events.{name}.queue")
        if e.get("note"):
            check_enum("add_note", "n_reason", e["note"], f"events.{name}.note")
    for q in spec["identity"].get("questions", []):
        check_enum("verify_identity", "q_field", q.get("field"), "identity.questions.field")
        if q.get("kind") not in ("date", "digits", "year", "upper", "text"):
            errs.append(f"identity question kind {q.get('kind')} invalid")
    if not spec["identity"].get("questions"):
        errs.append("identity.questions is empty")
    kinds = {"business_days_after", "calendar_days_after", "end_of_month", "end_of_next_month", "last_business_day_of_month", "fixed_date"}
    for b in spec["bands"]:
        if b.get("deadline", {}).get("kind") not in kinds:
            errs.append(f"band {b.get('name')}: deadline kind invalid")
    for s in spec["ladder"]:
        if s.get("amount") not in ("full", "floor", "full_or_floor"):
            errs.append(f"ladder amount {s.get('amount')} invalid")
    try:
        ptypes = openapi["paths"]["/get_account"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]["properties"]["products"]["items"]["properties"]["type"].get("enum")
    except KeyError:
        ptypes = None
    for t in ptypes or []:
        if t not in spec["products"].get("names", {}):
            errs.append(f"products.names has no spoken name for product type {t}")
        if t not in spec["products"].get("floor_field", {}) and not spec["products"].get("floor_pct"):
            errs.append(f"products.floor_field missing for product type {t}")
    for k, v in spec["lines"].items():
        if k not in ("recorded", "sms_line", "record_failed") and re.search(r"\brecorded\b", str(v), re.I):
            errs.append(f"lines.{k} uses the word 'recorded'; a judge can hear it as a false claim that a promise was recorded. "
                        f"Rephrase in the active voice ('we record this call') or use 'noted'")
        if "{{" in str(v) or "}}" in str(v):
            errs.append(f"lines.{k} must use single braces")
    return errs


# ------------------------------------------------------------------------------------------- comparison
CORE = ["calendar", "date_rules", "confirm", "callback", "identity.questions", "identity.max_wrong", "identity.hints",
        "products.floor_field", "products.amount_field", "products.floor_pct", "bands", "ladder", "notes", "events",
        "tool_bodies", "multi", "human", "max_not_talk", "rules"]


def get(d, path):
    for p in path.split("."):
        d = d.get(p) if isinstance(d, dict) else None
    return d


def norm(v):
    if isinstance(v, list) and v and isinstance(v[0], dict):
        return [{k: x for k, x in i.items() if k not in ("ask", "name")} for i in v]
    if isinstance(v, list):
        return sorted(map(str, v)) if all(not isinstance(x, (dict, list)) for x in v) else v
    return v


def diff(a, b):
    out = []
    for path in CORE:
        if json.dumps(norm(get(a, path)), sort_keys=True) != json.dumps(norm(get(b, path)), sort_keys=True):
            out.append(path)
    return out


ADJ = """Two analysts produced specs from the same materials and disagree on these fields: {fields}.
Re-read the materials, decide each disputed field, quoting the sentence that decides it, then output the final
complete spec JSON (all keys), starting from spec A and replacing only what is wrong.

<spec_A>
{a}
</spec_A>
<spec_B>
{b}
</spec_B>

First write one line per disputed field: FIELD: decision -- "quote". Then the JSON in a ```json block."""

REPAIR = """Your spec has these problems:
{errs}
Fix them and output the complete corrected spec JSON in a ```json block."""


def extract(briefs, openapi, trace):
    base = prompt_for(briefs, openapi)
    texts = claude.ask_many([(base, SYSTEM, "read the brief and tool API into a spec (reading 1)"),
                             (base, SYSTEM, "read the brief and tool API into a spec (reading 2, independent)")], trace)
    specs = []
    for t in texts:
        try:
            specs.append(claude.json_block(t))
        except Exception as e:
            trace.note(f"a reading did not parse as JSON: {e}")
    if not specs:
        raise RuntimeError("no reading produced a spec")
    spec = specs[0]
    if len(specs) == 2:
        d = diff(specs[0], specs[1])
        trace.note(f"readings disagree on: {d or 'nothing'}")
        if d:
            out = claude.ask(base + "\n\n" + ADJ.format(fields=", ".join(d), a=json.dumps(specs[0], indent=1), b=json.dumps(specs[1], indent=1)),
                             SYSTEM, "adjudicate disagreements between the two readings: " + ", ".join(d), trace)
            trace.note("adjudication: " + out.split("```")[0].strip()[:3000])
            spec = claude.json_block(out)
    for attempt in range(3):
        errs = validate(spec, openapi)
        trace.note(f"validation round {attempt + 1}: {len(errs)} problem(s)" + ("".join("\n  - " + e for e in errs)))
        if not errs:
            break
        out = claude.ask(base + "\n\n<your_spec>\n" + json.dumps(spec, indent=1) + "\n</your_spec>\n\n" + REPAIR.format(errs="\n".join("- " + e for e in errs)),
                         SYSTEM, f"repair {len(errs)} validation problem(s) in the spec", trace)
        spec = claude.json_block(out)
    return spec
