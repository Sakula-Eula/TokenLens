from backend.usage.model import Usage
from backend.usage.openai_parser import parse_usage as parse_openai
from backend.usage.anthropic_parser import parse_usage as parse_anthropic
from backend.usage.responses_parser import parse_usage as parse_responses


def test_openai_full_mapping():
    payload = {
        "usage": {
            "prompt_tokens": 12500,
            "completion_tokens": 3210,
            "total_tokens": 15710,
            "prompt_tokens_details": {"cached_tokens": 8000},
        }
    }
    u = parse_openai(payload)
    assert u == Usage(12500, 3210, 8000, 0, 15710)


def test_openai_total_fallback():
    u = parse_openai({"usage": {"prompt_tokens": 100, "completion_tokens": 50}})
    assert u == Usage(100, 50, 0, 0, 150)


def test_openai_missing_usage_returns_none():
    assert parse_openai({"id": "x"}) is None


def test_anthropic_full_mapping():
    payload = {
        "usage": {
            "input_tokens": 1000,
            "output_tokens": 300,
            "cache_read_input_tokens": 600,
            "cache_creation_input_tokens": 120,
        }
    }
    u = parse_anthropic(payload)
    assert u == Usage(1000, 300, 600, 120, 1300)


def test_anthropic_missing_usage_returns_none():
    assert parse_anthropic({"type": "message"}) is None


def test_responses_full_mapping():
    payload = {
        "usage": {
            "input_tokens": 12500,
            "input_tokens_details": {"cached_tokens": 8000},
            "output_tokens": 3210,
            "total_tokens": 15710,
        }
    }
    u = parse_responses(payload)
    assert u == Usage(12500, 3210, 8000, 0, 15710)


def test_responses_total_fallback():
    u = parse_responses({"usage": {"input_tokens": 100, "output_tokens": 50}})
    assert u == Usage(100, 50, 0, 0, 150)


def test_responses_missing_usage_returns_none():
    assert parse_responses({"id": "resp_x"}) is None
