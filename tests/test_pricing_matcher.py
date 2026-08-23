from backend.pricing.matcher import choose_rule


def _rule(rule_id, pattern, match_type="glob", provider=None, priority=0):
    return {"id": rule_id, "name": str(rule_id), "model_pattern": pattern,
            "match_type": match_type, "provider": provider, "priority": priority, "enabled": 1}


def test_match_order_exact_then_provider_then_priority():
    rules = [
        _rule(1, "gpt-*", priority=999),
        _rule(2, "gpt-5", "exact"),
        _rule(3, "gpt-5", "exact", provider="openai"),
        _rule(4, "gpt-5", "exact", provider="openai", priority=10),
    ]
    assert choose_rule(rules, "openai", "gpt-5")["id"] == 4
    assert choose_rule(rules, "other", "gpt-5")["id"] == 2
    assert choose_rule(rules, "other", "gpt-6")["id"] == 1


def test_disabled_and_missing_model_do_not_match():
    rule = _rule(1, "*")
    rule["enabled"] = 0
    assert choose_rule([rule], "p", "m") is None
    assert choose_rule([_rule(2, "*")], "p", None) is None
