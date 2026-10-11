"""Input files: the tool API is found by content (an OpenAPI document has 'paths'); a code list delivered as JSON is
bank material, read whole, not a usage error."""
import json
from builder.build import split_inputs


def test_a_second_json_file_is_material_not_an_error(tmp_path):
    (tmp_path / "brief.md").write_text("Brief")
    (tmp_path / "codes.json").write_text(json.dumps({"codes": [{"code": "REF", "meaning": "refused"}]}))
    (tmp_path / "tools.json").write_text(json.dumps({"openapi": "3.0.0", "paths": {"/close_call": {}}}))
    api, docs = split_inputs([str(tmp_path / "brief.md"), str(tmp_path / "codes.json"), str(tmp_path / "tools.json")])
    assert api == [str(tmp_path / "tools.json")]
    assert docs == [str(tmp_path / "brief.md"), str(tmp_path / "codes.json")]


def test_one_json_file_is_the_tool_api():
    api, docs = split_inputs(["brief.md", "api.json"])
    assert api == ["api.json"] and docs == ["brief.md"]
