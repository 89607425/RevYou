"""Tests for LLM client's truncated-JSON salvage logic."""
import sys
sys.path.insert(0, ".")

from app.services.llm_client import salvage_truncated_json


class TestSalvageTruncatedJson:
    def test_complete_json_untouched(self):
        text = '{"issues": [{"id": "PM-001", "title": "ok"}]}'
        assert salvage_truncated_json(text) == text

    def test_truncated_issue_array(self):
        # Truncated mid-object inside the issues array
        text = (
            '{"role": "tester", "overall_score": 60, "verdict": "v", '
            '"highlights": ["h"], "issues": ['
            '{"id": "TEST-001", "severity": "major", "title": "a"}, '
            '{"id": "TEST-002", "severity": "critical", "title": "b"}, '
            '{"id": "TEST-003", "sev'
        )
        result = salvage_truncated_json(text)
        assert result is not None
        import json
        parsed = json.loads(result)
        # The last partial object should be dropped
        assert len(parsed["issues"]) == 2
        assert parsed["issues"][0]["id"] == "TEST-001"

    def test_truncated_top_level_string_value(self):
        # Truncated inside a top-level string value — not salvageable by design
        text = '{"role": "tester", "verdict": "这'
        result = salvage_truncated_json(text)
        # Cannot cut safely inside a string; either None or valid prefix
        if result is not None:
            import json
            json.loads(result)

    def test_truncated_nested_object_field(self):
        text = (
            '{"summary": {"a": 1, "b": [1, 2]}, "items": [{"x": 1}, {"y": '
        )
        result = salvage_truncated_json(text)
        assert result is not None
        import json
        parsed = json.loads(result)
        assert parsed["items"] == [{"x": 1}]

    def test_empty_and_garbage(self):
        assert salvage_truncated_json("") is None
        assert salvage_truncated_json("not json at all") is None

    def test_trailing_comma_cleanup(self):
        # Cut point right after a trailing comma
        text = '{"items": [{"a": 1}, {"b": 2}, '
        result = salvage_truncated_json(text)
        assert result is not None
        import json
        parsed = json.loads(result)
        assert len(parsed["items"]) == 2
