import json

from backend.usage.anthropic_parser import parse_usage as parse_anthropic
from backend.usage.model import Usage
from backend.usage.openai_parser import parse_usage as parse_openai
from backend.usage.responses_parser import parse_usage as parse_responses


class StreamUsageParser:
    def __init__(self, protocol: str):
        self.protocol = protocol
        self.stream_error: str | None = None
        self._buffer = ""
        self._openai_usage: Usage | None = None
        self._anthropic_input: Usage | None = None
        self._anthropic_output: Usage | None = None
        self._responses_usage: Usage | None = None

    def feed(self, text: str) -> Usage | None:
        self._buffer += text
        lines = self._buffer.split("\n")
        self._buffer = lines.pop()
        new_usage = None
        for line in lines:
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue
            new_usage = self._handle_event(event) or new_usage
        return new_usage

    def _handle_event(self, event) -> Usage | None:
        if not isinstance(event, dict):
            return None
        if "error" in event and isinstance(event["error"], dict):
            err = event["error"]
            self.stream_error = err.get("type") or err.get("code") or "stream_error"
            return None
        if self.protocol == "openai":
            usage = parse_openai(event)
            if usage is not None:
                self._openai_usage = usage
                return usage
            return None
        if self.protocol == "responses":
            if event.get("type") == "response.completed":
                response = event.get("response") or {}
                usage = parse_responses(response)
                if usage is not None:
                    self._responses_usage = usage
                    return usage
            return None
        if event.get("type") == "message_start":
            message = event.get("message") or {}
            usage = parse_anthropic({"usage": message.get("usage")})
            if usage is not None:
                self._anthropic_input = usage
            return None
        elif event.get("type") == "message_delta":
            usage = parse_anthropic({"usage": event.get("usage")})
            if usage is not None:
                self._anthropic_output = usage
        return self._merged_anthropic()

    def _merged_anthropic(self) -> Usage | None:
        a, b = self._anthropic_input, self._anthropic_output
        if a is None and b is None:
            return None
        return Usage(
            input_tokens=a.input_tokens if a else 0,
            output_tokens=b.output_tokens if b else 0,
            cache_read_tokens=a.cache_read_tokens if a else 0,
            cache_write_tokens=a.cache_write_tokens if a else 0,
        ).finalize()

    def finish(self) -> Usage | None:
        if self.protocol == "openai":
            return self._openai_usage
        if self.protocol == "responses":
            return self._responses_usage
        return self._merged_anthropic()
