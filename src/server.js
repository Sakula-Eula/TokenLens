"use strict";

const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { Readable } = require("node:stream");
const { UsageStore } = require("./usage-store");
const { calculateCost, extractStreamingUsage, extractUsage } = require("./usage");

const host = process.env.MODELMETER_HOST || "127.0.0.1";
const port = Number(process.env.MODELMETER_PORT || 3188);
const upstream = new URL(process.env.OPENAI_UPSTREAM || "https://api.openai.com");
const root = path.resolve(__dirname, "..");
const publicDir = path.join(__dirname, "public");
const prices = JSON.parse(fs.readFileSync(path.join(__dirname, "pricing.json"), "utf8"));
const store = new UsageStore(process.env.MODELMETER_DATA_DIR || path.join(root, "data"));

function json(response, status, body) {
  response.writeHead(status, { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" });
  response.end(JSON.stringify(body));
}

function sendStatic(response, name, contentType) {
  try {
    response.writeHead(200, { "content-type": contentType, "cache-control": "no-store" });
    response.end(fs.readFileSync(path.join(publicDir, name)));
  } catch {
    json(response, 404, { error: "文件不存在" });
  }
}

function thisMonthKey(timestamp) {
  return new Date(timestamp).toISOString().slice(0, 7);
}

function summary() {
  const now = new Date();
  const month = thisMonthKey(now);
  const day = now.toISOString().slice(0, 10);
  const records = store.all();
  const aggregate = (items) => items.reduce((sum, item) => ({
    requests: sum.requests + 1,
    inputTokens: sum.inputTokens + (item.inputTokens || 0),
    outputTokens: sum.outputTokens + (item.outputTokens || 0),
    cachedTokens: sum.cachedTokens + (item.cachedTokens || 0),
    reasoningTokens: sum.reasoningTokens + (item.reasoningTokens || 0),
    totalTokens: sum.totalTokens + (item.totalTokens || 0),
    costUsd: sum.costUsd + (item.costUsd || 0),
    pricedRequests: sum.pricedRequests + (item.costUsd === null ? 0 : 1),
  }), { requests: 0, inputTokens: 0, outputTokens: 0, cachedTokens: 0, reasoningTokens: 0, totalTokens: 0, costUsd: 0, pricedRequests: 0 });
  const models = {};
  for (const item of records) {
    const key = item.model || "未知模型";
    if (!models[key]) models[key] = aggregate([]);
    const result = aggregate([models[key], item]);
    models[key] = result;
  }
  const config = store.getConfig();
  return {
    today: aggregate(records.filter((item) => String(item.timestamp).slice(0, 10) === day)),
    month: aggregate(records.filter((item) => thisMonthKey(item.timestamp) === month)),
    models,
    recent: records.slice(-30).reverse(),
    config,
    currency: prices.currency,
    startedAt: startedAt.toISOString(),
  };
}

function recordUsage({ model, endpoint, statusCode, usage }) {
  if (!usage) return;
  const costUsd = calculateCost(model, usage, prices);
  store.add({
    timestamp: new Date().toISOString(),
    provider: "openai",
    endpoint,
    model: model || "unknown",
    statusCode,
    ...usage,
    costUsd,
  });
}

function forwardHeaders(headers) {
  const result = new Headers();
  for (const [key, value] of Object.entries(headers)) {
    if (value === undefined || ["host", "connection", "content-length"].includes(key.toLowerCase())) continue;
    result.set(key, Array.isArray(value) ? value.join(", ") : value);
  }
  return result;
}

function responseHeaders(upstreamResponse) {
  const result = {};
  upstreamResponse.headers.forEach((value, key) => {
    if (!["content-encoding", "content-length", "connection", "transfer-encoding"].includes(key.toLowerCase())) result[key] = value;
  });
  return result;
}

function isStream(contentType) {
  return String(contentType || "").toLowerCase().includes("text/event-stream");
}

async function proxy(request, response) {
  const incomingUrl = new URL(request.url, `http://${request.headers.host || `${host}:${port}`}`);
  const target = new URL(incomingUrl.pathname + incomingUrl.search, upstream);
  const endpoint = incomingUrl.pathname;
  const requestModel = request.headers["x-modelmeter-model"];
  const init = {
    method: request.method,
    headers: forwardHeaders(request.headers),
    redirect: "manual",
  };
  if (!["GET", "HEAD"].includes(request.method)) {
    init.body = Readable.toWeb(request);
    init.duplex = "half";
  }

  let upstreamResponse;
  try {
    upstreamResponse = await fetch(target, init);
  } catch (error) {
    json(response, 502, { error: { message: `无法连接 OpenAI：${error.message}`, type: "proxy_connection_error" } });
    return;
  }

  const headers = responseHeaders(upstreamResponse);
  const contentType = upstreamResponse.headers.get("content-type");
  response.writeHead(upstreamResponse.status, headers);

  if (!upstreamResponse.body) {
    response.end();
    return;
  }

  if (!isStream(contentType)) {
    const body = Buffer.from(await upstreamResponse.arrayBuffer());
    response.end(body);
    if (upstreamResponse.ok && String(contentType).includes("application/json")) {
      try {
        const payload = JSON.parse(body.toString("utf8"));
        recordUsage({ model: payload.model || requestModel, endpoint, statusCode: upstreamResponse.status, usage: extractUsage(payload) });
      } catch { /* Forwarding must never fail because optional accounting parsing failed. */ }
    }
    return;
  }

  const decoder = new TextDecoder();
  let pending = "";
  const reader = upstreamResponse.body.getReader();
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      response.write(Buffer.from(value));
      pending += decoder.decode(value, { stream: true });
      const lines = pending.split(/\r?\n/);
      pending = lines.pop();
      for (const line of lines) {
        if (!line.startsWith("data:")) continue;
        const data = line.slice(5).trim();
        if (!data || data === "[DONE]") continue;
        try {
          const event = JSON.parse(data);
          const parsed = extractStreamingUsage(event);
          if (parsed?.usage) recordUsage({ model: parsed.model || requestModel, endpoint, statusCode: upstreamResponse.status, usage: parsed.usage });
        } catch { /* Individual SSE payloads may be non-JSON. */ }
      }
    }
  } finally {
    response.end();
  }
}

