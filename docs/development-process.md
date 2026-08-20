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
