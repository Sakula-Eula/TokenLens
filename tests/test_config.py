import pytest
import yaml

from backend.config import ProviderConfig, load_config


def test_load_valid(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump({
        "providers": {
            "provider_a": {"type": "openai", "base_url": "https://api.example.com", "api_key": "sk-1"},
            "provider_b": {"type": "anthropic", "base_url": "https://api.anthropic.com/"},
        }
    }), encoding="utf-8")
    cfg = load_config(p)
    assert cfg["provider_a"] == ProviderConfig("provider_a", "openai", "https://api.example.com", "sk-1")
    assert cfg["provider_b"].base_url == "https://api.anthropic.com"
    assert cfg["provider_b"].api_key is None


def test_missing_file_returns_empty(tmp_path):
    assert load_config(tmp_path / "nope.yaml") == {}


def test_reject_v1_suffix(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump({
        "providers": {"bad": {"type": "openai", "base_url": "https://api.example.com/v1"}}
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="bad"):
        load_config(p)


def test_reject_unknown_type(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump({
        "providers": {"bad": {"type": "gemini", "base_url": "https://x.com"}}
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="bad"):
        load_config(p)
