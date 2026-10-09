# 更新日志

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 的组织方式，
版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

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
