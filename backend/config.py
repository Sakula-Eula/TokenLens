from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class ProviderConfig:
    name: str
    type: str
    base_url: str
    api_key: str | None = None


def load_config(path: Path) -> dict[str, ProviderConfig]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    providers: dict[str, ProviderConfig] = {}
    for name, item in (raw.get("providers") or {}).items():
        ptype = item.get("type")
        if ptype not in ("openai", "anthropic"):
            raise ValueError(f"provider '{name}': type must be openai or anthropic")
        base_url = str(item.get("base_url", "")).rstrip("/")
        if base_url.endswith("/v1"):
            raise ValueError(f"provider '{name}': base_url must not end with /v1")
        if not base_url:
            raise ValueError(f"provider '{name}': base_url is required")
        providers[name] = ProviderConfig(
            name=name, type=ptype, base_url=base_url,
            api_key=item.get("api_key"),
        )
    return providers
