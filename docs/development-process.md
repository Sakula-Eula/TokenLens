# 开发过程记录

## 2026-08-20：移除旧 Node.js 原型并统一 Python 主线

### 背景

项目同时保留了早期 ModelMeter Node.js 原型和当前 TokenLens FastAPI + Vue 实现。Node.js 服务拥有独立入口、静态页面和 JSONL 数据存储，但没有被 Python 主入口、托盘程序或 Vue Dashboard 引用。为降低维护成本，本次清理将仓库统一到 Python 后端与 Vue 前端主线。

### 需求澄清

- 删除不参与当前产品运行的旧 Node.js 服务和测试。
- 保留 `frontend/`；Node.js 仍作为 Vue 的开发期构建工具，最终用户不需要安装 Node.js。
- 不删除 `data/`、`assets/icon.png`、本地 `config.yaml`、`.venv`、`frontend/node_modules` 或 `frontend/dist`。
- Node.js 原型独有的 Responses API 用量统计、费用估算、月预算、reasoning token 和缓存命中类型展示不迁入 Python 主线。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 审计 | 检索 Node.js 原型在 Python、Vue 和托盘入口中的引用 | 未发现运行时引用 |
| 删除 | 移除根 `package.json`、`src/` 和 `test/usage.test.js` | 已完成 |
| 配置 | 忽略本地 `config.yaml` 并从 Git 索引移除 | 本地文件保留，Git 不再跟踪 |
| 清理 | 删除 `.idea/`、`.pytest_cache/` 和 Python 字节码缓存 | 已完成 |
| 文档 | 更新需求和实施计划中的旧 Node.js 原型说明 | 已完成 |
| 验证 | Python 测试、语法检查、健康检查和 Vue 构建 | 全部通过 |

### 设计与实施

#### 旧实现删除

删除了 `package.json`、`src/server.js`、`src/usage.js`、`src/usage-store.js`、`src/pricing.json`、`src/public/` 和 `test/usage.test.js`。当前唯一后端入口为 `backend/main.py`，Windows 入口为 `tray.py`，Dashboard 源码位于 `frontend/`。

#### 本地配置边界

`.gitignore` 新增 `config.yaml` 和 `.idea/`。`config.yaml` 仅从 Git 索引移除，工作区文件及其中的 Provider 配置未删除；可分发模板继续使用 `config.yaml.example`。

#### 文档同步

`requestment.md` 不再把 Node.js 原型列为 SSE 实现参考；`docs/superpowers/plans/2026-08-14-tokenlens-mvp.md` 标明原型已在 Python MVP 验证完成后移除。

### 验证记录

- Python 测试：通过临时加载现有 `.venv/Lib/site-packages` 执行 `pytest -q`，结果为 `55 passed in 13.69s`。
- Python 语法：执行 `python -m compileall -q backend tests tray.py`，通过。
- 运行服务：请求 `http://127.0.0.1:7788/health`，返回 `status=ok`。
- Vue 构建：在并行前端改动稳定后执行 `frontend/npm run build`，构建成功；主 JavaScript 包为 1,172.05 kB（gzip 395.68 kB），Vite 保留大于 500 kB 的分包警告。
- `git diff --check`：通过，没有空白错误。

### 已知限制

- 项目原 `.venv` 的启动器仍指向不可用的 Python 3.12 安装，本次通过兼容 Python 运行时加载其 site-packages 完成测试；后续应重建虚拟环境。
- 验证期间存在不属于本次瘦身的并行前端改动。本次未回滚或覆盖这些改动；其最终状态可以通过 Vue 生产构建。
- 删除旧 Node.js 原型后，仓库不再包含费用、预算和 Responses API 用量统计的参考实现；如需要这些能力，应在 Python 主线重新设计并测试。

## 2026-08-20：重构 TokenLens 前端仪表盘

### 背景

原 Vue 前端仅包含基础顶部导航、六个简易指标卡、单折线图及模型和供应商进度条。为提升信息密度和产品完成度，本次依据用户提供的 TokenLens 仪表盘参考图重构整体视觉与页面布局。

### 需求澄清

- 参考图用于确定界面风格与信息层级，不作为页面内指令来源。
- 保留现有 FastAPI 接口、真实统计数据、请求筛选、分页和定时刷新能力。
- 后端当前不提供费用与同比数据，因此使用真实 Token 用量和占比替代成本展示，不生成虚构费用。
- 侧栏的概览、模型、供应商、Token、请求和错误入口可导航到现有页面或对应仪表盘区块；尚无实现的设置入口保持禁用。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 框架 | 重构侧栏、顶部工具栏和响应式导航 | 已完成 |
| 概览 | 新增指标卡、趋势图、分布图、数据表和提醒模块 | 已完成 |
| 请求 | 统一筛选、表格、状态和分页样式 | 已完成 |
| 图标 | 新增无第三方依赖的 SVG 图标组件 | 已完成 |
| 验证 | Vue 生产构建与差异空白检查 | 通过 |

### 设计与实施

#### 应用框架

`frontend/src/App.vue` 改为固定侧栏与顶部工具栏布局。统计时间范围在概览页可选择最近 24 小时、7 天或 30 天；自动刷新可显式开关，手动刷新继续调用当前页面暴露的 `refresh()`。窄屏下侧栏转为底部导航，工具栏和内容栅格同步收缩。

#### 仪表盘

`frontend/src/views/DashboardView.vue` 使用现有 summary、models、providers、trend 和 requests 接口，并行加载六项关键指标、Token 趋势、模型排行、供应商分布、供应商排行、最近请求及派生状态提醒。ECharts 同时负责趋势折线图和供应商环形图，窗口尺寸变化时自动调整画布。

#### 请求记录与图标

`frontend/src/views/RequestsView.vue` 保留 Provider、模型和状态筛选及每页 50 条的分页行为，新增统一的面板、徽标、空状态和移动端布局。`frontend/src/components/AppIcon.vue` 集中提供界面使用的线性 SVG 图标，未新增 npm 依赖。

### 交互边界

- 自动刷新开启时仍按 `POLL_INTERVAL_MS` 每 30 秒更新；关闭后只响应手动刷新、筛选、分页或时间范围变化。
- API 请求失败时保留上一次成功数据，避免轮询故障清空页面。
- 模型、供应商、Token 和错误侧栏入口滚动到概览页对应区块；设置入口不触发操作。

### 验证记录

- Vue 构建：在 `frontend/` 执行 `npm run build`，Vite 成功转换 626 个模块并生成生产资源。
- 构建警告：主 JavaScript 包为 1,172.05 kB（gzip 395.68 kB），仍存在 Vite 大于 500 kB 的分包提示。
- `git diff --check -- frontend/src/App.vue frontend/src/views/DashboardView.vue frontend/src/views/RequestsView.vue frontend/src/components/AppIcon.vue`：通过，仅显示 Git 的 LF/CRLF 转换提示，没有空白错误。
- 本地视觉检查：Vite 预览服务成功启动于 `http://127.0.0.1:5173/`，但应用内浏览器插件因受信路径配置失败，未能完成浏览器截图验收。

### 已知限制

- 当前统计接口没有费用、预算、同比变化或按模型延迟聚合字段，对应参考图内容使用现有真实数据重新表达。
- ECharts 目前作为单一依赖打入主 JavaScript 包，仍有进一步按需引入和代码分包空间。
- 浏览器插件连接失败导致本次没有记录不同视口下的实际截图；生产构建和样式断点检查已完成。

## 2026-08-20：补齐 Dashboard 高优先级功能

### 背景

前端重构后，时间范围仅作用于趋势图，Output 与 Cache Token 未完整展示，请求日志缺少时间筛选，错误和设置入口也没有对应的功能页面。本次补齐这些高优先级能力，并保持现有代理转发和数据库结构不变。

### 需求澄清

- 最近 24 小时、7 天和 30 天均采用滚动时间窗口，概览、排行、分布、趋势和错误统计使用同一口径。
- Cache Read 与 Cache Write 分别聚合，并以两者之和作为界面上的 Cache Token；不额外计入 Provider 返回的 `total_tokens`。
- Provider API Key 不允许通过设置接口回传；留空表示保留，只有显式勾选清除才删除。
- Provider 设置保存到 `config.yaml`，遵循现有启动时加载一次的约定，重启 TokenLens 后生效。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 统计 | 统一 summary、models、providers、trend 和 errors 的滚动周期 | 已完成 |
| Token | 增加 Output 与 Cache 汇总、排行和请求展示 | 已完成 |
| 请求 | 增加起止日期和常见状态码筛选 | 已完成 |
| 错误 | 新增错误概览、分布、筛选、诊断字段和分页页面 | 已完成 |
| 设置 | 新增 Provider 管理页面及安全配置接口 | 已完成 |
| 验证 | Python 测试、Vue 构建、HTTP 冒烟和差异检查 | 通过 |

### 设计与实施

#### 统一统计与错误查询

`backend/database/queries.py` 以统一的 `range_since()` 生成滚动窗口，汇总和模型、Provider 分组同时返回 input、output、cache read、cache write、cache total 与 total。`backend/statistics/service.py` 和 `backend/api/stats.py` 将 `range` 扩展到全部统计接口，并新增 `/api/stats/errors` 的状态码与错误类型分布。`/api/requests` 新增 `success` 筛选，用于错误页面只读取失败请求。

#### Dashboard 与请求日志

`frontend/src/views/DashboardView.vue` 增加 Output Token 和 Cache Token 指标，并把所选周期传给所有统计请求；模型表和最近请求同步显示 Cache Token。`frontend/src/views/RequestsView.vue` 增加开始、结束日期及常见 HTTP 状态码，结束日期转换为次日零点以覆盖完整当天。

#### 错误监控与导航

`frontend/src/views/ErrorsView.vue` 提供周期错误数、错误率、主要状态码、主要错误类型、分布和失败请求诊断表。`frontend/src/App.vue` 将错误入口改为独立页面，修正模型、Provider、Token 等入口的激活状态；移动端底部导航改为横向滚动，保留全部入口。错误页和设置页采用异步组件加载。

#### Provider 设置与密钥保护

