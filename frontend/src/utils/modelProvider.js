const MODEL_RULES = [
  ["anthropic", /(?:^|[\s/_.:-])claude(?=$|[\s/_.:-]|\d)/],
  ["gemini", /(?:^|[\s/_.:-])gemini(?=$|[\s/_.:-]|\d)/],
  ["deepseek", /(?:^|[\s/_.:-])deepseek(?=$|[\s/_.:-]|\d)/],
  ["qwen", /(?:^|[\s/_.:-])(?:qwen|qwq)(?=$|[\s/_.:-]|\d)/],
  ["kimi", /(?:^|[\s/_.:-])(?:kimi|moonshot)(?=$|[\s/_.:-]|\d)/],
  ["doubao", /(?:^|[\s/_.:-])doubao(?=$|[\s/_.:-]|\d)/],
  ["glm", /(?:^|[\s/_.:-])(?:glm|chatglm|zhipu)(?=$|[\s/_.:-]|\d)/],
  ["minimax", /(?:^|[\s/_.:-])minimax(?=$|[\s/_.:-]|\d)/],
  ["mistral", /(?:^|[\s/_.:-])(?:mistral|mixtral|codestral|pixtral)(?=$|[\s/_.:-]|\d)/],
  ["xai", /(?:^|[\s/_.:-])(?:grok|xai)(?=$|[\s/_.:-]|\d)/],
  ["llama", /(?:^|[\s/_.:-])llama(?=$|[\s/_.:-]|\d)/],
  ["openai", /(?:^|[\s/_.:-])(?:gpt|chatgpt|o1|o3|o4|dall-e|text-embedding)(?=$|[\s/_.:-]|\d)/],
];

const PROVIDER_RULES = [
  ["anthropic", /anthropic|claude/],
  ["gemini", /google|gemini/],
  ["deepseek", /deepseek/],
  ["qwen", /alibaba|aliyun|dashscope|qwen|tongyi/],
  ["kimi", /kimi|moonshot/],
  ["doubao", /doubao|volcengine|volces/],
  ["glm", /bigmodel|chatglm|glm|zhipu/],
  ["minimax", /minimax/],
  ["mistral", /mistral/],
  ["xai", /(?:^|[\s/_.:-])xai(?:$|[\s/_.:-])|x\.ai/],
  ["llama", /llama|meta/],
  ["openai", /openai|azure/],
];

function match(value, rules) {
  const normalized = String(value || "").trim().toLowerCase();
  return rules.find(([, pattern]) => pattern.test(normalized))?.[0] || null;
}

export function getModelProvider(model, provider = "") {
  return match(model, MODEL_RULES) || match(provider, PROVIDER_RULES);
}

export const MODEL_PROVIDER_KEYS = MODEL_RULES.map(([key]) => key);
