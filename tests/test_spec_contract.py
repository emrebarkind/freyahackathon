"""The spec doc is the extractor's whole view of the engine. A key the engine reads but the doc never names can only
ever hold its default (a fixed policy no brief can change); a key the doc names but the code never reads is silently
ignored. Both are the class of error the robustness round found; this test keeps the two in step."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOC = (ROOT / "builder" / "spec_doc.md").read_text()
CODE = "".join((ROOT / p).read_text() for p in ("builder/runtime/engine.py", "builder/runtime/cal.py",
                                              "builder/compile.py", "builder/selftest.py", "builder/spec_model.py"))
INTERNAL = {"no_chains", "promise_integer"}          # set by the compiler from the tool API, not by the extractor


def engine_reads():
    eng = (ROOT / "builder" / "runtime" / "engine.py").read_text()
    out = set()
    arg = r'(?:, (?:dict\(\)|\[\]|\(\)|[^()]*))?'
    for m in re.finditer(r'S(?:\.get\("([a-z_]+)"' + arg + r'\)|\["([a-z_]+)"\])((?:\.get\("[a-z_]+"' + arg + r'\)|\["[a-z_]+"\])*)', eng):
        subs = re.findall(r'(?:get\("|\[")([a-z_]+)', m.group(3))
        out.add((subs[:1] or [m.group(1) or m.group(2)])[0])
    return out


def test_every_key_the_engine_reads_is_in_the_spec_doc():
    missing = sorted(k for k in engine_reads() - INTERNAL if not re.search(r'["`]' + k + r'["`]', DOC))
    assert not missing, f"engine reads keys the extractor is never told about: {missing}"


def test_every_key_the_spec_doc_names_is_read_somewhere():
    keys = set(re.findall(r'^\s*"([a-z_]+)":', DOC, re.M))
    unread = sorted(k for k in keys if not re.search(r'["\']' + k + r'["\']', CODE) and "transfer_" not in k)
    assert not unread, f"spec doc names keys no code reads: {unread}"
