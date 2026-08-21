from dataclasses import dataclass
from pathlib import Path
import re
import tempfile

import yaml


@dataclass
class ProviderConfig:
    name: str
    type: str
    base_url: str
    api_key: str | None = None
    upstream_path_mode: str = "v1"


_PROVIDER_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def _normalize_provider(name: str, item: dict) -> ProviderConfig:
    name = str(name).strip()
    if not name or not _PROVIDER_NAME.fullmatch(name):
        raise ValueError("provider name may only contain letters, numbers, '.', '_' and '-'")
    ptype = item.get("type")
    if ptype not in ("openai", "anthropic"):
        raise ValueError(f"provider '{name}': type must be openai or anthropic")
    base_url = str(item.get("base_url", "")).strip().rstrip("/")
    if base_url.endswith("/v1"):
        raise ValueError(f"provider '{name}': base_url must not end with /v1")
    if not base_url.startswith(("http://", "https://")):
        raise ValueError(f"provider '{name}': base_url must start with http:// or https://")
    path_mode = item.get("upstream_path_mode") or "v1"
    if path_mode not in ("v1", "codex"):
        raise ValueError(f"provider '{name}': upstream_path_mode must be v1 or codex")
    return ProviderConfig(
        name=name, type=ptype, base_url=base_url,
        api_key=item.get("api_key") or None, upstream_path_mode=path_mode,
    )


def load_config(path: Path) -> dict[str, ProviderConfig]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    providers: dict[str, ProviderConfig] = {}
    for name, item in (raw.get("providers") or {}).items():
        providers[name] = _normalize_provider(name, item or {})
    return providers


def public_providers(path: Path) -> list[dict]:
    return [
        {
            "name": provider.name,
            "type": provider.type,
            "base_url": provider.base_url,
            "upstream_path_mode": provider.upstream_path_mode,
            "has_api_key": bool(provider.api_key),
        }
        for provider in load_config(path).values()
    ]


def save_providers(path: Path, items: list[dict]) -> None:
    existing = load_config(path)
    normalized: dict[str, dict] = {}
    for item in items:
        name = str(item.get("name", "")).strip()
        if name in normalized:
            raise ValueError(f"duplicate provider name: {name}")
        current_key = existing.get(name).api_key if name in existing else None
        api_key = item.get("api_key")
        if api_key is None:
            api_key = current_key
        if item.get("clear_api_key"):
            api_key = None
        provider = _normalize_provider(name, {**item, "api_key": api_key})
        data = {"type": provider.type, "base_url": provider.base_url}
        if provider.upstream_path_mode != "v1":
            data["upstream_path_mode"] = provider.upstream_path_mode
        if provider.api_key:
            data["api_key"] = provider.api_key
        normalized[provider.name] = data

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    raw = raw if isinstance(raw, dict) else {}
    raw["providers"] = normalized
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False) as handle:
        yaml.safe_dump(raw, handle, allow_unicode=True, sort_keys=False)
        temp_path = Path(handle.name)
    temp_path.replace(path)
