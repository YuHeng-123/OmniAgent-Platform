# OmniAgent Platform 2.0 · 企业级全域 AI 智能体控制中枢

把 **7 个各自独立的 AI 微服务**，收进一个统一控制台 —— 一个页面看清整个 Agent 集群的拓扑、在线状态与业务闭环。

```
┌──────────────────────────────────────────────────────────────┐
│  控制台 (FastAPI 8888 / 或纯静态托管)                          │
│  ├─ 总览     7 个微服务实时在线状态                            │
│  ├─ 网关     主备毫秒级热切仿真                                │
│  ├─ 导购     LangGraph 导购 Agent（含自纠错链路）              │
│  ├─ 营销     Coze 工作流 + 广告法违禁词合规质检                │
│  ├─ 分析     Text-to-SQL + 动态图表                            │
│  └─ 知识库   RAG 检索问答                                      │
└──────────────────────────────────────────────────────────────┘
```

---

## 两种打开方式（都是真的能跑）

| 场景 | 怎么跑 | 说明 |
|---|---|---|
| 🌐 **在线演示 · 零后端** | 打开 `docs/index.html`（或部署 GitHub Pages） | 纯静态、依赖全本地化，**断网也能渲染**；数据来自内置降级层，页面顶栏会明确标注「静态演示模式」 |
| 💻 **本地全功能** | `run.bat`（Windows）/ `./run.sh`（macOS·Linux） | 真后端、真接口、真耗时；7 个服务在线时亮绿点并实时数出来 |

### 本地一键启动

```bash
# Windows
run.bat

# macOS / Linux
chmod +x run.sh && ./run.sh
```

首次运行会自动建 `.venv` 并装依赖，然后启动在 <http://127.0.0.1:8888>。

手动方式：

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
python server.py
```

端口可换：`OMNI_PORT=8899 python server.py`（默认 8888）。

### 部署到 GitHub Pages

`docs/` 目录是**自包含**的（HTML + `static/vendor/` 全部前端库都在里面），可直接作为发布目录：

1. 把仓库推到 GitHub
2. **Settings → Pages → Source: Deploy from a branch → Branch: `main` / 目录: `/docs`**
3. 访问 `https://<你的用户名>.github.io/<仓库名>/`

> `docs/` 由 `build_docs.py` 生成，**不要手改**。改了 `templates/index.html` 或 `static/` 之后重跑：
> ```bash
> .venv/Scripts/python build_docs.py
> ```

---

## 7 个微服务矩阵

控制台本身不包含业务逻辑，它编排的是下面这些独立项目（各自一个仓库 / 一个端口）：

| 端口 | 服务 | 角色 | 技术栈 |
|---|---|---|---|
| 8000 | 企业 AI 统一网关 | 流量总线与大模型调度 | FastAPI + Redis + MCP |
| 8001 | 琼华珠宝 AI 智能导购 | 核心业务 Agent | LangGraph + SQLite + SSE |
| 8002 | 多平台爆款素材工作台 | 内容营销 Agent | Coze API + FastAPI |
| 8501 | 企业级智能知识库 (RAG) | 知识底座 | Streamlit + ChromaDB |
| 8510 | AI 数据分析专家 | 决策分析 Agent | Streamlit + DuckDB + Plotly |
| 8765 | 自动化情报抓取平台 | 数据管道 | Python Native HTTP + SQLite |
| 7860 | 多模态音视频智能体 (FunClip) | 交互 Agent | Gradio + PyTorch + FunASR |

**控制台不依赖这 7 个服务是否在线** —— 在线就亮绿点，不在线就灰色，控制台自身照常可用。

---

## 核心设计：双模式数据源

前端所有取数走 `static/omni-api.js` 这一层适配器：

```
                 ┌─── 成功 → 用真实数据（顶栏:「本地服务已连接 N/7」）
请求本地后端 ────┤
  (2.5s 超时)    └─── 失败 → 降级到内置演示逻辑（顶栏:「静态演示模式」）
```

