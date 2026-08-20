from collections.abc import Mapping

from backend.config import ProviderConfig

HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade",
}
REQUEST_STRIP = HOP_BY_HOP | {"host", "accept-encoding", "content-length"}
RESPONSE_STRIP = {"content-encoding", "content-length", "connection", "transfer-encoding"}


def forward_request_headers(headers: Mapping[str, str], upstream_host: str) -> dict:
    out = {k.lower(): v for k, v in headers.items() if k.lower() not in REQUEST_STRIP}
    out["host"] = upstream_host
    return out


def strip_response_headers(headers: Mapping[str, str]) -> dict:
    return {k: v for k, v in headers.items() if k.lower() not in RESPONSE_STRIP}


def inject_stream_options(body: dict, protocol: str, path: str) -> bool:
    if protocol != "openai" or not path.endswith("/chat/completions"):
        return False
    if body.get("stream") is not True:
        return False
    stream_options = body.get("stream_options")
    if isinstance(stream_options, dict) and stream_options.get("include_usage") is True:
        return False
    body["stream_options"] = {**(stream_options if isinstance(stream_options, dict) else {}), "include_usage": True}
    return True


def apply_auth_fallback(headers: dict, cfg: ProviderConfig, protocol: str) -> dict:
    if cfg.api_key is None:
        return headers
    if protocol in ("openai", "responses") and "authorization" not in headers:
        headers["authorization"] = f"Bearer {cfg.api_key}"
    elif protocol == "anthropic" and "x-api-key" not in headers:
        headers["x-api-key"] = cfg.api_key
    return headers
