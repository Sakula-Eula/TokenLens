from fnmatch import fnmatchcase


def rule_matches(rule: dict, provider: str, model: str | None) -> bool:
    if not rule.get("enabled", 1) or not model:
        return False
    scope = rule.get("provider")
    if scope and scope != provider:
        return False
    pattern = rule.get("model_pattern") or ""
    if rule.get("match_type") == "exact":
        return model == pattern
    return fnmatchcase(model, pattern)


def choose_rule(rules: list[dict], provider: str, model: str | None) -> dict | None:
    matches = [rule for rule in rules if rule_matches(rule, provider, model)]
    if not matches:
        return None
    return min(matches, key=lambda rule: (
        0 if rule.get("match_type") == "exact" else 1,
        0 if rule.get("provider") else 1,
        -int(rule.get("priority") or 0),
        int(rule.get("id") or 0),
    ))