function readJson(request) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    request.on("data", (chunk) => {
      size += chunk.length;
      if (size > 32_768) reject(new Error("请求过大"));
      else chunks.push(chunk);
    });
    request.on("end", () => {
      try { resolve(JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}")); } catch { reject(new Error("JSON 格式无效")); }
    });
    request.on("error", reject);
  });
}

const startedAt = new Date();
const server = http.createServer(async (request, response) => {
  const pathname = new URL(request.url, `http://${request.headers.host || "localhost"}`).pathname;
  if (request.method === "GET" && pathname === "/") return sendStatic(response, "index.html", "text/html; charset=utf-8");
  if (request.method === "GET" && pathname === "/app.js") return sendStatic(response, "app.js", "text/javascript; charset=utf-8");
  if (request.method === "GET" && pathname === "/styles.css") return sendStatic(response, "styles.css", "text/css; charset=utf-8");
  if (request.method === "GET" && pathname === "/health") return json(response, 200, { status: "ok", upstream: upstream.origin });
  if (request.method === "GET" && pathname === "/api/summary") return json(response, 200, summary());
  if (request.method === "GET" && pathname === "/api/pricing") return json(response, 200, prices);
  if (request.method === "POST" && pathname === "/api/config") {
    try { return json(response, 200, store.setConfig(await readJson(request))); }
    catch (error) { return json(response, 400, { error: error.message }); }
  }
  if (pathname.startsWith("/v1/")) return proxy(request, response);
  return json(response, 404, { error: "未找到页面。OpenAI API 请使用 /v1/..." });
});

if (require.main === module) {
  server.listen(port, host, () => console.log(`ModelMeter 正在监听 http://${host}:${port}`));
}

module.exports = { server };
