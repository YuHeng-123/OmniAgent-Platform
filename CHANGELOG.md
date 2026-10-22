# 更新日志

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 的组织方式，
版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

### 修复 —— CI 连续 15 次全红，pytest 与 docker build 从未真正执行过

- **问题**：`ruff format --check` 卡在 CI 第 5 步（`core/state.py` 的 `TRACE_AUDIT_LOGS.extendleft([...])`
  不符合当前 ruff-format 的换行规则），而 lint 排在 pytest 之前 ——
  **70 条断言、五层验证、`docker build` 一次都没在 CI 里跑过**，徽章却一直被当作「绿」来引用。
- **根因之一**：`requirements-dev.txt` 写的是 `ruff>=0.6` 没锁定，CI 每次拉最新版，
  与作者本地旧版规则不一致（本地过、CI 不过）。
- **修复**：`ruff format core/state.py`（纯格式，无逻辑改动）+ 把 ruff 锁到 `==0.16.10`。

### 修复 —— 镜像缺 `core/` 与 `routers/`：能 build、一启动就崩

- **问题**：`Dockerfile` 只 `COPY server.py services.yaml` + `templates/` + `static/`，
  而 `server.py` 的 `from core.config import ...`、`from routers.business import ...` 全在这里面。
  镜像 layers 是「成功」的，容器启动即 `ModuleNotFoundError: No module named 'core'`，
  `docker compose up` 表现为 restart 循环。
  **实测复现**：按旧 COPY 清单在空目录复刻文件集后执行 `python server.py` →
  `File "server.py", line 31 ... ModuleNotFoundError: No module named 'core'`。
- **修复**：补 `COPY core/ ./core/` 与 `COPY routers/ ./routers/`。
- **实测验证**：按新 COPY 清单复刻文件集，`OMNI_PORT=8899 python server.py` →
  `/healthz` 返回 `{"status":"ok","version":"2.8.0","services_total":8}`、首页 `200`，
  8 个探针全部按 `services.yaml` 表列出。`docker build` 本身仍未跑过（本机无 Docker CLI），
  已在 README「诚实边界」如实标注。

### 新增 —— `tools/check_image_files.py`：没有 Docker 也能查「镜像里缺文件」

- 解析 `Dockerfile` 的 `COPY` 行得到镜像内顶层条目，再扫 `server.py` 的本地 `import`
  逐个对账，缺一个就 `exit 1`。纯静态、不依赖 Docker，已接进 CI 当门禁。
- 实测输出：`已 COPY = core, requirements.txt, routers, server.py, services.yaml, static, templates`，
  `server.py 依赖 = core, routers` → `[OK]`。
- CI 另加 `hadolint` 步骤（`failure-threshold: error`），在没有 Docker 的环境下兜住镜像层规则。

### 变更 —— 演示数据脱敏：移除真实业务与品牌名

- `services.yaml` / `core/config.py` 的导购服务名、`routers/business.py` 与
  `static/omni-api.js` 里的商品名、话术、营销文案，以及 `templates/` 与生成后的 `docs/`，
  统一把公司业务名替换为通用演示名（`Jewelry Advisor Demo · AI 智能导购` / `AURORA` 系列）。
- 共 70 处，`docs/` 由 `build_docs.py` 重新生成而非手改；改后 `pytest -q` 仍是 **70 passed**。
- **遗留（如实记录）**：git 历史里仍能检出旧品牌名（`git log -S` 可查，17 个 commit）。
  彻底清理需 `git filter-repo` 重写历史并 force push，**尚未执行**。

### 变更 —— README 收敛：从「8 个微服务并列」改为主次两层叙事

- 首屏改成「核心 = Runtime + MCP 网关 / 其余 = 接入靶场」，并加一行脱敏声明。
- 删除约 60 行 ASCII 架构图（正文已有 `assets/architecture.svg` 真图）、
  6 个静态自述徽章（只留 CI / Live Demo / python / license）、25 行 v2.8 功能清单
  （指向本 CHANGELOG）、5 张重复截图、整棵目录树压缩为关键路径。
- 新增「可验证性」一节：把 pytest 数量、evidence 产物、探针、镜像文件集对账四条证据集中呈现。
- 效果：README 523 → 388 行（**净删 135 行**），「诚实边界」一节保留并补了 2 条（历史未清理 / CI 曾全红）。


## [2.8.0] - 2026-10-13