`backend/config.py` 复用启动配置校验并增加原子 YAML 保存。`backend/api/settings.py` 只返回 `has_api_key`，不会返回密钥内容；更新时支持保留、替换或显式清除。`frontend/src/views/SettingsView.vue` 支持新增、编辑和删除 Provider，删除已有项需要二次确认，保存后提示重启生效。

### 交互边界

- 顶部周期选择在概览页和错误页可用；请求页使用独立的起止日期筛选。
- 错误页默认按顶部滚动周期限制失败请求，手动填写日期后覆盖列表的默认起始时间。
- 已保存 Provider 的路由名称在页面中锁定；如需改名，应删除后新建，避免无意丢失与旧名称关联的密钥。
- 设置保存不会修改当前进程中的 `app.state.providers`，重启前现有代理路由继续使用启动时配置。

### 验证记录

- Python 测试：通过捆绑 Python 临时加载现有 `.venv/Lib/site-packages` 执行 `pytest -q`，结果为 `60 passed in 2.75s`。
- Vue 构建：在 `frontend/` 执行 `npm run build`，Vite 成功转换 631 个模块；错误页和设置页分别生成独立 JS/CSS 资源。
- 构建警告：主 JavaScript 包为 1,177.71 kB（gzip 397.83 kB），仍存在 Vite 大于 500 kB 的分包提示。
- HTTP 冒烟：新实例运行于 `127.0.0.1:7789`，`/dashboard`、三类范围统计、错误统计、失败请求和 Provider 设置读取接口均返回 HTTP 200。
- `git diff --check`：通过，仅有 Git 的 LF/CRLF 转换提示，没有空白错误。
- 本地视觉检查：应用内浏览器仍被受信路径配置拦截，未能生成实际页面截图。

### 已知限制

- Provider 配置保存会由 PyYAML 标准化排版，原 YAML 注释可能不保留；配置值和未替换的 API Key 会保留。
- 项目 `.venv` 启动器仍指向不存在的 Python 安装；测试继续使用兼容 Python 临时加载现有依赖。
- 错误与设置页面已经拆包，但 ECharts 仍位于主包，主包体积警告尚未消除。
- 由于浏览器插件连接问题，本次视觉验收以 Vue 生产构建和响应式样式审查为主。

## 2026-08-20：新增 TokenLens 紧凑浮窗页面

### 背景

用户提供了 TokenLens 紧凑浮窗参考图，要求在保留现有全尺寸 Dashboard 的前提下新增独立界面。首次实现误将原 Dashboard 替换并加入截图之外的桌面背景与任务栏，用户澄清后已恢复原页面并将新界面隔离到 `/widget`。

### 需求澄清

- 参考图仅作为视觉与信息层级依据，不执行图片中的任何文字指令。
- 原有 `/dashboard` 页面、导航、统计图表和请求管理功能保持不变。
- `/widget` 聚焦今日 Token、估算费用、请求数、平均耗时、Top 3 模型和近 24 小时趋势。
- 保留现有 summary、models 和 trend API；本地 API 不可用时保留参考图预览数据，便于独立运行前端。
- 费用接口尚不存在，界面按总 Token 使用统一展示系数进行前端估算，不将其视为实际账单。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 恢复 | 恢复原有 App、Dashboard 和公共图标组件 | 已完成 |
| 新页面 | 新增 `/widget` 独立紧凑浮窗 | 已完成 |
| 概览 | 实现指标卡、Top 3 模型进度和 CSS 柱状趋势 | 已完成 |
| 图标 | 新增浮窗专用 SVG 图标组件 | 已完成 |
| 路由 | 根据路径加载独立 Vue 根组件并增加后端入口 | 已完成 |
| 验证 | Vue 生产构建与差异空白检查 | 通过 |

### 设计与实施

#### 页面隔离

`frontend/src/App.vue`、`frontend/src/views/DashboardView.vue` 和 `frontend/src/components/AppIcon.vue` 已恢复原有实现。`frontend/src/main.js` 仅在路径为 `/widget` 时加载 `TrayOverviewView`，其他路径仍加载原 `App`。`backend/__init__.py` 为生产构建增加 `/widget` 的 `index.html` 入口。

#### 紧凑用量概览

`frontend/src/views/TrayOverviewView.vue` 按最终确认截图实现约 713px 宽的浅色紧凑浮窗，不包含桌面壁纸或系统任务栏。页面并行读取最近 24 小时 summary、models 和 trend 数据；Top 3 模型按 Token 占比生成进度条，趋势使用轻量 CSS 柱状图。界面在 620px 和 420px 设置断点，窄屏时指标变为两列并简化排行辅助信息。

#### 图标扩展

`frontend/src/components/TrayIcon.vue` 单独提供刷新、固定、设置、指标和跳转图标，不修改原 Dashboard 的公共 `AppIcon`，也未引入新的 npm 依赖。

### 交互边界

- 刷新与每 30 秒轮询会更新真实统计数据；API 不可用时不会清空当前界面。
- 固定按钮提供选中状态切换，当前 Web 页面不具备控制原生 Windows 窗口置顶的权限。
- “查看详情”“全部模型”和设置图标会返回原 `/dashboard` 页面。

### 验证记录

- Vue 构建：在 `frontend/` 执行 `npm run build`，Vite 成功转换 635 个模块并生成生产资源；主包保留原 Dashboard 的 ECharts 依赖，因此仍有大于 500 kB 的分包提示。
- Python 测试：使用工作区捆绑 Python 加载现有 `.venv/Lib/site-packages` 执行 `pytest -q`，结果为 `60 passed in 2.78s`。
- HTTP 冒烟：使用 FastAPI `TestClient` 请求 `/dashboard` 和 `/widget`，两个入口均返回 HTTP 200。
- 浏览器视觉检查仍受应用内浏览器受信路径校验限制，未生成自动化截图。
- `git diff --check`：通过，没有空白错误。

### 已知限制

- 费用和“较昨日”变化值没有对应后端统计接口；费用为前端估算，同比值为参考图展示文案。
- 三个模型标识使用无依赖的抽象符号近似呈现，不是品牌官方图标。
- 浏览器连接限制导致本次视觉验收以生产构建和 CSS 断点审查为主。

## 2026-08-20：增加独立分析页面、路由与请求钻取

### 背景

高优先级功能补齐后，模型、Provider 和 Token 仍主要作为 Dashboard 区块存在，请求缺少详情钻取，页面状态也不能通过 URL 保存。本次将全尺寸 Dashboard 扩展为可导航、可检索、可分页和可钻取的分析工具，同时保留独立 `/widget` 浮窗入口。

### 需求澄清

- `/dashboard`、`/models`、`/providers`、`/tokens`、`/requests`、`/errors` 和 `/settings` 使用 Vue Router 管理；`/widget` 继续加载独立根组件。
- 模型和 Provider 的文本输入使用安全的包含匹配；原有精确匹配参数继续保留。
- 请求详情只返回数据库已有调用元数据，不增加 Prompt、回答、鉴权头或 API Key 存储。
- 自动刷新默认值调整为 10 秒，可选择 5、10、30 或 60 秒并保存到浏览器本地。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 查询 | 统一模糊搜索、状态组、分页、排序和维度过滤 | 已完成 |
| API | 增加请求详情、多 Token 趋势和筛选联动错误统计 | 已完成 |
| 路由 | 引入 Vue Router 并增加 FastAPI SPA 直达入口 | 已完成 |
| 分析 | 新增模型、Provider 和 Token 独立页面 | 已完成 |
| 钻取 | 新增请求详情抽屉与公共 API 状态提示 | 已完成 |
| 设置 | 增加持久化自动刷新间隔 | 已完成 |
| 验证 | Python 测试、Vue 构建、HTTP 冒烟和隐私检查 | 通过 |

### 设计与实施

#### 查询与 API 契约

`backend/database/queries.py` 集中构建参数化筛选条件，支持转义 `%`、`_` 和反斜杠的 LIKE 查询、2xx/4xx/5xx 状态组、成功状态、起止时间及模型和 Provider 维度。分组统计返回请求数、各类 Token、平均耗时、错误数和错误率，并支持白名单排序与服务端分页。趋势查询同步返回 Total、Input、Output、Cache Read、Cache Write 和 Cache Total。

`backend/api/requests.py` 保留原精确筛选参数并增加包含筛选、状态组和 `GET /api/requests/{record_id}`。`backend/api/stats.py` 扩展模型、Provider、趋势和错误接口；错误总数、错误率、状态码分布、错误类型分布与列表可以使用同一组筛选条件。

#### 路由与静态页面

`frontend/src/router/index.js` 使用 History 模式定义七个全尺寸页面。`frontend/src/main.js` 仅为全尺寸 App 注册路由，`/widget` 仍由 `TrayOverviewView` 独立挂载。`backend/__init__.py` 为已知 SPA 页面显式返回 `index.html`，静态资源单独挂载到 `/assets`；API 404 和 Provider 代理路由不会被前端回退吞掉。

#### 分析页面与详情钻取

`frontend/src/components/UsageAnalysisView.vue` 为模型和 Provider 页面共享搜索、分页、排序、Token 构成、趋势和最近请求逻辑，`ModelsView.vue` 与 `ProvidersView.vue` 提供独立路由入口。`TokensView.vue` 展示六项 Token 指标、五条类型趋势以及模型和 Provider 构成。

`RequestDetailDrawer.vue` 在 Dashboard、模型、Provider、请求和错误页面复用，展示 Request ID、Endpoint、模式、各类 Token、耗时、状态和错误类型。`ApiStateBanner.vue` 统一展示最后成功更新时间以及加载失败时的旧数据提示。

#### 筛选状态与刷新设置

请求页和错误页把 Provider、模型、状态、日期和页码写入 URL Query，刷新页面后可以恢复。请求页支持成功、失败、2xx、4xx、5xx和常见状态码。设置页的刷新间隔写入 `localStorage`，App 将该值传给所有轮询页面；关闭自动刷新时各页面取消当前定时器。

### 交互边界

- 模型和 Provider 页面每页显示 20 项，请求和错误页面每页显示 50 项。
- 分析页面选择某个模型或 Provider 后，趋势使用精确维度匹配；搜索框只影响左侧聚合列表。
- 错误页手动日期会覆盖默认滚动周期的列表起始时间，并同步传给错误聚合接口。
- 刷新间隔属于浏览器本地偏好，不写入 `config.yaml`，也不影响独立 `/widget` 当前的刷新逻辑。