**先试真的，真不了才用假的，且当前模式始终显示在页面上** —— 不把演示数据伪装成线上数据。

导购链路的降级更细一层（`server.py`）：

```
POST /api/v1/guide/chat
   ├─ 优先真调 ecom-agent(8001)，解析其 SSE 事件流
   │     └─ 拿到 token → 返回 backend="live:ecom-agent@8001"
   └─ 8001 不可用 / 上游 4xx / 流里没有正文
         └─ 降级到本地规则引擎 → backend="fallback:local-demo"
```
响应里永远带 `backend` 字段，你一眼能看出这次回答是真跑的还是兜底的。

---

## 核心设计：中枢事件总线（真实探测驱动，不是滚动的假日志）

总览页右下角那条事件流，**不是把几行日志写死在前端滚动**，而是一条真 SSE 流：

```
GET /api/v1/events/stream   (text/event-stream)
   ├─ 打开即推：1 条接入说明 + 7 条服务就绪播报（基于真实 TCP 探测结果）
   ├─ 之后每 3s 重新探测 7 个端口，与上一轮快照比对
   │     ├─ 有变化 → 立刻推「上线 / 下线」事件
   │     └─ 无变化 → 每第 4 轮推一条巡检心跳（避免刷屏）
   └─ 客户端断开即回收（request.is_disconnected）
```

拿不到后端（GitHub Pages / `file://` / 服务未启）时，前端 `omni-api.js` 自动降级为内置示例事件，
右上角角标从 `LIVE · 真实端口探测` 变成 `示例事件流 · 无后端` —— 不冒充实时。

**这条链路有独立验证脚本**（不靠自夸，靠注入式端口探测做端到端验证）：

```bash
.venv/Scripts/python verify_event_bus.py     # → evidence/event-bus-diff.txt
```

它把底层 `scan_ports` 做注入：第 1 轮全在线、第 2 轮把 `:7860` 置为离线，
然后断言流里**确实出现了「状态变化：下线」**。实测输出：

```
T+ 0.0s  [MASTER  ] (info) 事件总线接入成功：…当前在线 7/7
T+ 0.0s  [FUNCLIP ] (ok)   多模态音视频智能体 (FunClip)（:7860）已就绪。
T+ 3.0s  [HEALTH  ] (err)  多模态音视频智能体 (FunClip)（:7860）状态变化：下线，流量已摘除。
T+12.1s  [HEALTH  ] (info) 全局健康巡检完成，6/7 在线，本轮无状态变化。
结论: PASS —— 事件确实由状态差异驱动，非定时文本播报
```

> **现场演示怎么用**：把任意一个服务停掉（例如 `:7860`），**3 秒内**右侧面板就会出现一条红色的下线事件；
> 再启动它，3 秒内出现绿色的上线事件。比任何形容词都有说服力。

---

## 2.0 相对 1.0 改了什么（每条都有实测）

| # | 1.0 的问题 | 2.0 的做法 |
|---|---|---|
| 1 | 导购接口接了 8001 却 `pass` 丢弃结果，页面回的是写死的套话 | 真解析 SSE 流；失败才降级，且 `backend` 如实标注 |
| 2 | `latency_ms` 是写死的常数（38 / 22 / 42） | 全部 `time.perf_counter()` 实测 |
| 3 | 前端 4 个 CDN（tailwind / fontawesome / chart.js / Google Fonts），断网即白屏 | 全部本地化到 `static/vendor/`，改系统字体栈，**零外部请求** |
| 4 | 假模型名 `Gemini-3.8-Flash` | 移除编造模型名 |
| 5 | 同步 socket 探测端口阻塞 async 事件循环 | `asyncio.open_connection` + `asyncio.gather` 并发探测 |
| 6 | CORS `allow_origins=["*"]` + `credentials=True`（浏览器规范禁止） | `allow_credentials=False` |
| 7 | 只能在本地跑，无法静态演示 | 新增 `docs/` 纯静态版 + `build_docs.py` 构建脚本 |
| 8 | 事件总线是**写死的 6 行文本**（时间戳永远停在 `19:15:02`），标着 LIVE 却永不刷新 | 改为真 SSE 差异驱动流（见上一节）；降级时角标明确写「示例事件流」 |

