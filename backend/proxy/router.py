import json
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

from backend.proxy import forwarder

router = APIRouter()

MAX_BODY = 32 * 1024 * 1024  # 32MB，与 Anthropic/Claude Code 客户端限制一致（spec 第 7.2 节）


def _classify(rest: str) -> str | None:
    if rest.startswith("chat/completions"):
        return "openai"
    if rest == "responses":
        return "responses"
    if rest == "messages":
        return "anthropic"
    return None


@router.api_route("/{provider}/v1/{rest:path}",
                  methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def proxy_endpoint(provider: str, rest: str, request: Request):
    latency_start = time.perf_counter()
    created_at = datetime.now().isoformat(timespec="seconds")
    state = request.app.state
    cfg = state.providers.get(provider)
    if cfg is None:
        raise HTTPException(status_code=404, detail="provider not found")

    raw_body = b""
    if request.method not in ("GET", "HEAD"):
        async for chunk in request.stream():
            raw_body += chunk
            if len(raw_body) > MAX_BODY:
                raise HTTPException(status_code=413, detail="request body too large")

    protocol = _classify(rest)
    endpoint = f"/v1/{rest}"
    body, model = None, None
    if raw_body:
        if "application/json" not in (request.headers.get("content-type") or ""):
            raise HTTPException(status_code=400, detail="unsupported content-type")
        try:
            body = json.loads(raw_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise HTTPException(status_code=400, detail="invalid json body")
        model = body.get("model") if isinstance(body, dict) else None

    if protocol is None:
        return await forwarder.forward_passthrough(request, cfg, endpoint, raw_body)

    if body is not None and not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="invalid json body")

    from backend.proxy.preprocess import inject_stream_options

    inject_stream_options(body or {}, protocol, endpoint)
    is_stream = isinstance(body, dict) and body.get("stream") is True

    if is_stream:
        from backend.proxy.stream_proxy import forward_stream
        return await forward_stream(
            request, cfg, provider, protocol, endpoint, body, model,
            latency_start=latency_start, created_at=created_at,
        )

    return await forwarder.forward_non_stream(
        request, client=state.client, cfg=cfg, provider=provider,
        protocol=protocol, endpoint=endpoint, body=body, model=model,
        latency_start=latency_start, created_at=created_at,
    )
