from backend.config import ProviderConfig
from backend.proxy.preprocess import (
    apply_auth_fallback, forward_request_headers, inject_stream_options, strip_response_headers,
)

INBOUND = {
    "Host": "127.0.0.1:7788",
    "Authorization": "Bearer sk-abc",
    "Accept-Encoding": "gzip, deflate",
    "Content-Length": "123",
    "Connection": "keep-alive",
    "Content-Type": "application/json",
    "X-Custom": "v",
}


def test_forward_request_headers():
    out = forward_request_headers(INBOUND, "api.example.com")
    assert out["host"] == "api.example.com"
    assert "accept-encoding" not in out and "content-length" not in out and "connection" not in out
    assert out["authorization"] == "Bearer sk-abc"
    assert out["x-custom"] == "v"


def test_strip_response_headers():
    out = strip_response_headers({
        "content-type": "text/event-stream",
        "content-encoding": "gzip",
        "content-length": "99",
        "connection": "close",
        "transfer-encoding": "chunked",
        "x-request-id": "req_9",
    })
    assert out == {"content-type": "text/event-stream", "x-request-id": "req_9"}


def test_inject_stream_options_only_for_openai_stream():
    body = {"model": "m", "stream": True}
    assert inject_stream_options(body, "openai", "/v1/chat/completions") is True
    assert body["stream_options"] == {"include_usage": True}
    assert inject_stream_options(body, "openai", "/v1/chat/completions") is False
    assert inject_stream_options({"model": "m", "stream": False}, "openai", "/v1/chat/completions") is False
    assert inject_stream_options({"model": "m", "stream": True}, "anthropic", "/v1/messages") is False


def test_inject_preserves_existing_stream_options():
    body = {"model": "m", "stream": True, "stream_options": {"chunk_size": 64}}
    inject_stream_options(body, "openai", "/v1/chat/completions")
    assert body["stream_options"] == {"chunk_size": 64, "include_usage": True}


def test_auth_fallback():
    cfg = ProviderConfig("p", "openai", "https://x.com", "sk-cfg")
    out = apply_auth_fallback({"content-type": "application/json"}, cfg, "openai")
    assert out["authorization"] == "Bearer sk-cfg"
    out = apply_auth_fallback({"authorization": "Bearer sk-client"}, cfg, "openai")
    assert out["authorization"] == "Bearer sk-client"
    out = apply_auth_fallback({"content-type": "application/json"}, ProviderConfig("p", "anthropic", "https://x.com", "ak"), "anthropic")
    out = apply_auth_fallback({"content-type": "application/json"}, ProviderConfig("p", "responses", "https://x.com", "sk-resp"), "responses")
    assert out["authorization"] == "Bearer sk-resp"
    assert out["x-api-key"] == "ak"
