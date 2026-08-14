from dataclasses import asdict, dataclass


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_tokens: int = 0

    def finalize(self) -> "Usage":
        if self.total_tokens == 0:
            self.total_tokens = self.input_tokens + self.output_tokens
        return self

    def to_dict(self) -> dict:
        return asdict(self)
