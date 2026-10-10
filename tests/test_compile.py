"""The compiled code node runs the way the platform runs it: wrapped in a function, every line indented,
code + call variables under the platform's 128 KB limit."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from builder import compile as comp  # noqa: E402

OPENAPI = json.load(open(ROOT / "kit" / "build-the-builder" / "tools" / "openapi.json"))


def run_step(src, V):
    wrapped = "def __user_main__():\n" + "\n".join("    " + line for line in src.split("\n")) + "\n__user_main__()\n"
    exec(wrapped, {"vars": V})


def test_code_node_runs_wrapped_and_fits():
    for name in ("brief-a", "brief-b"):
        wf = comp.compile_workflow(json.load(open(ROOT / "specs" / f"{name}.gold.json")), OPENAPI)
        src = wf["nodes"]["step"]["pre_actions"][0]["function"]["parameters"]["properties"]["code"]["default"]
        assert len(src.encode()) < comp.CODE_LIMIT
        assert "{{" not in src and "}}" not in src
        V = dict(customer_id="c", first_name="Daniel", last_name="Reyes", title="Mr", now="2026-10-14T11:00",
                 open_kind="confirmed", open_text="yes, speaking")
        run_step(src, V)
        assert V.get("next") == "talk_id" and not V.get("engine_error"), V.get("engine_error")
        assert len(json.dumps(V)) + len(src.encode()) < 131072


def test_minified_engine_is_the_same_program():
    import ast
    src = (comp.RUNTIME / "cal.py").read_text() + "\n" + (comp.RUNTIME / "engine.py").read_text()
    plain = ast.unparse(comp._StripDocs().visit(ast.parse(src)))
    assert ast.dump(ast.parse(comp.minify(src))) == ast.dump(ast.parse(plain))
