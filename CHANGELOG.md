# 更新日志

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 的组织方式，
版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [2.3.0] - 2026-10-10

### 新增 —— 五个业务页面的「内容厚度」升级（前后端演示引擎行为保持镜像）

- **电商智能导购**：意图 4 类 → **8 类**（优惠查询 / 售后政策 / 玉石·珍珠养护 / 选材对比 /
  莫桑知识 / 按对象推荐 / 按预算选品 / 欢迎语轮换），内置商品池 2 款 → **8 款**，
  支持从消息里提取预算数字自动配品；「500 元无门槛券」自纠错彩蛋保留。
- **爆款营销工场**：发布渠道 3 → **5**（新增「电商详情页」「朋友圈短文案」）；
  违禁词库 6 → **30 条**，分四大类（广告法极限词 / 质量承诺 / 医疗功效 / 封建迷信 /
  虚假渊源），每条带违规理由与合规改写建议；质检范围扩到**最终生成文案全文**（连模板一起查）。
- **数据分析（Text-to-SQL）**：可答问法 3 → **8 种**（新增客单价与复购 / 爆款 TopN /
  新客趋势 / 退款率 / 环比增长），每问独立 SQL + 图表 + 经营结论；默认分支改为
  主动列出可问清单，不再让人猜。
- **企业知识库检索**：结果从写死 2 条 → **14 条内置切片 + 真·关键词打分检索**
  （命中加权、置信度映射、关键词高亮），未命中时如实返回「没有强相关切片」并给出建议问法。
- **模型调度网关**：容灾仿真从单一 504 场景 → **三场景确定性轮换**
  （超时熔断 / 限流分流 / 质量降级重生成）；前端按钮从「写死的动画」改为
  **真调 `/api/v1/gateway/simulate_failover`**，静态模式降级到行为一致的本地镜像。

### 修复
- 静态版事件流的提示文案「违禁词库 114 词」与实际词库条数不符（实际 6 条）——
  改为**动态取 `BANNED_WORDS_DB.length`**，从源头杜绝文案与代码漂移。

## [2.2.0] - 2026-10-10

### 新增
- **服务起停管控**：服务卡片上的「停止 / 启动」按钮，背后是两个新接口
  `POST /api/v1/services/{id}/stop` 与 `/start`，外加 `GET /api/v1/services/control-capabilities`
  告诉前端每个服务哪些操作可用。停掉任意一个服务，**约 3 秒内**事件总线就会推出下线事件 ——
  演示「差异驱动」不再需要手动去命令行杀进程。
  - 安全约束：`stop` 只杀监听在**拓扑配置端口**上的进程，端口表之外的 PID 一律不碰；
  - 诚实约束：`start` 只拉起 `services.yaml` 里配了 `start_cmd` 的服务，没配就如实返回
    `not-configured` 并说明如何启用，不假装知道没告诉过它的启动方式。
- **状态历史曲线 + 事件持久化**：SQLite 落盘（`data/omni_history.db`，不入 git），
  新增 `GET /api/v1/history/probes`（各服务在线率 / 平均延迟，按时间桶降采样）与
  `GET /api/v1/events/recent`（最近事件倒序回放）。页面从「实时快照」变成「有历史」。
- **「历史趋势」页签**：30 分 / 2 小时 / 8 小时窗口切换，在线状态阶梯曲线 + 平均延迟折线 +
  最近事件流水。静态演示模式下走内置样例曲线，不假装有真实历史。
- **容器化**：`Dockerfile`（python-slim + 非 root + `HEALTHCHECK` 打 `/healthz`）、
  `docker-compose.yml`（命名卷持久化历史库 + `host.docker.internal`）、`.dockerignore`。
- **两个可配置的网络地址**：`OMNI_HOST`（控制台监听地址）与 `OMNI_PROBE_HOST`（探测 7 个
  微服务的地址）。本机默认仍是 `127.0.0.1`，容器里由镜像设为 `0.0.0.0` / `host.docker.internal`。
  `/healthz` 新增 `networking` 字段，容器排障时一眼看出 bind 到哪、探的是谁。
- **代码规范**：`ruff.toml` + `.pre-commit-config.yaml`，CI 增加 lint 与镜像构建步骤。

### 文档
- README 新增「界面预览」：4 张**真机截图**（总览 / 历史趋势 / 导购 / 网关容灾），
  均在本机实跑后截取，落 `assets/screenshots/`，不是设计稿。

### 变更
- **事件总线架构重构**：由「每个 SSE 连接各自探测」改为**全局共享巡检器**
  （lifespan 内启动的 asyncio 任务）。现在 N 个页面连接只探测一次，
  事件由巡检器统一 diff 并广播给所有订阅者 —— 这也是历史落盘与起停联动的地基。
- `zip()` 全部补 `strict=True`：探测结果与端口列表本应一一对应，错位时立即抛错而非静默截断。
- 版本号断言不再写死 `2.1.0`（否则每次发版假 FAIL），改为从 `APP_VERSION` 派生并校验渲染产物。

### 新增（工具）
- `tools/audit_frontend_wiring.py`：静态接线审计 —— 抓「按钮点了没反应」这类死接线
  （`onclick` 无实现 / `OmniAPI.xxx` 不存在 / `getElementById` 悬空）。已进 CI。
