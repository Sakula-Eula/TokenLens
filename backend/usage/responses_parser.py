from backend.usage.model import Usage


def _num(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse_usage(payload: dict) -> Usage | None:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    details = usage.get("input_tokens_details")
    details = details if isinstance(details, dict) else {}
    return Usage(
        input_tokens=_num(usage.get("input_tokens")),
        output_tokens=_num(usage.get("output_tokens")),
        cache_read_tokens=_num(details.get("cached_tokens")),
        total_tokens=_num(usage.get("total_tokens")),
    ).finalize()
