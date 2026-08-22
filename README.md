# TokenLens

TokenLens 是一个运行在 Windows 本地的模型 API 透明代理与用量监控工具。它位于客户端与模型 Provider 之间，透传请求和响应，并把 Provider、模型、Token 用量、耗时与状态码记录到本地 SQLite 数据库。

它不会保存 Authorization、API Key、Prompt 正文或模型完整响应。

## 环境要求

- Python 3.11+
- Node.js 20+（仅用于构建 Dashboard）
- Microsoft Edge WebView2 Runtime（Windows 11 通常已预装）

## 启动

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Push-Location frontend
npm ci
npm run build
Pop-Location
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 7788
```

打开 <http://127.0.0.1:7788/dashboard> 查看 Dashboard。

## 系统托盘启动（推荐）

```powershell
.\.venv\Scripts\python.exe tray.py
```

启动后 TokenLens 常驻 Windows 右下角系统托盘，并使用 WebView2 提供原生桌面窗口：

- 单击托盘图标显示紧凑用量悬浮窗，单纯悬停不会弹出，移出后自动隐藏
- 右键菜单「打开 Dashboard」打开独立 Dashboard 桌面窗口，不启动浏览器
- 悬浮窗的固定按钮可关闭自动隐藏；设置、查看详情和全部模型会跳到桌面 Dashboard 的对应页面
- 关闭 Dashboard 窗口不会停止代理服务
- 右键菜单「打开 config.yaml」打开配置文件
- 右键菜单「退出」停止服务并退出

托盘图标取自 `assets/icon.png`；若想换图标，替换该文件即可（建议正方形、透明背景）。

## 配置 Provider

将 `config.yaml.example` 复制为 `config.yaml`，然后按实际 Provider 填写配置。每个 provider 名称也是代理路由的一部分：

```yaml
providers:
  openai:
    type: openai
    base_url: https://api.openai.com
    # api_key: sk-xxx
```

`base_url` 不应以 `/v1` 结尾。保存 Provider 后，在设置页可直接复制对应的 Harness Base URL；其固定格式为 `http://127.0.0.1:7788/<provider 名称>/v1`。将该地址填入 CC Switch、Codex、Claude Code 或其他 harness 的 Base URL。

| 协议 | Provider 类型 | Harness Base URL | harness 请求路径 |
| --- | --- | --- | --- |
| OpenAI Compatible | `openai` | `http://127.0.0.1:7788/openai/v1` | `/chat/completions` |
| OpenAI Responses | `responses` | `http://127.0.0.1:7788/responses/v1` | `/responses` |
| Anthropic Messages | `anthropic` | `http://127.0.0.1:7788/anthropic/v1` | `/messages` |


当客户端已发送相应认证头时，TokenLens 原样转发；只有客户端未发送认证头时，才使用 `config.yaml` 中的 `api_key` 回退。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest -q
Push-Location frontend
npm run build
Pop-Location
```

## 支持范围

- 统计 OpenAI Compatible 的 `/v1/chat/completions`，包括 SSE 流式请求；流式请求会自动注入 `stream_options.include_usage`。
- 统计 OpenAI Responses API 的 `/v1/responses`，包括 SSE 流式请求（usage 取自流末尾的 `response.completed` 事件）。
- 统计 Anthropic 的 `/v1/messages`，包括 SSE 流式请求。
- 其余 `/v1/*` 路径会透明转发，但不会产生 Token 用量记录。
- Dashboard 每 5 秒轮询本地统计 API。
