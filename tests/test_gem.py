import pytest
from dub import gem


@pytest.mark.live
def test_json_call_roundtrip():
    out = gem.json_call("Return the number 7.", {"type": "object", "properties": {"n": {"type": "integer"}},
                                                  "required": ["n"]})
    assert out["n"] == 7
    assert gem.cost() > 0
