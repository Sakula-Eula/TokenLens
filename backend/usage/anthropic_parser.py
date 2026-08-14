from backend.usage.model import Usage
from backend.usage.openai_parser import _num


def parse_usage(payload: dict) -> Usage | None:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    return Usage(
        input_tokens=_num(usage.get("input_tokens")),
        output_tokens=_num(usage.get("output_tokens")),
        cache_read_tokens=_num(usage.get("cache_read_input_tokens")),
        cache_write_tokens=_num(usage.get("cache_creation_input_tokens")),
    ).finalize()
