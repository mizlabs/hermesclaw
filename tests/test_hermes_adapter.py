"""Tests for Hermes adapter — JSON only, no raw executable code."""

import json

import pytest

from hermes_openclaw.hermes.adapter import (
    HermesAdapterError,
    MockHermesAdapter,
    extract_json_from_response,
    reject_executable_content,
)


def test_mock_adapter_returns_structured_json():
    adapter = MockHermesAdapter()
    plan = adapter.plan("organize my downloads")
    assert "intent" in plan
    assert "actions" in plan
    assert isinstance(plan["actions"], list)


def test_extract_json_from_plain_response():
    raw = '{"intent": "test", "actions": [{"type": "list_files", "source": "."}]}'
    data = extract_json_from_response(raw)
    assert data["intent"] == "test"


def test_extract_json_from_markdown_fence():
    raw = (
        "Here is the plan:\n```json\n"
        '{"intent": "test", "actions": [{"type": "list_files", "source": "."}]}\n```'
    )
    data = extract_json_from_response(raw)
    assert data["intent"] == "test"


def test_rejects_python_code_block():
    raw = "```python\nimport os\nos.system('rm -rf /')\n```"
    with pytest.raises(HermesAdapterError, match="executable content"):
        reject_executable_content(raw)


def test_rejects_bash_code_block():
    raw = "```bash\nrm -rf /\n```"
    with pytest.raises(HermesAdapterError, match="executable content"):
        reject_executable_content(raw)


def test_rejects_forbidden_plan_keys():
    raw = json.dumps({"shell": "rm -rf /", "intent": "bad", "actions": []})
    with pytest.raises(HermesAdapterError, match="forbidden fields"):
        extract_json_from_response(raw)


def test_rejects_subprocess_in_text():
    raw = "import subprocess\nsubprocess.run(['ls'])"
    with pytest.raises(HermesAdapterError, match="executable content"):
        reject_executable_content(raw)