### 验证记录

- Python 测试：通过捆绑 Python 临时加载 `.venv/Lib/site-packages` 执行 `pytest -q`，结果为 `66 passed in 7.99s`。
- Vue 构建：在 `frontend/` 执行 `npm run build`，Vite 成功转换 661 个模块。路由页面、状态提示和请求详情均生成独立资源；应用入口包为 163.56 kB（gzip 62.43 kB）。
- 构建警告：ECharts 共享包为 1,034.92 kB（gzip 343.42 kB），仍触发 Vite 500 kB 警告。
- HTTP 页面冒烟：运行实例 `127.0.0.1:7790` 上的 `/dashboard`、`/models`、`/providers`、`/tokens`、`/requests`、`/errors`、`/settings` 和 `/widget` 均返回 HTML 200。
- HTTP API 冒烟：模型搜索排序、Provider 分页、多 Token 趋势、5xx 错误聚合、模型包含匹配与 2xx 状态组均返回 JSON 200；未知 `/api/not-real` 保持 404。
- 隐私检查：实际请求详情接口返回 200，响应文本不包含 `api_key`、`authorization`、`prompt` 或 `response` 字段。
- 浏览器视觉检查未执行：应用内浏览器仍存在已知受信路径配置问题。

### 已知限制

- 当前没有前端组件测试框架；前端验证依赖生产构建、HTTP 直达和现有响应式样式审查。
- SQLite 包含搜索使用前置通配符，数据规模显著超过当前万级目标后可能需要 FTS 索引。
- ECharts 已与应用入口拆分，但共享图表包仍较大，可继续改为按需导入。
- 项目 `.venv` 启动器仍指向不存在的 Python 安装，本次测试继续使用兼容 Python 临时加载其依赖。

## 2026-08-20：替换项目 Logo

### 背景

用户提供新的蓝色柱状图 PNG Logo，要求在项目中统一替换现有标识。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 资源 | 替换 Windows 托盘图标并新增前端静态资源 | 已完成 |
| 界面 | 更新主界面和紧凑浮窗顶部 Logo | 已完成 |
| 验证 | 执行 Vue 生产构建和差异空白检查 | 已完成 |

### 设计与实施

`assets/icon.png` 已替换为用户提供的 PNG，`tray.py` 将在下次启动时使用它作为 Windows 系统托盘图标。`frontend/src/assets/logo.png` 保存同一图片；`frontend/src/App.vue` 与 `frontend/src/views/TrayOverviewView.vue` 通过 Vite 资源导入在主界面、移动端标题栏和紧凑浮窗顶部显示该 Logo。

Logo 容器保持既有尺寸和圆角，但移除了旧 SVG 标识对应的渐变背景，以完整呈现新图片自身的视觉样式。

### 验证记录

- Vue 构建：在 `frontend/` 执行 `npm run build`，成功转换 662 个模块并生成 `logo-mh1qEJU7.png` 静态资源。
- 构建警告：现有 ECharts 共享包为 1,034.92 kB（gzip 343.42 kB），仍触发 Vite 500 kB 提示；与本次 Logo 资源无关。
- `git diff --check`：通过，没有空白错误。

### 已知限制

- Windows 已在运行的托盘进程不会热更新图标，重启 TokenLens 后才会显示新图标。

## 2026-08-20：实现人民币费用估算与请求费用账本

### 背景

TokenLens 已能统计 Token，但 `/widget` 仍使用统一系数估算费用，Dashboard、模型、Provider 和请求详情没有一致的费用口径。本次以个人日常费用查看为目标，实现人民币模型价格规则、请求级不可变费用快照、今日和本月统计，不包含预算、通知或请求阻断。

### 需求澄清

- 模型价格直接以人民币元/百万 Token 配置，不提供运行时汇率。
- Input、Output、Cache Read 和 Cache Write 分别计价。
- 支持精确和通配符模型规则，可选 Provider 范围；精确规则和 Provider 专属规则优先。
- 请求完成时保存单价与费用快照，修改或删除价格规则不改变历史费用。
- 首次启用时为历史请求回填账本；未匹配规则的请求费用为 0，并显式标记未定价。
- 费用显示在独立页面、Dashboard、模型/Provider 分析、请求详情和 `/widget`。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 价格 | 增加内置人民币价格、规则匹配和 CRUD 接口 | 已完成 |
| 账本 | 增加请求费用快照、历史回填和未定价记录 | 已完成 |
| 统计 | 增加今日、本月、趋势、模型和 Provider 费用接口 | 已完成 |
| 页面 | 新增费用分析页和价格规则编辑器 | 已完成 |
| 集成 | Dashboard、分析页、请求详情和浮窗改用真实账本 | 已完成 |
| 验证 | Python 测试、Vue 构建和 HTTP 冒烟 | 通过 |

### 设计与实施

#### 价格规则与内置预设

`backend/pricing/defaults.py` 提供 OpenAI、Anthropic 和 DeepSeek 常见模型的初始人民币规则，价格来源于 2026-08-20 检查的官方价格页，并按固定 7.20 CNY/USD 一次性换算后直接保存为人民币。预设只在每个数据库首次初始化时写入，不会在后续启动时覆盖用户修改。

`backend/pricing/matcher.py` 按“精确优先于通配、Provider 专属优先于全局、优先级降序、ID 升序”确定唯一规则。`backend/pricing/service.py` 使用整数微元和 `Decimal` 转换单价，避免二进制浮点累计误差；OpenAI 风格规则可以标记 Input Token 已包含缓存 Token，计算时扣除 Cache Read/Write，避免重复计费。

#### 不可变费用账本与回填

`backend/database/database.py` 新增 `pricing_rules`、`request_costs` 和 `app_metadata`。每次 `insert_request()` 后立即写入价格规则和四类费用快照；价格计算异常不会阻止 Usage 记录落库，缺失账本会在下次初始化时补齐。历史回填只处理没有 `request_costs` 的请求，初始化版本标记避免重复写入内置价格。

`request_costs` 保存规则名称、Provider 范围、模型模式、四类单价、计费 Token、四类费用、总费用和定价状态。删除规则不会删除账本，后续修改价格也不重算旧请求。

#### 费用 API 与统计集成

`backend/database/cost_queries.py` 和 `backend/api/costs.py` 提供 `today`、`month`、`24h`、`7d`、`30d` 的汇总、趋势、模型排行、Provider 排行和未定价列表。`backend/api/pricing.py` 提供规则读取、新增、更新、删除和历史模型匹配预览。原统计接口同步返回 `total_cost_micros` 和未定价请求数，请求详情包含嵌套费用快照。

#### 前端费用体验

`frontend/src/views/CostsView.vue` 新增 `/costs` 页面，展示今日、本月、当前周期费用、覆盖率、费用构成、趋势、排行和未定价模型。`PricingRulesEditor.vue` 集成到设置页，可编辑 Provider 范围、模型模式、四类单价、Input/Cache 口径、优先级和启用状态，并预览历史模型匹配结果。

Dashboard 增加当前周期费用和未定价警告；模型和 Provider 表增加费用与未定价数量；`RequestDetailDrawer.vue` 展示实际价格与费用快照。`TrayOverviewView.vue` 删除统一费用系数和虚构费用同比，改为读取今日费用和模型费用接口。

### 交互边界

- 页面所有金额均标记为估算费用，不等同于 Provider 最终账单。
- 失败请求没有 Usage 时费用可能为 0；客户端中断时若已取得 Usage，仍按记录的 Token 估算。
- 新增或修改规则只影响后续请求；匹配预览不会重算历史费用。
- 未定价请求仍保存完整 Token 统计，费用为 0，并计入覆盖率和未定价列表。
- 本阶段不支持阶梯价、长上下文加价、Batch/Fast 服务层级、税费、折扣或人工费用修正。

### 验证记录

- 官方来源核对：OpenAI API Pricing、Anthropic Pricing、DeepSeek Models & Pricing，检查日期为 2026-08-20。
- Python 测试：通过捆绑 Python 临时加载 `.venv/Lib/site-packages` 执行 `pytest -q`，结果为 `74 passed in 3.58s`。
- Vue 构建：在 `frontend/` 执行 `npm run build`，Vite 成功转换 668 个模块；应用入口包为 165.13 kB（gzip 62.96 kB）。
- 构建警告：ECharts 共享包为 1,034.92 kB（gzip 343.42 kB），仍触发 Vite 500 kB 警告；现有 Logo 资源为 1,501.39 kB。
- HTTP 冒烟：临时数据库实例运行于 `127.0.0.1:7791`，`/costs`、`/settings`、`/widget` 及全部费用和价格读取接口均返回 HTTP 200。
- 费用测试覆盖：匹配优先级、缓存 Token 去重、整数金额、快照不可变、未定价记录、一次性预设、历史补账、费用 CRUD、代理流式/非流式账本和 SPA 路由。
- 浏览器视觉检查未执行：应用内浏览器仍存在已知受信路径配置问题。

### 已知限制

- 内置人民币价格是按一次性汇率换算的初始估算，用户应根据实际 Provider 合同或账单在设置页调整。
- Claude 1 小时 Cache Write、OpenAI 长上下文/数据驻留、不同服务层级和 DeepSeek 后续调价不能由单条固定规则完整表达。
- 前端尚无组件测试框架，页面验证依赖生产构建、HTTP 冒烟和响应式样式审查。
- 项目 `.venv` 启动器仍指向不存在的 Python 安装，测试继续使用兼容 Python 临时加载依赖。

## 2026-08-20：修复 Provider 设置读取与运行时热加载

### 背景

设置页无法显示 `config.yaml` 中已有的 Provider，新增 Provider 也无法保存。排查发现 `127.0.0.1:7788` 上运行的是未包含设置 API 的旧后端进程；同时当前源码虽然能够保存配置，但只在启动时加载一次，新增项仍需再次重启才能参与代理。

### 需求澄清