---

## 实测证据

`evidence/selftest-omni.txt` 由 `selftest_omni.py` 生成，**一次跑完 11 组真实 HTTP 校验**（同进程起 API + 起静态站，不依赖长驻服务）：

```bash
.venv/Scripts/python selftest_omni.py       # 全链路自检
.venv/Scripts/python verify_event_bus.py    # 事件总线差异驱动专项验证
```

覆盖：主控台渲染 · 0 外部 CDN · 7 服务在线数 · 导购降级链路 · 自纠错链路 · 合规质检命中违禁词 · Text-to-SQL · 热切仿真 · docs 静态资源全部 200 · 静态化自检 · **SSE 事件总线首帧 8 条真实事件**。

---

## 诚实边界

这个仓库是我（作者）用来**演示 Agent 集群编排形态**的控制台，以下几点如实说明：

- **控制台的业务数据是演示数据。** 营销文案、SQL 结果、GMV 数字、热切延迟，都是本地生成的样例，不是某家公司的真实经营数据。
- **`/api/v1/gateway/simulate_failover` 是仿真端点**，它不真的去熔断某个上游，只演示「主备热切」这个形态。
- **7 个微服务是独立项目**，不在本仓库内。本仓库是控制台 + 编排层。想看真实链路，需要各自把服务起起来。
- **端口探测只探本机 `127.0.0.1`**，不做远程服务发现。
- **事件总线的心跳是 12s 一次**（3s 探测 × 4 轮），只有状态**变化**才实时推送 —— 这是刻意压掉刷屏，不是采样不到。
- 无鉴权、无多租户 —— 定位是单机演示。

---

## 目录结构

```
OmniAgent-Platform/
├─ server.py              # FastAPI 控制台（页面 + 6 个 API + 端口探测 + SSE 事件总线）
├─ build_docs.py          # 生成 docs/ 静态演示版（单一拓扑来源：复用 server.py）
├─ selftest_omni.py       # 11 组离线自检 → evidence/
├─ verify_event_bus.py    # 事件总线「差异驱动」专项验证 → evidence/
├─ requirements.txt
├─ run.bat / run.sh       # 一键启动（自动建 venv 装依赖）
├─ templates/
│  └─ index.html          # 主控台页面（Jinja2 模板）
├─ static/
│  ├─ omni-api.js         # 双模式数据源适配层（真接口 ⇄ 内置降级）+ 事件总线客户端
│  └─ vendor/             # 本地化前端库：tailwind / chart.js / fontawesome
├─ docs/                  # ← GitHub Pages 发布目录（build_docs.py 生成，勿手改）
└─ evidence/
   ├─ selftest-omni.txt   # 全链路实测证据
   └─ event-bus-diff.txt  # 事件总线差异驱动验证证据
```

---

## 常见问题

**页面打开是白板 / 样式丢了？**
1.0 时代是因为依赖外部 CDN。2.0 已全部本地化。若仍异常，检查浏览器控制台是否 404 了 `static/vendor/...`（确认你是从仓库根目录启动，而不是把 `index.html` 单独拷出去）。

**总览页 7 个服务全是灰的？**
正常 —— 说明你只起了控制台，那 7 个服务没起。控制台自身功能不受影响。

**端口 8888 被占用？**
`OMNI_PORT=8899 python server.py`。

**想改页面样式？**
改 `templates/index.html` 或 `static/omni-api.js`，然后重跑 `build_docs.py` 更新静态演示版。
