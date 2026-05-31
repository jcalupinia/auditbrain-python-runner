from backend.app.client_portal.tool_registry import (
    TOOLS, get_tool, list_enabled_tools, CATEGORIES,
)


def test_stub_tool_registered():
    assert "STUB_ECHO" in TOOLS
    t = get_tool("STUB_ECHO")
    assert t.label == "Stub Echo (testing)"
    assert "input" in t.slots


def test_get_unknown_tool_raises():
    import pytest
    with pytest.raises(KeyError):
        get_tool("DOES_NOT_EXIST")


def test_categories_have_required_keys():
    for cat in CATEGORIES:
        assert "id" in cat
        assert "label" in cat