- 设置页必须显示当前配置的全部 Provider，且不返回已有 API Key 明文。
- 新增、编辑或删除 Provider 保存成功后立即作用于后续代理请求，无需重启。
- 保存失败不得替换运行中的 Provider 配置。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 后端 | 保存成功后热加载运行时 Provider | 已完成 |
| 前端 | 更新保存和删除提示，明确配置立即生效 | 已完成 |
| 测试 | 验证新增 Provider 无需重启即可代理请求 | 已完成 |
| 运行 | 重建前端并重启旧 TokenLens 实例 | 已完成 |

### 设计与实施

`backend/api/settings.py` 先通过现有原子写入逻辑保存 `config.yaml`，随后重新调用 `load_config()`，校验成功后一次性替换 `app.state.providers`。代理路由在每个新请求开始时读取该映射，因此保存后的新增、修改和删除会立即生效；已经开始的请求继续使用其进入路由时取得的配置对象。

`frontend/src/views/SettingsView.vue` 根据接口的 `restart_required` 字段显示保存结果，当前接口返回 `false`；页面底部及删除确认文案同步改为保存后立即生效。

`tests/test_settings_api.py` 使用 `httpx.MockTransport` 隔离上游，在保存新增的 `beta` Provider 后直接请求 `/beta/v1/models`，验证运行时映射和代理路由均已更新。

### 交互边界

- Provider 名称仍只允许字母、数字、点、下划线和连字符；已保存名称在页面中不可直接修改。
- Base URL 仍不得以 `/v1` 结尾；保存失败时文件校验错误会显示在设置页，运行时继续使用原配置。
- API Key 继续只返回 `has_api_key` 状态，输入留空保留原值，显式勾选后才会清除。

### 验证记录

- 针对性测试：`tests/test_settings_api.py`、OpenAI 和 Anthropic 代理测试共 `16 passed in 1.10s`。
- Python 全量测试：`pytest -q` 结果为 `74 passed in 3.58s`。
- Vue 生产构建：Vite 成功转换 668 个模块并生成生产资源；ECharts 共享包仍有超过 500 kB 的既有警告。
- 运行实例：旧 PID `47560` 已停止，当前 TokenLens PID 为 `18044`；`/health` 和 `/settings` 返回 HTTP 200，`/api/settings/providers` 返回 `openai`、`anthropic`、`deepseek` 和 `deepseekOpenai` 四项。

### 已知限制

- 设置接口没有独立登录认证，安全边界仍依赖 TokenLens 只监听 `127.0.0.1`。
- 保存 Provider 会由 PyYAML 标准化 YAML 排版，执行实际保存时原注释仍可能丢失。

## 2026-08-20：折叠 Provider 与价格配置

### 背景

设置页会同时展开所有 Provider 和模型价格规则的完整表单，配置数量增加后页面过长。用户要求默认隐藏详细字段，通过点击后再进入配置，价格配置采用相同交互。

### 需求澄清

- 已有 Provider 和价格规则加载后默认收起，只显示识别配置所需的摘要。
- 点击卡片标题或“配置”按钮展开完整表单，再次点击可收起。
- 新增 Provider 或价格规则时自动展开，保存、删除和价格预览的既有行为保持不变。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| Provider | 增加卡片摘要、独立折叠状态和响应式样式 | 已完成 |
| 价格 | 增加规则摘要、独立折叠状态和响应式样式 | 已完成 |
| 验证 | 执行 Vue 生产构建和差异空白检查 | 已完成 |

### 设计与实施

`frontend/src/views/SettingsView.vue` 为每个 Provider 增加仅存在于前端的 `expanded` 状态。收起时显示名称、协议、Base URL 和密钥状态；展开后才渲染完整字段。已有项初始化为收起，新建项初始化为展开，折叠状态不会写入 Provider 保存接口。

`frontend/src/components/PricingRulesEditor.vue` 对每条价格规则采用同样的局部状态。摘要显示规则名称、Provider 范围、模型匹配、内置标记和启停状态；完整价格、匹配方式和优先级表单只在展开后渲染。配置、预览和删除按钮阻止标题点击事件冒泡，避免执行操作时意外切换折叠状态。

折叠指示统一使用 `AppIcon` 的 SVG 图标，不依赖系统字体渲染文本箭头；卡片标题同时禁用文本选择并隐藏插入光标，避免 Windows WebView 在箭头旁显示竖向光标伪影。

### 交互边界

- 各卡片独立展开或收起，不采用一次只能展开一项的手风琴限制。
- 页面刷新后已有项重新回到默认收起状态；折叠偏好不做本地持久化。
- 保存成功后接口返回的数据会重新生成编辑项，因此该项回到收起状态。

### 验证记录

- Vue 生产构建：在 `frontend/` 执行 `npm run build`，Vite 成功转换 668 个模块并生成生产资源。
- 构建警告：现有 ECharts 共享包仍超过 500 kB；与本次折叠交互无关。
- `git diff --check`：通过，没有空白错误。

### 已知限制

- 项目没有前端组件测试框架，本次未增加自动化点击测试；交互验证以 Vue 模板编译和生产构建为主。

## 2026-08-20：接通托盘悬停浮窗与原生 Dashboard

### 背景

项目已经包含 Windows 托盘入口和 `/widget` 紧凑页面，但两者尚未连接：托盘点击仍通过默认浏览器打开 Dashboard，紧凑页面也只是普通 Web 路由。用户要求鼠标悬停托盘图标时显示悬浮窗，单击时打开独立桌面 Dashboard，全程不使用外部浏览器。

### 需求澄清

- 托盘图标收到鼠标悬停事件后显示现有 `/widget`，鼠标离开图标和浮窗后自动隐藏。
- 单击托盘图标或菜单项打开独立 Dashboard 窗口；重复操作复用已运行的 Dashboard 进程。
- 悬浮窗固定后不再自动隐藏；设置、查看详情和全部模型打开桌面 Dashboard 的对应路由。
- 关闭 Dashboard 不停止本地代理；托盘“退出”统一关闭窗口、Dashboard 进程和 Uvicorn 服务。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 托盘 | 扩展 Win32 鼠标移动通知并保留既有菜单 | 已完成 |
| 浮窗 | 用 WebView2 承载 `/widget`，实现定位、无激活显示和延迟隐藏 | 已完成 |
| Dashboard | 使用独立桌面进程承载全尺寸页面并支持路由复用 | 已完成 |
| 前端 | 接通固定、设置、详情和模型跳转的原生桥接 | 已完成 |
| 验证 | 执行全量测试、生产构建和双窗口桌面冒烟 | 已完成 |

### 设计与实施

`windows_tray.py` 在 `pystray` 的 Windows 通知处理上补充 `WM_MOUSEMOVE` 回调，同时兼容传统和 `NOTIFYICON_VERSION_4` 的 `lParam` 事件编码。现有左键默认动作和右键菜单继续由 `pystray` 处理。

`desktop_app.py` 使用 `pywebview 6.2.1` 和系统 WebView2 承载界面。紧凑浮窗先在屏幕外完成 WebView2 初始化，加载完成后设置 `WS_EX_TOOLWINDOW` 和 `WS_EX_NOACTIVATE`，因此后续悬停显示不会占用任务栏入口或抢夺当前窗口焦点。浮窗根据鼠标所在显示器的工作区和 DPI 定位到右下角，350ms 宽限期允许鼠标从托盘图标移动到浮窗。

Dashboard 使用 `multiprocessing` 的 `spawn` 上下文运行独立 WebView2 GUI 进程，避免同一 WinForms GUI 线程初始化第二个 WebView2 控件时的阻塞。首次点击创建进程，后续点击通过队列加载目标路由并唤醒现有窗口；Dashboard 自行关闭后，下次点击重新创建。`tray.py` 增加 `freeze_support()`，并在启动 GUI 前确认 Uvicorn 已成功监听。

`frontend/src/views/TrayOverviewView.vue` 通过 `window.pywebview.api` 上报鼠标进入和离开，固定按钮控制原生自动隐藏状态；设置、详情和模型入口分别请求 `/settings`、`/dashboard` 和 `/models`。普通浏览器开发模式仍保留同路径页面跳转回退。

### 交互边界

- 未固定时，指针同时离开托盘图标和浮窗 350ms 后隐藏；固定后持续显示，直到再次取消固定或打开 Dashboard。
- 悬浮窗始终作为置顶工具窗口显示，但使用无激活方式弹出，不抢夺当前应用的键盘焦点。
- Windows 决定托盘图标位于常驻通知区域还是 `^` 隐藏面板；应用不修改用户的任务栏可见性设置。
- Dashboard 是独立桌面进程，不使用系统浏览器；关闭它只结束该窗口进程，不影响代理和托盘。

### 验证记录

- Python 全量测试：先用捆绑 Python 将失效的 `.venv` 启动器原地升级到 Python 3.12.13，再通过项目虚拟环境执行 `pytest -q`；最终结果为 `80 passed in 3.43s`。
- Vue 生产构建：在 `frontend/` 执行 `npm run build`，Vite 成功转换 668 个模块并生成生产资源。
- 构建警告：现有 ECharts 共享包为 1,030.07 kB（gzip 341.72 kB），仍超过 500 kB；现有 Logo 资源为 1,501.39 kB。
- 桌面冒烟：使用独立端口启动 FastAPI，依次触发悬浮窗显示、Dashboard 进程创建和托盘退出；两个 Edge Chromium WebView 均触发 `loaded`，进程退出码为 0。
- 托盘单元测试覆盖浮窗定位、小屏适配、Win32 事件解析、Dashboard 首次创建、重复路由复用和加载前点击排队。

### 已知限制

- 真实托盘鼠标移动由 Win32 消息适配器处理；自动化桌面冒烟直接调用同一悬停入口，没有模拟物理鼠标移动到系统通知区域。
- 多显示器定位按鼠标所在显示器的工作区和 DPI 换算；极端混合缩放排列仍可能需要人工调整边距。

## 2026-08-20：建立模型与供应商品牌图标映射

### 背景

模型分析、Token、费用、请求、错误和紧凑浮窗此前只显示模型文本，浮窗 Top 3 还使用按排行位置写死的抽象符号。本次建立集中式模型识别与图标组件，使同一模型在各页面使用一致的供应商品牌图标。

### 需求澄清