### 新增 —— 企业级生产架构升级：多角色视窗、爆款归因抽屉、微内核解耦、JWT 多租户鉴权与异步任务中心

- **多角色动态视窗 (Persona Views)**：Overview 顶部支持 4 大角色视图即时切换（👑 经营决策大盘、⚡ 出海运营工场、🛠️ 架构运维拓扑、🌐 全域调度总览），针对性过滤展示指标。
- **爆款 SKU 深度实效归因抽屉**：点击商品卡片滑出沉浸式抽屉，集成「转化漏斗与 ROAS 归因」、「Prompt 演进与 A/B 测试」、「短视频 15s 完播留存曲线」，并支持导出实效 JSON 报告与一键派生 3 套新变体。
- **后端架构模块化解耦 (DDD-Style)**：将原本 2,470 行单体 `server.py` 无损拆解为 `core/` 与 `routers/`，精简微内核装配层至 200 行，100% 保持历史契约与端口探测兼容。
- **企业级安全与 4-Tier RBAC 服务端守卫**：实现 HMAC-SHA256 JWT Token 签发与租户上下文提取（`tenant-hq`, `tenant-tiktok`, `tenant-embroidery`），敏感操作（微服务起停）在服务端实现严格校验（只读角色响应 HTTP 403 `PERMISSION_DENIED`）。
- **后台分布式异步任务队列与状态机抽屉**：针对长耗时音视频切片 (FunClip) 与批量出海文案批处理，实现带锁状态机（`PENDING` ➔ `RUNNING` ➔ `COMPLETED` / `FAILED`）并发解耦队列，顶栏集成任务中心实时抽屉与在途徽章。
- **自动化测试扩充**：测试套件新增企业安全与异步任务断言，总测试数扩充至 **70 项 100% PASS**。

## [2.7.0] - 2026-10-10

### 新增 —— Labs 转正：graph-xiaohongshu 注册为第 8 个探针服务

- **真融合**：`graph-xiaohongshu` 从「源码快照」升级为服务矩阵一等公民 ——
  `services.yaml` 与内置兜底拓扑各加第 8 个服务条目，探针端口 **`:8020`**
  （上游默认 8000 与 ai-gateway 冲突，README 已写明统一改 8020 启动）。
- **`GET /api/v1/labs`**：Labs 模块索引端点 —— 两个模块的名称 / 技术栈 / 亮点 /
  README 摘要（运行时读 `labs/*/README.md`）+ 复用端口探测的在线状态。
- **总览页新增「Labs · 收编进中枢的纵深模块」区块**：两张模块卡
  （亮点列表 + 技术 chip + 运行中/冷备状态），连本地后端拉真数据、
  Pages 静态模式保持占位提示不装数据。
- **FunClip 卡片口径**：desc 明确「上游源码已收编 labs/funclip-studio」。
- **拓扑口径 7 → 8 全量同步**：KPI 分母、纳管 tag、meta description、
  事件总线首帧（`0/8` / `8/8`）、`check_services` FAQ、诚实边界；
  `tests/test_omni.py` 9 处断言同步 + 新增 `/api/v1/labs` 契约测试；
  `selftest_omni.py` SSE 首帧采集阈值 8 → 9（1 接入 + 8 就绪播报）。
- Key 安全复查：labs 全目录扫描真实 Key 特征（含项目实际三个 Key 的特征串）零命中；
  `yuannengai` 仅存在于环境变量读取默认值与 PII 脱敏正则，无泄密面。
- `APP_VERSION` → 2.7.0。

## [2.6.0] - 2026-10-10

### 新增 —— Labs：收编两个纵深模块进中枢

- **labs/graph-xiaohongshu**：LangGraph 1.0+ 小红书营销内容流水线的源码快照
  （`StateGraph` + subgraph 图编排、`interrupt()` / `Command(resume)` 标准人在环路、
  AsyncPostgresSaver 状态持久化、日志出口 PII 脱敏、JWT 认证、Vue 3 前端）。
  收编前完成安全清洗：`.env`（真实 Key）不入库，以 `.env.example` 占位。
- **labs/funclip-studio**：阿里达摩院 FunClip（MIT © 2023 Alibaba）的 Windows 工程化封装
  —— 上游源码快照 + 原样保留的 LICENSE / 双语 README（署名上游）+ 本仓作者的一键启停脚本
  与不加载模型的 ASR 结果兼容性单测；即中枢 7 服务矩阵中的 `:7860`。
