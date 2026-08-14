from backend.usage.model import Usage
from backend.usage.stream_parser import StreamUsageParser


def test_openai_usage_chunk_split_across_feeds():
    p = StreamUsageParser("openai")
    assert p.feed('data: {"choices":[{"delta":{"content":"你"}}]}\n\nda') is None
    u = p.feed('ta: {"choices":[{"finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":5,"total_tokens":15}}\n\ndata: [DONE]\n\n')
    assert u == Usage(10, 5, 0, 0, 15)
    assert p.finish() == Usage(10, 5, 0, 0, 15)


def test_openai_ignores_non_usage_chunks_and_bad_json():
    p = StreamUsageParser("openai")
    assert p.feed('event: x\ndata: {"choices":[{"delta":{}}]}\n\ndata: not-json\n\ndata: [DONE]\n\n') is None
    assert p.finish() is None


def test_openai_stream_error():
    p = StreamUsageParser("openai")
    p.feed('data: {"error": {"type": "server_error", "message": "boom"}}\n\n')
    assert p.stream_error == "server_error"


def test_anthropic_message_start_and_delta_merge():
    p = StreamUsageParser("anthropic")
    assert p.feed(
        'data: {"type":"message_start","message":{"usage":{"input_tokens":1000,'
        '"cache_read_input_tokens":600,"cache_creation_input_tokens":120}}}\n\n'
    ) is None
    u = p.feed('data: {"type":"message_delta","usage":{"output_tokens":300}}\n\n')
    assert u == Usage(1000, 300, 600, 120, 1300)
    assert p.finish() == Usage(1000, 300, 600, 120, 1300)


def test_anthropic_delta_only():
    p = StreamUsageParser("anthropic")
    p.feed('data: {"type":"message_delta","usage":{"output_tokens":42}}\n\n')
    assert p.finish() == Usage(0, 42, 0, 0, 42)
