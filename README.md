# ModelMeter OpenAI 监听器

一个零依赖的本地 OpenAI API 代理与使用量面板。它将调用转发到 `api.openai.com`，并在响应完成后记录模型、输入/输出/cached/reasoning token、估算费用、状态码和时间。

它不会记录 API Key、提示词、模型回答或请求正文。所有统计数据保存在本机 `data/usage.jsonl`。

## 启动

需要 Node.js 20 或更新版本（本机现有 Node.js 22 可直接运行）。

```powershell
node src/server.js
```

打开 <http://127.0.0.1:3188> 查看统计面板。

## 接入 OpenAI 客户端

将客户端的 OpenAI Base URL 设置为：

```text
http://127.0.0.1:3188/v1
```

API Key 仍使用原来的 OpenAI Key。监听器会原样转发 `Authorization` 请求头，但不会写入磁盘或日志。

Node SDK 示例：

```js
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://127.0.0.1:3188/v1",
  apiKey: process.env.OPENAI_API_KEY,
});
```

## 支持范围

- `POST /v1/responses`：非流式和 SSE 流式；流式会读取 `response.completed` 事件的 usage。
- `POST /v1/chat/completions`：非流式和 SSE 流式；流式仅在上游返回 usage 时记录。
- 其他 OpenAI 路径会被透明转发，但不一定产生 token 统计。
- 仅监听经过本代理的请求，不会监听 ChatGPT 网页或未改 Base URL 的程序。

## 费用与预算

`src/pricing.json` 是可编辑的估算价格表，金额单位为 USD / 1M tokens。面板可设置月度预算；未知模型会显示为“待配置价格”，不会伪造费用。

估算价格不等于 OpenAI 的最终账单；折扣、Batch、工具调用、图像/音频和未来模型价格变动都可能造成差异。请定期按 OpenAI 官方价格页更新价格表。

## 开发检查

```powershell
node --test
```