- **labs/README.md**：收编边界如实写明 —— CI（`pytest.ini` / `ruff.toml`）与 Docker
  （`.dockerignore`）均不包含 labs，各模块重依赖独立管理。
- `APP_VERSION` → 2.6.0。

## [2.5.0] - 2026-10-10

### 变更 —— 控制台主题再重构：「墨金石」→「翡翠 × 奶油 · Jade & Cream」

- **为业务换装**：这是一家珠宝（和田玉 / 珍珠 / 莫桑钻）电商的控制台，
  上一版「石墨黑 + 香槟金」的科技终端气质与业务不符；本次整体换为
  **深翡翠侧栏 / 顶栏（`#123B2E`）+ 奶油白工作区（`#F5F0E6`）+ 金渐变点缀
  （`#E8C87E → #C9A05A`）+ 深咖啡正文（`#2B241B`）**，观感对齐奢侈品牌后台。
- **双区语义色系统**：`slate-*` 与 `text-white` 全部变量化——在翡翠区自动渲染为米白字、
  在奶油区自动渲染为咖啡字，同一份模板两区各自正确；翡翠区分隔线改为半透明米白。
- **图标统一**：全站图标收拢为单色系统（奶油区咖啡灰 / 翡翠区米白），状态一律用
  圆点 + 文字表达，不再用图标本身配色；品牌 favicon 由遗留的蓝紫彩虹渐变换成
  翡翠方底 + 金色等轴测立方体，与新侧栏品牌章同款。
- **侧栏激活态 / 主按钮**升级为金渐变胶囊（全站唯一高饱和元素）；
  卡片改暖白底 + 柔和投影 + 14px 圆角；徽章 / chip / 滚动条全部转暖沙色系。
- **数据可视化重上色**：历史趋势 7 色系列、分析页饼图 / 柱状图、坐标轴刻度与网格线
  全部按浅色底重调（网格由白 5% 改为咖啡 7%，刻度改暖咖啡灰）。
- **toast 反色**：由深底浮层改为白瓷底 + 深字 + 状态色描边，浮层阴影转暖。
- 散落的 Tailwind 内置彩色类（`rose-400` / `amber-300` 等）全部收敛到主题
  `accent-*` 令牌；404 页与 `theme-color` 同步翡翠奶油。

## [2.4.0] - 2026-10-10

### 变更 —— 控制台视觉重构：从「彩虹霓虹」到「墨金石 · Inkwell & Champagne」

- **设计令牌收敛为一条规则**：石墨近黑底（`#0B0B0F`）+ **唯一主色香槟金**（`#D9B36A`）
  + 三种状态色（在线绿 / 告警琥珀 / 故障红，只表状态、不做装饰）。
- 移除渐变文字、幽灵大图标、多层辉光与「遍地霓虹」；面板统一为**单层 1px 发丝线**，
  不再叠加卡片套卡片。
- **KPI 四张卡 → 一条紧凑数据带**，数字用等宽字形（`tabular-nums`），刷新时不跳版。
- **侧栏激活态**改为「金色细亮条 + 微金底」，不再是整块高亮；技术栈标签统一为低调石墨 mono 徽章。
- 七个页签（总览 / 智能导购 / 营销工场 / 数据分析 / 模型网关 / 知识库 / 历史回放）**全部按同一视觉语言重排**，
  图表主色统一为香槟金。
- 新增**窄屏抽屉导航**（<1024px），手机端可正常使用。

### 修复

- **阻塞式原生弹窗 → 非阻塞 toast**：营销生成与数据查询的失败提示原用 `alert()`，
  原生弹窗在无头浏览器中会**阻塞渲染进程**，导致自动化截图 / CI 巡检假死；改为右下角 `showToast`。
- 违禁词检出块的配色由 Tailwind 默认 `rose/slate` 收敛到主题 `accent-rose`，与设计令牌一致。
- **静态演示版 `localMarketing` 分支死代码**：`else`（私域默认）提前收口，
  使「电商详情页」「朋友圈短文案」两个平台分支**永不可达**；改为显式 `else if (platform === 'wechat')`，
  与 `server.py` 的分支顺序对齐（两侧镜像保持一致）。
- 404 页与 `<meta name="theme-color">` 由旧的蓝紫渐变改为墨金石配色。

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

### 变更 —— 事件总线一节去掉重复的实测输出

原始输出已经在 `evidence/event-bus-diff.txt`，README 里那份是第二份副本，删掉改成链接。
README 最终 523 → 376 行。
