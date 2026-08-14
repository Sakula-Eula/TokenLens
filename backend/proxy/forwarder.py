import json
import time
import uuid
from datetime import datetime

import httpx
from fastapi import Request, Response
from starlette.responses import JSONResponse

from backend.config import ProviderConfig
from backend.database.database import insert_request
from backend.proxy.preprocess import (
    apply_auth_fallback, forward_request_headers, strip_response_headers,
)
from backend.usage.anthropic_parser import parse_usage as parse_anthropic
from backend.usage.model import Usage
from backend.usage.openai_parser import parse_usage as parse_openai


def build_record(*, request_id, provider, model, endpoint, stream, usage: Usage | None,
                 latency_ms, status_code, error_type=None, created_at: str | None = None) -> dict:
    u = usage.to_dict() if usage else {}
    return {
        "request_id": request_id,
        "provider": provider,
        "model": model,
        "endpoint": endpoint,
        "stream": 1 if stream else 0,
        "input_tokens": u.get("input_tokens", 0),
        "output_tokens": u.get("output_tokens", 0),
        "cache_read_tokens": u.get("cache_read_tokens", 0),
        "cache_write_tokens": u.get("cache_write_tokens", 0),
        "total_tokens": u.get("total_tokens", 0),
        "latency_ms": latency_ms,
        "status_code": status_code,
        "success": 1 if (200 <= status_code < 300 and error_type is None) else 0,
        "error_type": error_type,
        "created_at": created_at or datetime.now().isoformat(timespec="seconds"),
    }


def _parse_usage(protocol: str, payload: dict) -> Usage | None:
    if protocol == "openai":
        return parse_openai(payload)
    return parse_anthropic(payload)


def _error_type_from(payload: dict) -> str | None:
    err = payload.get("error")
    if isinstance(err, dict):
        return err.get("type") or err.get("code") or err.get("message")
    if isinstance(payload.get("type"), dict):
        return payload["type"].get("type") or payload["type"].get("message")
    return None


async def forward_non_stream(request: Request, *, client: httpx.AsyncClient,
                              cfg: ProviderConfig, provider: str, protocol: str,
                              endpoint: str, body: dict | None, model: str | None,
                              latency_start: float, created_at: str) -> Response:
    headers = forward_request_headers(request.headers, httpx.URL(cfg.base_url).netloc)
    headers = apply_auth_fallback(headers, cfg, protocol)
    target = f"{cfg.base_url}{endpoint}"
    if request.url.query:
        target += f"?{request.url.query}"
    content = json.dumps(body).encode("utf-8") if body is not None else None

    def _finish(status_code, error_type, usage=None, request_id=None):
        latency = round((time.perf_counter() - latency_start) * 1000)
        insert_request(build_record(
            request_id=request_id or f"req_{uuid.uuid4().hex[:12]}",
            provider=provider, model=model, endpoint=endpoint,
            stream=False, usage=usage, latency_ms=latency,
            status_code=status_code, error_type=error_type, created_at=created_at,
        ))

    try:
        upstream = await client.request(request.method, target, headers=headers, content=content)
    except httpx.TransportError as exc:
        _finish(502, "proxy_connection_error")
        return JSONResponse(
            status_code=502,
            content={"error": {"message": f"无法连接上游：{exc}", "type": "proxy_connection_error"}},
        )

    payload = None
    raw = await upstream.aread()
    if raw and "application/json" in (upstream.headers.get("content-type") or ""):
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = None

    request_id = (upstream.headers.get("x-request-id")
                  or upstream.headers.get("request-id")
                  or f"req_{uuid.uuid4().hex[:12]}")

    error_type = None
    usage = None
    if upstream.status_code >= 400 and payload is not None:
        error_type = _error_type_from(payload)
    elif upstream.status_code < 300 and payload is not None:
        usage = _parse_usage(protocol, payload)
    _finish(upstream.status_code, error_type, usage, request_id)

    return Response(
        content=raw,
        status_code=upstream.status_code,
        headers=strip_response_headers(upstream.headers),
        media_type=upstream.headers.get("content-type"),
    )


async def forward_passthrough(request: Request, cfg: ProviderConfig,
                              endpoint: str, raw_body: bytes) -> Response:
    headers = forward_request_headers(request.headers, httpx.URL(cfg.base_url).netloc)
    target = f"{cfg.base_url}{endpoint}"
    if request.url.query:
        target += f"?{request.url.query}"
    try:
        upstream = await request.app.state.client.request(
            request.method, target, headers=headers, content=raw_body or None,
        )
    except httpx.TransportError as exc:
        return JSONResponse(status_code=502, content={"error": {"message": f"无法连接上游：{exc}"}})
    content = await upstream.aread()
    return Response(
        content=content, status_code=upstream.status_code,
        headers=strip_response_headers(upstream.headers),
        media_type=upstream.headers.get("content-type"),
    )