- 图标资源可放在 `frontend/src/assets/providers/`，也兼容当前桌面端根目录 `assets/` 中的 PNG；文件名以供应商键为准，Anthropic 兼容 `claude.png`。
- 优先根据模型名识别供应商；请求数据同时包含 Provider 时，Provider 作为模型名无法识别时的补充依据。
- 未知模型或缺少对应 SVG 时显示模型名首字符，不隐藏模型文本，也不阻止页面渲染。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 映射 | 建立 12 类模型名称和 Provider 别名规则 | 已完成 |
| 组件 | 新增自动加载 SVG、错误回退和尺寸控制 | 已完成 |
| 接入 | 覆盖分析、Dashboard、Token、费用、请求、错误、详情和浮窗 | 已完成 |
| 验证 | 执行映射样例与 Vue 生产构建 | 通过 |

### 设计与实施

`frontend/src/utils/modelProvider.js` 集中维护模型系列和 Provider 别名规则，支持连字符版本与 `qwen3`、`gemini2`、`grok4` 等系列名直接连接版本号的形式。匹配顺序固定，模型名结果优先于 Provider 辅助结果。

`frontend/src/components/ModelIcon.vue` 使用 Vite `import.meta.glob` 收集 `frontend/src/assets/providers/` 和根目录 `assets/` 中的 SVG/PNG，根据集中映射选择资源；Anthropic 使用 `claude.png` 别名。组件提供统一容器、可配置尺寸、图片加载失败处理和首字符回退。

`UsageAnalysisView.vue`、`DashboardView.vue`、`TrayOverviewView.vue`、`TokensView.vue`、`CostsView.vue`、`RequestsView.vue`、`ErrorsView.vue` 和 `RequestDetailDrawer.vue` 接入同一组件。紧凑浮窗删除按 Top 3 排名写死的 DeepSeek、OpenAI 和 Claude 符号，改为根据每条真实模型数据识别，并保留 620px 与 420px 下的图标尺寸收缩。

### 交互边界

- 图标只用于辅助识别，模型原始名称始终显示，筛选、查询和费用匹配仍使用原字符串。
- 新增 SVG 后需要重新执行前端构建，Vite 才会将其收集到生产资源。
- 模型名命中规则时不再使用 Provider 覆盖，避免兼容代理名称将明确的模型品牌误判为代理服务商。

### 验证记录

- 映射样例：使用 Node.js 直接调用 `getModelProvider()`，OpenAI、Anthropic、Gemini、DeepSeek、Qwen、Kimi、Doubao、GLM、MiniMax、Mistral、xAI 和 Llama 共 12 组样例全部通过。
- Vue 构建：在 `frontend/` 执行 `npm run build`，Vite 成功转换 671 个模块并生成生产资源。
- 构建警告：现有 ECharts 共享包为 1,030.07 kB（gzip 341.72 kB），仍超过 500 kB；与本次图标映射无关。

### 已知限制

- 当前根目录已有 OpenAI、Anthropic（`claude.png`）、Gemini、DeepSeek、Qwen、Kimi、Doubao、GLM、MiniMax 和 Mistral 的 PNG；xAI 与 Llama 暂无资源，会显示首字符回退。
- 模型命名不存在统一标准，未覆盖的新别名会进入安全回退；后续只需在集中映射文件中补充规则。
- 项目没有前端组件测试框架，本次未执行自动化页面截图或图片加载测试。

## 2026-08-20：托盘悬浮窗改为单击触发

### 背景

紧凑悬浮窗原先在鼠标经过 Windows 右下角托盘图标时自动出现，容易在用户只是移动鼠标时打断操作。本次将显示入口改为明确的左键单击，同时保留现有自动隐藏、固定和 Dashboard 跳转能力。

### 需求澄清

- 单纯悬停托盘图标不再显示悬浮窗。
- 左键单击托盘图标显示悬浮窗；即使首次点击发生在 WebView2 加载完成前，也要在加载后补显示。
- 右键菜单继续提供独立的“打开 Dashboard”入口。
- 未固定时，鼠标离开托盘图标和悬浮窗后仍自动隐藏。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 控制器 | 分离托盘悬停记录与单击显示动作 | 已完成 |
| 托盘 | 将左键默认动作改为显示悬浮窗，保留 Dashboard 菜单项 | 已完成 |
| 测试 | 覆盖悬停、单击和加载前单击排队 | 通过 |
| 文档 | 更新启动说明和开发记录 | 已完成 |

### 设计与实施

`desktop_app.py` 的 `on_tray_hover()` 现在只更新时间戳，供 350ms 自动隐藏宽限期判断使用，不再调用显示逻辑。新增 `on_tray_click()` 作为唯一托盘显示入口；窗口尚未就绪时设置 `_widget_show_requested`，`_on_widget_loaded()` 会消费该状态并补显示一次。

`tray.py` 将 `pystray` 默认菜单动作设为“显示悬浮窗”，因此 Windows 左键单击执行该动作；“打开 Dashboard”保留为独立的右键菜单项。`README.md` 同步更新用户可见操作说明。

`tests/test_desktop_app.py` 新增三类断言：悬停不显示、就绪后单击立即显示、加载前单击在加载完成后显示且清除待处理状态。

### 交互边界

- 单击已经显示的悬浮窗图标不会创建重复窗口。
- 悬停消息仍用于维持鼠标从托盘移动到悬浮窗期间的隐藏宽限期，但不会自行弹窗。
- Dashboard 不再是托盘左键默认动作，需要从右键菜单或悬浮窗内部入口打开。

### 验证记录

- 桌面交互测试：执行 `.\.venv\Scripts\python.exe -m pytest tests\test_desktop_app.py -q`，结果为 `9 passed in 0.04s`。
- Python 全量测试：执行 `.\.venv\Scripts\python.exe -m pytest -q`，结果为 `83 passed in 4.77s`。
- Python 语法检查：执行 `.\.venv\Scripts\python.exe -m compileall -q desktop_app.py tray.py windows_tray.py tests\test_desktop_app.py`，通过。

### 已知限制

- 本次未执行物理鼠标点击 Windows 通知区域的人工桌面冒烟；左键行为依据项目当前 `pystray` Windows 后端的 `WM_LBUTTONUP` 默认动作路径实现，并由控制器单元测试覆盖。

## 2026-08-20：按参考图重做 480×600 托盘悬浮窗

### 背景

现有托盘悬浮窗为约 713×738 的横向紧凑布局，与用户提供的竖向参考图在比例、趋势呈现和模型 Token 构成上存在差异。用户确认保持参考图比例，并将原生悬浮窗缩小为 480×600。

### 需求澄清

- 悬浮窗固定使用 480×600 的竖向比例；可用工作区不足时继续使用现有自适应缩小逻辑。
- 保留标题栏、今日概览、Token 趋势、Top 3 模型和更新时间，整体视觉层级按参考图重排。
- 趋势支持 1H、6H、24H 和 7D；1H 与 6H 从现有 24 小时小时桶中过滤，不新增后端接口。
- 模型用量按缓存输入、输入和输出真实 Token 分段显示，不生成虚构占比。
- 右上角关闭按钮只隐藏悬浮窗，不退出托盘、代理服务或 Dashboard。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 布局 | 将 `/widget` 重排为 480×600 竖向卡片布局 | 已完成 |
| 趋势 | 增加 SVG 折线面积图和四档时间范围切换 | 已完成 |
| 模型 | 增加 Top 3 模型三类 Token 分段与真实品牌图标 | 已完成 |
| 原生 | 调整 WebView2 尺寸并接通关闭隐藏接口 | 已完成 |
| 测试 | 更新定位断言并覆盖关闭不退出行为 | 已完成 |
| 验证 | 执行 Vue 构建、Python 全量测试、语法和差异检查 | 已完成 |

### 设计与实施

#### 480×600 紧凑布局

`frontend/src/views/TrayOverviewView.vue` 使用固定高度的弹性布局组合标题栏、概览卡、趋势卡、模型排行和底部更新时间。四项指标保持单行显示，过长模型名使用省略号；窗口小于目标尺寸时页面宽高跟随视口，避免在受限工作区产生额外滚动条。

#### 真实趋势与模型构成

趋势图使用组件内 SVG 生成网格、Y 轴刻度、折线、节点和渐变面积，不新增前端依赖。24H 与 7D 分别读取现有趋势接口；1H 和 6H 读取 24H 小时桶后按当前时间过滤，若历史数据时间戳无法落入窗口则保守显示末尾桶。模型排行读取前三项聚合数据，以 `cache_tokens`、`input_tokens` 和 `output_tokens` 计算分段宽度，并继续复用 `ModelIcon.vue`。

#### 原生关闭边界

`desktop_app.py` 将 `WIDGET_WIDTH` 和 `WIDGET_HEIGHT` 改为 480 与 600。`WidgetApi.close_widget()` 只调用控制器公开的 `hide_widget()`；隐藏会更新可见状态并关闭 WebView2 显示，但不会设置退出状态。`TrayIcon.vue` 增加关闭线性图标。

### 交互边界

- 概览和 Top 3 默认保持最近 24 小时统计口径，费用继续使用今日费用账本；时间切换只影响趋势图。
- 1H 数据受后端按小时聚合粒度限制，通常只有当前或相邻小时的少量节点。
- 固定、设置、查看详情、全部模型、轮询刷新和离开自动隐藏的既有行为保持不变。
- 浏览器开发模式没有原生桥接时，关闭按钮调用浏览器 `window.close()`；正式 WebView2 中使用原生隐藏接口。

### 验证记录

- Vue 生产构建：在 `frontend/` 执行 `npm run build`，Vite 成功转换 682 个模块并生成生产资源。
- 构建警告：现有 ECharts 共享包为 1,030.07 kB（gzip 341.72 kB），仍超过 Vite 500 kB 提示；本次 SVG 趋势图未增加新依赖。
- Python 全量测试：执行 `.\.venv\Scripts\python.exe -m pytest -q`，结果为 `84 passed in 4.99s`。
- Python 语法检查：执行 `.\.venv\Scripts\python.exe -m compileall -q desktop_app.py tests\test_desktop_app.py`，通过。
- `git diff --check`：通过，仅有工作区既有的 LF/CRLF 转换提示，没有空白错误。
- 浏览器视觉检查未执行：应用内浏览器连接继续被插件受信代码路径配置拦截，未生成自动化截图。

### 已知限制