- `tools/audit_runtime.py`：运行时端到端审计 —— 起真服务，真拉起假监听进程 →
  同一条 SSE 流上等「上线」→ 点 stop → 等「下线」→ 校验 SQLite 落盘。
  全程只用自己的假进程，不碰宿主机上正在跑的服务。故意不进 CI（耗时长、依赖本机环境）。

### 修复
- `ruff check .` 在工作目录而非项目根执行会「假绿」——已确认并在 CI 里用显式路径避免。
- **容器网络三处会「跑起来就是坏的」**（读代码即得，非猜测；已修 + 断言锁定）：
  1. `uvicorn.run(host="127.0.0.1")` 写死 —— 容器里只 bind 回环，Docker 的端口发布
     （`-p 8888:8888`）转发到容器 eth0，从宿主机**打不通**；而容器 healthcheck 从
     loopback 打是通的，于是显示「健康」却访问不了。改为走 `BIND_HOST`。
  2. 端口探测写死 `127.0.0.1` —— 容器内的回环是容器自己，**永远探不到宿主机上的微服务**
     （面板恒显示 0/7），`extra_hosts` 也因此形同虚设。改为走 `PROBE_HOST`；导购上游同理。
  3. `./data:/app/data` 绑定挂载 + 非 root 运行 —— 宿主机 `data/` 不存在时由 Docker 以 root
     创建，容器内 uid 1000 写不进 SQLite。改用**命名卷**。
  本机实测：设 `OMNI_HOST=0.0.0.0` 后从非回环地址访问 `/healthz` 返回 200（即端口发布可达）。
  注意：**镜像本身仍未在本机 build 过**（环境无 Docker CLI），这条属未验证。

## [2.1.0] - 2026-10-09

### 新增
- `services.yaml`：7 个微服务的端口 / 名称 / 事件标签 / 探测参数全部配置化；坏配置自动回退内置默认。
- `GET /healthz`：标准健康检查端点（版本 / 运行时长 / 拓扑来源 / 实时在线数）。
- `tests/`：40 条 pytest 断言（拓扑、事件总线纯函数、前端本地化、API 契约、docs 一致性）。
- `.github/workflows/ci.yml`：pytest → 全链路自检 → 事件总线专项 → 校验 `docs/` 无漂移 → 上传 evidence。
- `assets/architecture.svg`：控制台 / 双模式适配层 / 7 服务网格三段式架构图。
- `check_services.py`：读 `services.yaml` 的就绪检查（`--require-all` 要求 7/7 全在线）。
- `static/favicon.svg`：站点图标（此前 `/favicon.ico` 请求 404）。
- `docs/404.html`：GitHub Pages 自定义 404 页。
- `CODE_OF_CONDUCT` 之外的工程化基建：`LICENSE`(MIT)、`CHANGELOG.md`、`.editorconfig`。

### 变更
- 导购链路的上游端口与请求路径改为从 `services.yaml` 读取（`GUIDE_PORT` / `GUIDE_CHAT_PATH`），
  不再硬编码 `8001` —— 换上游端口只改配置。
- 版本号收敛为单一来源 `APP_VERSION`：页面标题、侧边栏角标、`/healthz`、FastAPI 文档共用。
- `/api/v1/analysis/overview` 补上 `metrics_source` 与实测 `latency_ms`，与 `/overview/stats` 口径一致。
- 网关热切仿真端点新增 `token_usage_note`，声明 token 数值为样例而非真实计费。
- 事件总线验证脚本的注入方式由「写死置离线」改为「翻转」，与运行环境是否开着服务无关。

### 移除
- 编造模型名彻底清除：`DeepSeek-V3`（此前残留在网关页 3 处与仿真端点 2 处）、`Gemini-3.8-Flash`。
  断言从 2 个前端文件扩大到全部交付代码文件，防止回归。
- 冗余脚本 `start.bat`、`start_all_services.py`（指向并不存在的 `:9999`）、3 个 `.bak` 备份文件。

## [2.0.0] - 2026-10-09

### 新增
- `docs/` 纯静态演示版 + `build_docs.py` 构建脚本，可发布到 GitHub Pages。
- 双模式数据源适配层 `static/omni-api.js`：先试真后端，失败降级内置逻辑，且模式显示在顶栏。
- 事件总线改为真实 TCP 端口探测驱动的 SSE 流（差异驱动 + 巡检心跳）。

### 变更
- 前端依赖全部本地化到 `static/vendor/`，移除 4 个外部 CDN，断网可渲染。
- 导购接口真解析 `:8001` 的 SSE 流，失败才降级，响应里以 `backend` 如实标注来源。
- 所有耗时改为 `time.perf_counter()` 实测，不再返回写死常数。

### 修复
- 导购接口此前接了 8001 却丢弃结果、返回写死套话。
- CORS `allow_origins=["*"]` 与 `allow_credentials=True` 的非法组合。
- 同步 socket 探测端口阻塞 async 事件循环，改为 `asyncio` 并发探测。

## [1.0.0] - 2026-10-09

- 初始版本：7 个微服务的统一控制台雏形。
  前端依赖走外部 CDN、事件总线为前端写死的日志文本、业务数据为硬编码样例。
