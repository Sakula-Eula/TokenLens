"""Editable initial CNY presets, seeded once per database.

USD list prices were converted once at CNY 7.20/USD for convenient local
estimation. Runtime calculations use only the CNY values stored in SQLite.
Sources checked 2026-08-20:
- https://openai.com/api/pricing/
- https://www.anthropic.com/pricing
- https://api-docs.deepseek.com/quick_start/pricing/
"""

DEFAULT_PRICE_RULES = [
    # name, provider, model pattern, type, input, output, cache read,
    # input includes cached tokens
    ("OpenAI GPT-5.6 Sol", None, "gpt-5.6-sol*", "glob", "36", "216", "3.6", True),
    ("OpenAI GPT-5.6 Terra", None, "gpt-5.6-terra*", "glob", "14.4", "86.4", "1.44", True),
    ("OpenAI GPT-5.6 Luna", None, "gpt-5.6-luna*", "glob", "1.44", "8.64", "0.144", True),
    ("OpenAI GPT-5.4", None, "gpt-5.4", "exact", "9", "54", "0.9", True),
    ("OpenAI GPT-5.4 Mini", None, "gpt-5.4-mini*", "glob", "2.7", "16.2", "0.27", True),
    ("Anthropic Claude Sonnet 5", None, "claude-sonnet-5*", "glob", "14.4", "72", "1.44", False),
    ("Anthropic Claude Opus 4.6+", None, "claude-opus-4-[678]*", "glob", "36", "180", "3.6", False),
    ("Anthropic Claude Opus 4 Legacy", None, "claude-opus-4*", "glob", "108", "540", "10.8", False),
    ("Anthropic Claude Sonnet 4.x", None, "claude-sonnet-4*", "glob", "21.6", "108", "2.16", False),
    ("Anthropic Claude Haiku 3.5", None, "claude-3-5-haiku*", "glob", "5.76", "28.8", "0.576", False),
    ("DeepSeek V4 Flash", None, "deepseek-v4-flash*", "glob", "1.008", "2.016", "0.02016", True),
    ("DeepSeek V4 Pro", None, "deepseek-v4-pro*", "glob", "3.132", "6.264", "0.0261", True),
]

PRICE_SOURCE_NOTE = "官方 USD 标准价格按 7.20 CNY/USD 一次性换算；仅作本地估算，可在设置中修改"