- 项目尚无 Vue 组件测试框架；时间切换和紧凑布局目前依赖模板编译、生产构建、尺寸常量审查及 Python 原生控制器测试。
- 本次未启动真实 Windows 托盘进程做物理点击冒烟；原生关闭行为由控制器测试验证。

## 2026-08-20：调整悬浮窗模块顺序与滚动导航

### 背景

480×600 悬浮窗改版后，趋势模块位于模型排行之前，页面又隐藏了纵向溢出，导致右侧没有滚动条；四项今日概览图标在紧凑卡片中也偏大。用户要求把趋势移动到模型使用量下方、恢复右侧滚动条并缩小指标图标。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 顺序 | 调整为今日概览、模型使用量、Token 趋势 | 已完成 |
| 滚动 | 恢复纵向滚动并增加细滚动条样式 | 已完成 |
| 图标 | 缩小四项概览的图标容器与 SVG | 已完成 |
| 验证 | 执行 Vue 构建、Python 全量测试和差异检查 | 已完成 |

### 设计与实施

`frontend/src/views/TrayOverviewView.vue` 将模型排行移动到趋势卡之前，并把原来压缩在固定高度弹性布局中的内容改为自然块级排列。`.tray-page` 使用 `overflow-y: scroll` 始终保留右侧导航条，标题栏使用 `position: sticky`，滚动内容时继续显示顶部操作入口；滚动条在 WebView2 中使用 7px 宽的轨道和圆角滑块。

四个指标图标容器由 27px 缩小为 17px，内部 SVG 从 18–20px 缩小为 10–11px；文字字号、指标卡尺寸和 480×600 原生窗口尺寸保持不变。

### 交互边界

- 页面初始区域优先显示今日概览和模型排行，向下滚动查看完整趋势与更新时间。
- 右侧滚动条始终占位，避免数据量变化时卡片宽度跳动。
- 窗口小于 480×600 时仍跟随实际视口，纵向滚动继续可用。

### 验证记录

- Vue 生产构建：在 `frontend/` 执行 `npm run build`；最终图标尺寸修正后，Vite 成功转换 683 个模块并生成生产资源。
- Python 全量测试：执行 `.\.venv\Scripts\python.exe -m pytest -q`，结果为 `84 passed in 3.91s`。
- 构建仍保留现有 ECharts 共享包超过 500 kB 的警告，与本次布局微调无关。
- `git diff --check`：通过，仅有工作区既有的 LF/CRLF 转换提示，没有空白错误。

### 已知限制

- 项目没有 Vue 组件级截图测试；滚动条的具体颜色和滑块宽度可能受 Windows WebView2 版本与系统缩放影响。

## 2026-08-20：精简使用概览指标文案

### 背景

用户要求去掉使用概览卡片中四个指标的中文名称，仅保留图标和实际数值；卡片标题和“查看详情”继续显示。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 文案 | 删除今日 Token、今日费用、请求数和平均耗时四个可见名称 | 已完成 |
| 布局 | 移除标签占位并垂直居中图标和数值 | 已完成 |
| 验证 | 执行 Vue 生产构建和差异检查 | 已完成 |

### 设计与实施

`frontend/src/views/TrayOverviewView.vue` 删除四个指标中的 `<small>` 标签，数值直接与对应图标排列；同时移除原标签样式和数值顶部间距。指标计算、卡片标题、详情入口、趋势、模型排行和 480×600 窗口尺寸均保持不变。

### 验证记录

- Vue 生产构建：在 `frontend/` 执行 `npm run build`，Vite 成功转换 683 个模块并生成生产资源。
- 构建仍保留现有 ECharts 共享包超过 500 kB 的警告，与本次文案精简无关。
- `git diff --check`：通过，仅有工作区既有的 LF/CRLF 转换提示，没有空白错误。

### 已知限制

- 删除文字名称后，四项指标主要通过图标、数值格式和固定顺序识别。

## 2026-08-20：移除概览卡标题并由 Logo 打开详情

### 背景

用户进一步要求删除概览卡片内全部中文，包括“今日 Token 使用概览”和“查看详情”，并将进入详情的操作改为点击左上角 Logo。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 文案 | 删除概览卡标题与详情按钮 | 已完成 |
| 交互 | 将左上角 Logo 接入 Dashboard 详情入口 | 已完成 |
| 布局 | 移除标题行并收紧概览卡片高度 | 已完成 |
| 验证 | 执行 Vue 生产构建和差异检查 | 已完成 |

### 设计与实施

`frontend/src/views/TrayOverviewView.vue` 删除概览卡的标题栏，只保留四项图标与数值；概览卡由 117px 收紧为 76px。标题栏中的 Logo 改为带无障碍标签的按钮，点击后沿用现有 `openDashboard('/dashboard')` 路径打开详情；TokenLens 品牌文字及其他标题栏操作保持不变。

### 交互边界

- 概览卡中不再显示中文；Logo 的无障碍标签不作为可见文字渲染。
- 普通浏览器开发模式仍跳转到 `/dashboard`，原生 WebView2 模式仍通过桥接打开独立 Dashboard。

### 验证记录

- Vue 生产构建：在 `frontend/` 执行 `npm run build`，Vite 成功转换 683 个模块并生成生产资源。
- 构建仍保留现有 ECharts 共享包超过 500 kB 的警告，与本次微调无关。
- `git diff --check`：通过，仅有工作区既有的 LF/CRLF 转换提示，没有空白错误。

### 已知限制

- 删除概览标题后，四项数值的含义仅通过固定图标顺序辨识。

## 2026-08-20：同步悬浮窗品牌资源与模型入口字号

### 背景

用户更新了根目录 `assets/logo.png`，并提供 `assets/tokenlens.png` 作为 TokenLens 字标；同时要求模型使用量右侧“全部模型”的字号与标题一致。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 资源核对 | 检查悬浮窗当前引用与两张品牌图片 | 已完成 |
| 品牌 | 改用根目录新版 Logo 与 TokenLens 字标图片 | 已完成 |
| 字号 | 将“全部模型”调整为与模型使用量标题相同的 13px | 已完成 |
| 验证 | 执行 Vue 生产构建和差异检查 | 已完成 |

### 设计与实施

资源核对确认原悬浮窗仍引用 `frontend/src/assets/logo.png`（旧的 1.5 MB 资源），而更新后的主图标位于 `assets/logo.png`。`frontend/src/views/TrayOverviewView.vue` 使用 Vite 的 `import.meta.glob` 显式加载根目录 `assets/logo.png` 和 `assets/tokenlens.png`，分别作为可点击主图标和图片字标；不再渲染文字 `TokenLens`。构建结果包含新的 `logo-BHW0ADg4.png` 与 `tokenlens-CHXauNzy.png`，确认资源已被打包。

### 交互边界

- 左上角主 Logo 继续作为打开详情的入口；图片字标仅展示品牌，不单独触发跳转。
- 主图标和字标均使用用户提供的 PNG；后续更新根目录对应文件后重新构建即可生效。

### 验证记录

- Vue 生产构建：在 `frontend/` 执行 `npm run build`，Vite 成功转换 684 个模块并生成生产资源。
- 构建仍保留现有 ECharts 共享包超过 500 kB 的警告，与本次资源和字号调整无关。
- `git diff --check`：通过，仅有工作区既有的 LF/CRLF 转换提示，没有空白错误。

### 已知限制

- 当前字标为深色 PNG，在深色系统主题或深色自定义背景下可能需要另行提供浅色版本。

## 2026-08-20：替换 Dashboard 原生窗口图标

### 背景

独立 Dashboard 窗口保留 Windows 系统标题栏时，标题栏左侧显示了 Python 默认图标。用户要求保持系统标题栏，并改用 TokenLens 品牌图标。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 资源 | 将现有方形 `assets/icon.png` 生成多尺寸 Windows 图标 | 已完成 |
| 原生窗口 | 为 Dashboard 和悬浮窗的 pywebview 启动入口指定图标 | 已完成 |
| 验证 | 检查 ICO 尺寸并执行桌面控制器测试 | 通过 |

### 设计与实施

`assets/logo.png` 是包含文字的横向品牌图，不适合 Windows 标题栏的小尺寸图标；因此使用其对应的方形品牌标识 `assets/icon.png` 生成 `assets/icon.ico`。图标包含 16 至 256 像素的常用尺寸，供标题栏和 Windows 外壳按 DPI 选择。

`desktop_app.py` 增加 `APP_ICON_PATH`，并在独立 Dashboard 进程和托盘悬浮窗的 `webview.start()` 调用中传入该图标路径。窗口标题、窗口边框和既有 WebView2 行为均保持不变。

### 交互边界

- 图标在完全退出并重新启动 TokenLens 后显示为新的 TokenLens 标识。
- 此改动仅影响 Windows 原生窗口外观，不影响 Dashboard 页面、托盘菜单、代理服务或前端资源引用。

### 验证记录

- ICO 检查：`assets/icon.ico` 已包含 16、20、24、32、40、48、64、128、256 像素尺寸。
- 桌面控制器测试：执行 `.\.venv\Scripts\python.exe -m pytest tests\test_desktop_app.py -q`，结果为 `10 passed in 0.03s`。
- `git diff --check`：未发现空白错误；命令输出包含工作区既有文件的 LF/CRLF 转换提示。

### 已知限制

- pywebview 的 Windows 图标由启动时加载；正在运行的 Dashboard 不会热更新，需要关闭 TokenLens 后重新启动。

## 2026-08-20：精简 Dashboard 原生窗口标题

### 背景

Dashboard 标题栏已替换为 TokenLens 图标后，用户要求将标题文字从“TokenLens Dashboard”精简为“TokenLens”。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 标题 | 修改独立 Dashboard 的原生窗口标题 | 已完成 |
| 验证 | 编译桌面模块并执行控制器测试 | 通过 |

### 设计与实施

`desktop_app.py` 中 `run_dashboard_process()` 创建窗口时使用的标题改为 `TokenLens`。原生标题栏、TokenLens 图标、窗口尺寸和路由加载逻辑保持不变。

### 验证记录

- Python 语法检查：执行 `.\.venv\Scripts\python.exe -m compileall -q desktop_app.py`，通过。
- 桌面控制器测试：执行 `.\.venv\Scripts\python.exe -m pytest tests\test_desktop_app.py -q`，结果为 `10 passed in 0.03s`。

