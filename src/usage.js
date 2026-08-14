"use strict";

function number(value) {
  return Number.isFinite(Number(value)) ? Number(value) : 0;
}

function extractUsage(payload) {
  const usage = payload?.usage;
  if (!usage || typeof usage !== "object") return null;

  const inputTokens = number(usage.input_tokens ?? usage.prompt_tokens);
  const outputTokens = number(usage.output_tokens ?? usage.completion_tokens);
  const cachedTokens = number(
    usage.input_tokens_details?.cached_tokens ?? usage.prompt_tokens_details?.cached_tokens,
  );
  const reasoningTokens = number(
    usage.output_tokens_details?.reasoning_tokens ?? usage.completion_tokens_details?.reasoning_tokens,
  );

  return {
    inputTokens,
    outputTokens,
    cachedTokens,
    reasoningTokens,
    totalTokens: number(usage.total_tokens) || inputTokens + outputTokens,
  };
}

function extractStreamingUsage(event) {
  if (!event || typeof event !== "object") return null;
  if (event.type === "response.completed" || event.type === "response.incomplete") {
    return { model: event.response?.model, usage: extractUsage(event.response) };
  }
  if (event.usage) return { model: event.model, usage: extractUsage(event) };
  return null;
}

function calculateCost(model, usage, prices) {
  const rate = prices?.models?.[model];
  if (!rate || !usage) return null;

  const cached = Math.min(usage.cachedTokens, usage.inputTokens);
  const uncachedInput = usage.inputTokens - cached;
  const output = usage.outputTokens;
  return Number(((uncachedInput * number(rate.input) + cached * number(rate.cachedInput) + output * number(rate.output)) / 1_000_000).toFixed(8));
}

module.exports = { extractStreamingUsage, extractUsage, calculateCost };

