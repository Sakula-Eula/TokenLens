import asyncio
import json
import time
import uuid

import httpx
from fastapi import Request
from starlette.responses import StreamingResponse

from backend.config import ProviderConfig
from backend.database.database import insert_request
from backend.proxy.forwarder import build_record
from backend.proxy.preprocess import (
    apply_auth_fallback, forward_request_headers, strip_response_headers,
)
from backend.usage.stream_parser import StreamUsageParser


async def _send_upstream(request: Request, cfg: ProviderConfig, protocol: str,
                         endpoint: str, body: dict) -> httpx.Response | None:
    headers = forward_request_headers(request.headers, httpx.URL(cfg.base_url).netloc)
    headers = apply_auth_fallback(headers, cfg, protocol)
    target = f"{cfg.base_url}{endpoint}"
    if request.url.query:
        target += f"?{request.url.query}"
    try:
        req = request.app.state.client.build_request(
            request.method, target, headers=headers,
            content=json.dumps(body).encode("utf-8"),
        )
        return await request.app.state.client.send(req, stream=True)
    except httpx.TransportError:
        return None


async def forward_stream(request: Request, cfg: ProviderConfig, provider: str,
                         protocol: str, endpoint: str, body: dict, model: str | None):
    latency_start = time.perf_counter()
    upstream = await _send_upstream(request, cfg, protocol, endpoint, body)
    if upstream is None:
        insert_request(build_record(
            request_id=f"req_{uuid.uuid4().hex[:12]}", provider=provider, model=model,
            endpoint=endpoint, stream=True, usage=None,
            latency_ms=round((time.perf_counter() - latency_start) * 1000),
            status_code=502, error_type="proxy_connection_error",
        ))
        return StreamingResponse(
            iter([json.dumps({"error": {"message": "无法连接上游", "type": "proxy_connection_error"}}).encode()]),
            status_code=502, media_type="application/json",
        )

    parser = StreamUsageParser(protocol)
    state = {"usage": None, "error_type": None, "recorded": False}

    def _record():
        if state["recorded"]:
            return
        state["recorded"] = True
        usage = state["usage"] or parser.finish()
        insert_request(build_record(
            request_id=(upstream.headers.get("x-request-id")
                        or upstream.headers.get("request-id")
                        or f"req_{uuid.uuid4().hex[:12]}"),
            provider=provider, model=model, endpoint=endpoint, stream=True,
            usage=usage,
            latency_ms=round((time.perf_counter() - latency_start) * 1000),
            status_code=upstream.status_code, error_type=state["error_type"],
        ))

    async def generate():
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
                usage = parser.feed(chunk.decode("utf-8", errors="ignore"))
                if usage is not None:
                    state["usage"] = usage
                if parser.stream_error is not None:
                    state["error_type"] = parser.stream_error
        except asyncio.CancelledError:
            state["error_type"] = state["error_type"] or "client_abort"
            _record()
            raise
        except httpx.HTTPError:
            state["error_type"] = state["error_type"] or "upstream_abort"
        finally:
            _record()

    return StreamingResponse(
        generate(), status_code=upstream.status_code,
        headers=strip_response_headers(upstream.headers),
    )