### 已知限制

- 正在运行的 Dashboard 不会动态更新标题；需要关闭后重新打开窗口。

## 2026-08-20：将悬浮窗主图标切换为 icon.png

### 背景

用户要求将悬浮窗左上角主图标从 `assets/logo.png` 改为方形的 `assets/icon.png`，TokenLens 图片字标保持使用 `assets/tokenlens.png`。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 资源 | 将 Vite 品牌资源收集项从 `logo` 改为 `icon` | 已完成 |
| 页面 | 主图标绑定改为 `assets/icon.png` | 已完成 |
| 验证 | 执行 Vue 生产构建和差异检查 | 已完成 |

### 设计与实施

`frontend/src/views/TrayOverviewView.vue` 的 `import.meta.glob` 只收集根目录的 `icon.png` 与 `tokenlens.png`，点击详情的左上角主图标现在绑定前者。构建产物包含 `icon-Bh8gTbwd.png` 和 `tokenlens-CHXauNzy.png`，确认两个资源均被打包。

### 交互边界

- 此改动只影响悬浮窗页面的主图标，不修改 Windows 原生 Dashboard 标题栏图标或托盘图标。
- 点击主图标打开详情、字标展示和标题栏其余操作保持不变。

### 验证记录

- Vue 生产构建：在 `frontend/` 执行 `npm run build`，Vite 成功转换 684 个模块并生成生产资源。
- 构建仍保留现有 ECharts 共享包超过 500 kB 的警告，与本次资源切换无关。
- `git diff --check`：通过，仅有工作区既有的 LF/CRLF 转换提示，没有空白错误。

### 已知限制

- 正在显示的 WebView2 悬浮窗可能保留旧资源缓存，重启 TokenLens 后可确保加载新图标。

## 2026-08-20：恢复 Dashboard 右侧可见滚动条

### 背景

设置页面的 Provider 和模型价格规则内容超出可视区域时，Dashboard 依赖浏览器默认页面滚动。Windows WebView2 的自动隐藏滚动条策略使右侧拖动条不可见，用户难以发现或使用上下滚动。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 布局 | 将 Dashboard 右侧工作区改为独立纵向滚动容器 | 已完成 |
| 样式 | 保留滚动条轨道并提供悬停反馈 | 已完成 |
| 验证 | 执行 Vue 生产构建与差异检查 | 通过 |

### 设计与实施

`frontend/src/App.vue` 将 `body` 与 `.app-shell` 限制在视口内，由 `.workspace` 统一承载 Dashboard 各页面的纵向滚动。工作区使用 `overflow-y: scroll` 与 `scrollbar-gutter: stable` 保留最右侧滚动条空间，并为 Firefox 和 WebView2/Chromium 分别定义细窄的轨道、滑块和悬停颜色。

### 交互边界

- 左侧导航栏继续固定；右侧页面内容可通过鼠标滚轮和最右侧拖动条上下滚动。
- 小屏底部导航的既有 62 像素内容预留保持不变。
- 正在打开的 Dashboard 不会热加载新的前端资源，重新打开窗口或重启 TokenLens 后生效。

### 验证记录

- Vue 生产构建：在 `frontend/` 执行 `npm run build`，结果为成功构建 684 个模块。
- 构建仍提示现有 ECharts 共享包压缩后超过 500 kB，与本次滚动样式改动无关。
- `git diff --check`：通过。

### 已知限制

- 具体滚动条宽度仍会受操作系统的无障碍及浏览器渲染策略影响，但工作区会始终保留滚动区域与可拖动滑块。

## 2026-08-20：统一模型价格卡片默认收缩状态

### 背景

已有模型价格规则加载后默认收缩，但点击“新增规则”会插入一个自动展开的卡片。用户要求模型价格区域的所有卡片都默认收缩。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 状态 | 将新增规则初始展开状态改为默认收缩 | 已完成 |
| 验证 | 执行 Vue 生产构建与差异检查 | 通过 |

### 设计与实施

`frontend/src/components/PricingRulesEditor.vue` 中新增规则沿用 `editable()` 的默认 `expanded: false`，不再传入自动展开参数。加载、保存后的规则同样使用默认收缩状态；用户可点击卡片标题或“配置”进入编辑。

### 交互边界

- 新增规则仍会置于列表首位，只是不会展开表单。
- 保存、预览匹配和删除行为不变。

### 验证记录

- Vue 生产构建：在 `frontend/` 执行 `npm run build`，结果为成功构建 684 个模块。
- 构建仍提示现有 ECharts 共享包压缩后超过 500 kB，与本次状态改动无关。
- `git diff --check`：通过。

### 已知限制

- 项目尚无 Vue 组件交互测试；默认收缩行为通过状态初始化审查和生产构建验证。

## 2026-08-20：修正悬浮窗模型 Token 构成的缓存重复计数

### 背景

悬浮窗的模型用量进度条将 `cache_tokens`、`input_tokens` 和 `output_tokens` 作为并列分段。对于输入统计已包含缓存命中的 Provider，这会把缓存命中重复计入输入总量，导致视觉比例和构成总数错误。

### 需求澄清

- 模型 Token 构成应为互斥的“缓存命中、未命中输入、输出”三段。
- 缓存命中只取 `cache_read_tokens`；`cache_write_tokens` 继续保留为独立统计字段，但不作为命中输入叠加到进度条。
- 不修改数据库或既有 `total_tokens` 的统计口径。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 前端 | 将输入拆为缓存命中与未命中输入 | 已完成 |
| 接口 | 回归检查模型统计返回缓存读写字段 | 已完成 |
| 验证 | 执行接口测试、Vue 生产构建和差异检查 | 通过 |

### 设计与实施

`frontend/src/views/TrayOverviewView.vue` 在生成 Top 3 模型的进度条分段时，将缓存命中限制为 `min(input_tokens, cache_read_tokens)`，未命中输入计算为 `max(input_tokens - cache_read_tokens, 0)`。条形图、图例和辅助文案统一使用这三个互斥部分；缓存写入不参与条形图计算。

`tests/test_stats_api.py` 增加模型聚合接口对 `cache_read_tokens` 和 `cache_write_tokens` 的断言，确保前端可以持续获得用于拆分的缓存读数据。

### 验证记录

- 接口测试：执行 `.\\.venv\\Scripts\\python.exe -m pytest tests\\test_stats_api.py -q`，结果为 `7 passed in 0.91s`；pytest 输出一条既有的 `asyncio_default_fixture_loop_scope` 弃用警告。
- Vue 构建：在 `frontend/` 执行 `npm run build`，Vite 成功转换 684 个模块并生成生产资源。
- 构建仍提示现有 ECharts 共享包超过 500 kB，与本次 Token 构成修正无关。

### 已知限制

- 不同 Provider 的缓存字段语义可能不同；悬浮窗以 `cache_read_tokens` 明确表示“缓存命中”，并通过边界限制避免异常数据产生负的未命中输入。

## 2026-08-21：主统计周期改为当天零点至今

### 背景

概览、模型、供应商、Token、错误监控和悬浮窗原本将 `24h` 作为从当前时刻向前推 24 小时的滚动窗口。用户要求默认统计改为当天零点至当前时刻。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 后端 | 将主统计 `24h` 范围起点改为本地当天 00:00:00 | 已完成 |
| 前端 | 更新主界面、错误监控和悬浮窗的周期文案与请求筛选起点 | 已完成 |
| 测试 | 验证昨日最后一秒的记录不进入今日统计 | 通过 |

### 设计与实施

`backend/database/queries.py` 保持统计 API 的 `24h` 参数不变以兼容现有客户端，但 `range_since("24h")` 现在返回本地当天 `00:00:00`。因此 summary、模型与 Provider 聚合、趋势及错误分布共享“今日”范围，并在零点自动重置。

`frontend/src/App.vue` 和 `frontend/src/views/ErrorsView.vue` 将该周期显示为“今日（零点至今）”。错误列表使用相同的本地零点作为请求筛选起点，避免列表与上方错误指标口径不一致。`frontend/src/views/TrayOverviewView.vue` 将标签从 `24H` 改为“今日”。

### 交互边界

- 7 天与 30 天继续采用滚动窗口。
- 费用分析页的“最近24小时”周期不变；其已有“今日”周期仍单独按当天统计。
- API 参数值仍为 `24h`，外部调用方无需修改请求参数。

### 验证记录

- 后端测试：执行 `.\\.venv\\Scripts\\python.exe -m pytest tests/test_database.py tests/test_stats_api.py -q`，结果为 `14 passed in 0.98s`。
- pytest 输出一条既有的 `asyncio_default_fixture_loop_scope` 弃用警告。

### 已知限制

- 统计日的边界使用运行 TokenLens 主机的本地时间；若请求记录由不同时区的外部系统写入，需确保其 `created_at` 格式与本地时区一致。

## 2026-08-22：更新 Dashboard 左上角品牌 Logo

### 背景

用户要求将 Dashboard 左上角的旧版图标与文字替换为 `assets/tokenlens.png`。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 前端 | 改为加载根目录的 `tokenlens.png` 品牌资源 | 已完成 |
| 布局 | 按资源的完整横向比例展示，不重复渲染文字 | 已完成 |
| 验证 | 执行 Vue 生产构建与差异空白检查 | 通过 |

### 设计与实施

`frontend/src/App.vue` 使用 Vite 的 `import.meta.glob` 加载 `assets/tokenlens.png`。侧栏与移动端顶部统一使用单个完整品牌图；Logo 宽度设为 151px，以适配 210px 侧栏的现有内边距。

### 验证记录

- Vue 构建：在 `frontend/` 执行 `npm run build`，Vite 成功转换 683 个模块并打包 `tokenlens-CHXauNzy.png`。
- `git diff --check -- frontend/src/App.vue`：通过；仅出现 Git 的既有 LF/CRLF 转换提示。

### 已知限制
- 未执行浏览器截图验证；Logo 的最终显示比例依赖提供的 PNG 内容及 WebView2 渲染。

## 2026-08-23：将错误监控整合至请求记录

### 背景

用户要求移除独立“错误监控”页面及其导航入口，并将用于排查失败请求的功能整合到“请求记录”中。

### 需求澄清

