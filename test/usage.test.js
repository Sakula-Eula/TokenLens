"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { calculateCost, extractStreamingUsage, extractUsage } = require("../src/usage");

test("解析 Responses API 的 usage 和缓存、reasoning 明细", () => {
  assert.deepEqual(extractUsage({ usage: { input_tokens: 100, output_tokens: 50, total_tokens: 150, input_tokens_details: { cached_tokens: 30 }, output_tokens_details: { reasoning_tokens: 12 } } }), {
    inputTokens: 100, outputTokens: 50, cachedTokens: 30, reasoningTokens: 12, totalTokens: 150,
  });
});

test("解析 chat.completion 的 usage", () => {
  assert.deepEqual(extractUsage({ usage: { prompt_tokens: 20, completion_tokens: 5, total_tokens: 25 } }), {
    inputTokens: 20, outputTokens: 5, cachedTokens: 0, reasoningTokens: 0, totalTokens: 25,
  });
});

test("解析 Response 流式完成事件", () => {
  const result = extractStreamingUsage({ type: "response.completed", response: { model: "gpt-5", usage: { input_tokens: 10, output_tokens: 2, total_tokens: 12 } } });
  assert.equal(result.model, "gpt-5");
  assert.equal(result.usage.totalTokens, 12);
});

test("缓存 token 按缓存价格，其余输入按标准价格", () => {
  const value = calculateCost("gpt-5", { inputTokens: 1_000_000, cachedTokens: 200_000, outputTokens: 100_000 }, { models: { "gpt-5": { input: 1.25, cachedInput: 0.125, output: 10 } } });
  assert.equal(value, 2.025);
});