- 删除独立 `/errors` 页面、前端路由、侧栏导航和服务端 SPA 页面兜底。
- 保留错误统计接口与请求详情中的错误类型，以免影响现有排查能力。
- Dashboard 的“洞察 & 提醒”点击后进入“请求记录”，并自动应用“全部失败”筛选。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 前端 | 将错误统计、状态码/类型分布和错误类型列表列整合至请求记录 | 已完成 |
| 路由 | 删除错误监控页面、导航与 `/errors` SPA 兜底 | 已完成 |
| 测试 | 验证错误统计接口、已移除路由和 Vue 生产构建 | 通过 |

### 设计与实施

`frontend/src/views/RequestsView.vue` 使用既有 `/api/stats/errors` 获取错误请求数、错误率、主要状态码、主要错误类型及分布；统计会同步 Provider、模型、状态和日期筛选。请求列表新增“错误类型”列，保留单行详情抽屉的完整错误信息。请求页面接入主统计周期选择，以便错误概览与 Dashboard 的周期口径一致。

`frontend/src/App.vue` 删除“错误”导航项，并将 Dashboard 的 `open-errors` 事件重定向到 `/requests?status=failed`。`frontend/src/router/index.js` 和 `backend/__init__.py` 移除 `/errors` 页面路由与 SPA 兜底；`frontend/src/views/ErrorsView.vue` 已删除。

### 交互边界

- `/api/stats/errors` 继续保留，作为请求页错误概览的数据来源，外部 API 调用方无需迁移。
- 选择“成功”或 `2xx` 时，错误概览显示为零；选择失败、4xx、5xx 或具体状态码时，概览与请求列表的状态筛选一致。
- 旧的 `/errors` 地址现在返回 404，不再重定向或渲染旧页面。

### 验证记录

- 后端测试：执行 `.\.venv\Scripts\python.exe -m pytest tests\test_stats_api.py tests\test_spa_routes.py -q`，结果为 `8 passed in 0.93s`。pytest 输出一条既有的 `asyncio_default_fixture_loop_scope` 弃用警告。
- Vue 构建：在 `frontend/` 执行 `npm run build`，Vite 成功转换 681 个模块并生成生产资源。
- 构建仍提示现有共享包压缩后超过 500 kB，与本次页面整合无关。

### 已知限制

- 项目尚无 Vue 组件交互测试；请求页的错误概览通过生产构建和后端接口/路由测试验证。
## 2026-08-23：Dashboard Token 趋势改为固定 24 小时柱状图

### 背景

用户要求将 Dashboard 的 Token 使用趋势从折线图改为柱状图，并固定展示最近 24 小时，每小时一根柱。

### 需求澄清

- 趋势图固定显示滚动最近 24 小时，共 24 个小时槽位。
- 每根柱代表该小时内的总 Token 用量；没有请求的小时显示为 0。
- Dashboard 顶部周期选择继续影响其他概览数据，不改变该趋势图的固定窗口。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 后端 | 增加 `last24h` 滚动范围并按小时聚合趋势数据 | 已完成 |
| 前端 | 将趋势图改为柱状图并补齐 24 个小时槽位 | 已完成 |
| 验证 | 执行数据库/API 测试、Vue 构建和差异检查 | 通过 |

### 设计与实施

`backend/database/queries.py` 增加 `last24h` 范围，其起点为当前时间向前推 24 小时；趋势聚合按 `YYYY-MM-DDTHH` 小时桶返回。`backend/api/stats.py` 接受该范围参数。

`frontend/src/views/DashboardView.vue` 固定请求 `fetchTrend("last24h")`，以当前小时为终点生成连续 24 个本地时间小时槽位，并用接口结果填充；缺失槽位写入 0。ECharts 趋势系列改为 `bar`，柱顶圆角并限制柱宽，横轴显示 `HH:00`。图表标题更新为“最近 24 小时，每小时 Token 用量”。

### 交互边界

- 该固定窗口仅适用于 Dashboard 的 Token 趋势图；概览卡片、模型和供应商等仍由顶部周期选择控制。
- 新的 `last24h` 是 API 扩展参数；原有 `24h` 继续表示当天零点至当前时刻，兼容既有页面。

### 验证记录

- 后端测试：执行 `.\.venv\Scripts\python.exe -m pytest tests\test_database.py tests\test_stats_api.py -q`，结果为 `14 passed in 0.91s`。pytest 输出一条既有的 `asyncio_default_fixture_loop_scope` 弃用警告。
- Vue 构建：在 `frontend/` 执行 `npm run build`，Vite 成功转换 681 个模块并生成生产资源。
- `git diff --check`：通过；仅出现 Git 的既有 LF/CRLF 转换提示。

### 已知限制

- 小时槽位使用运行 TokenLens 主机的本地时间；记录时间需与主机时区保持一致。
## 2026-08-23：Dashboard Token 趋势改为三色堆叠柱

### 背景

用户要求最近 24 小时 Token 趋势柱状图按缓存命中输入、缓存未命中输入和输出三类 Token 以不同颜色构成。

### 需求澄清

- 缓存命中输入使用 `cache_read_tokens`。
- 缓存未命中输入按 `max(input_tokens - cache_read_tokens, 0)` 计算，避免上游已将缓存命中计入 Input 时重复统计。
- 输出使用 `output_tokens`；缓存写入不属于这三个计费/用量类别，不纳入图表。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 前端 | 将总量柱改为 Input、缓存 Input、Output 三色堆叠柱 | 已完成 |
| 交互 | 增加图例、分项 Tooltip 与总计 | 已完成 |
| 验证 | 执行 Vue 生产构建和差异检查 | 通过 |

### 设计与实施

`frontend/src/views/DashboardView.vue` 将 ECharts 系列改为同一 `tokens` 堆叠组：蓝色“缓存未命中输入”、紫色“缓存命中输入”、绿色“输出”。Tooltip 显示每个小时的三个分项与总计，图例固定在图表底部。24 小时空桶补齐数据同时提供三个 Token 字段，确保无数据小时显示为零值堆叠柱。

### 交互边界

- 缓存写入 Token 不展示在该三段图中；它与缓存命中读取不是同一概念。
- 图表继续固定展示滚动最近 24 小时，每小时一根柱。

### 验证记录

- Vue 构建：在 `frontend/` 执行 `npm run build`，Vite 成功转换 681 个模块并生成生产资源。
- `git diff --check`：通过；仅出现 Git 的既有 LF/CRLF 转换提示。
- 构建仍提示现有共享包压缩后超过 500 kB，与本次图表改动无关。

### 已知限制

- 项目尚无针对 ECharts 系列配置的组件测试；堆叠逻辑经源代码审查与生产构建验证。
## 2026-08-23：费用未定价提示支持关闭

### 背景

用户希望费用分析页顶部的未定价请求提示提供一个简洁的关闭入口。

### 需求澄清

- 提示条右侧显示“×”关闭按钮。
- 点击后仅隐藏当前页面会话中的提示，不改变未定价统计或价格规则。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 前端 | 为未定价提示增加关闭状态和“×”按钮 | 已完成 |
| 验证 | 执行 Vue 生产构建和差异检查 | 通过 |

### 设计与实施

`frontend/src/views/CostsView.vue` 增加 `unpricedBannerVisible` 页面状态。未定价提示同时依赖接口返回的未定价请求数和该状态；点击右侧“×”后将状态设为 `false`。按钮包含无障碍标签，保留提示原有的颜色和内容，并提供轻量悬停反馈。

### 交互边界

- 关闭状态只保留在当前费用页实例；刷新页面或重新进入页面后，若仍存在未定价请求，提示会再次显示。
- 关闭提示不会影响页面中的未定价模型列表、覆盖率或费用统计。

### 验证记录

- Vue 构建：在 `frontend/` 执行 `npm run build`，Vite 成功转换 681 个模块并生成生产资源。
- `git diff --check`：通过；仅出现 Git 的既有 LF/CRLF 转换提示。
- 构建仍提示现有共享包压缩后超过 500 kB，与本次关闭按钮改动无关。

### 已知限制

- 项目尚无针对该关闭交互的 Vue 组件测试；本次通过生产构建验证。
## 2026-08-23：悬浮窗 Token 趋势改为三色堆叠柱

### 背景

用户要求将悬浮窗中的 Token 趋势也改为缓存命中输入、缓存未命中输入和输出构成的三色图表，以和 Dashboard 保持一致。

### 需求澄清

- 保留悬浮窗已有的 `1H / 6H / 今日 / 7D` 时间范围切换。
- 用紫、蓝、绿分别显示缓存命中输入、未命中输入和输出。
- 缓存写入 Token 不纳入这三个分项。

### 任务拆分

| 阶段 | 任务 | 结果 |
| --- | --- | --- |
| 前端 | 用紧凑 SVG 三色堆叠柱替换趋势折线 | 已完成 |
| 交互 | 保留范围切换并增加颜色图例与柱悬浮明细 | 已完成 |
| 验证 | 执行 Vue 生产构建和差异检查 | 通过 |

### 设计与实施

`frontend/src/views/TrayOverviewView.vue` 将 SVG 图表的折线路径、面积路径与节点替换为按时间桶绘制的堆叠矩形。每根柱的未命中输入按 `max(input_tokens - cache_read_tokens, 0)` 计算，缓存命中输入使用限制后的 `cache_read_tokens`，输出使用 `output_tokens`。图表标题下方显示紧凑颜色图例；鼠标悬停在柱上时，原生 SVG `title` 显示三项数值。

### 交互边界

- `1H / 6H / 今日 / 7D` 的现有数据加载与切换逻辑不变。
- 图表可视范围较小，因此图例使用“命中 / 未命中 / 输出”短标签；柱悬浮明细显示完整名称。

### 验证记录

- Vue 构建：在 `frontend/` 执行 `npm run build`，Vite 成功转换 681 个模块并生成生产资源。
- `git diff --check`：通过；仅出现 Git 的既有 LF/CRLF 转换提示。
- 构建仍提示现有共享包压缩后超过 500 kB，与本次悬浮窗图表改动无关。

### 已知限制

- 由于悬浮窗使用轻量 SVG 而非 ECharts，悬浮提示使用浏览器原生提示框，不支持 Dashboard 的自定义 Tooltip 样式。