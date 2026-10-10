# Graph 小红书内容引擎 —— LangGraph 1.0+ 营销 Agent 流水线

> 从作者独立开发的同名项目收编进 OmniAgent-Platform 中枢的源码快照
> （完整开发历史见作者原仓库：Gitee `mood6666/graph_xiaohongshu`，含 v1 / v2-vedio 分支）。
> 本模块演示 LangGraph 1.0+ 的生产级用法：**图编排、人在环路、状态持久化**。

## 它做什么

一条「选题 → 写稿 → 审稿 → 配图」的小红书内容生产流水线，两个关键节点都是
**人工闸门**（Human-in-the-loop）：AI 出候选，人来拍板；稿子被驳回会带着反馈
回到写作节点重写，整个状态在数据库里，服务重启也能续跑。

```
START
  │
  ▼
plan_topics（AI 生成 3~5 个候选选题，flash 快模型）
  │
  ▼
⏸ interrupt: human_select_topic（等待人工选题）
  │
  ▼
write_draft（Doubao 标准模型写长文）
  │
  ▼
⏸ interrupt: human_review（等待人工审稿）
  │
  ├── [approved] ──▶ extract_visuals（提炼配图要点，fast 模型）
  │                      │
  │                      ▼
  │                  generate_images（Gemini 生图）
  │                      │
  ▼                      ▼
  └── [rejected] ◀── END（驳回则携带 feedback 回到 write_draft）
```

## 技术亮点（均为代码实证，非口号）

- **LangGraph 1.0+ 图编排**：`StateGraph` 组装工作流，选题环节独立成
  **subgraph**（`app/graph/subgraphs/topic_selection.py`），节点按职责分文件
  （planner / writer / visualizer）。
- **标准 HITL 中断**：用 1.0 的 `interrupt()` + `Command(resume=...)` 恢复语义，
  API 层（`app/api/v1/workflow.py`）提供 start / state / resume 三个端点，
  中断期间状态完整落库。
- **Postgres Checkpointer**：`AsyncPostgresSaver` + psycopg3 连接池
  （`langgraph-checkpoint-postgres>=3.0.3`），工作流状态跨请求、跨重启持久化。
- **合规意识落在日志层**：`app/core/pii_anonymizer.py` 在日志出口对邮箱、手机号、
  信用卡号、API Key 做 PII 脱敏（`.env` 可开关），配合 structlog 结构化日志。
- **双模型分级调度**：标准模型（写长文）与 flash 快模型（选题 / 要点提取）按任务
  分配，temperature 分开配置 —— 省钱且提速。
- **带认证的后端**：JWT 登录（python-jose + passlib/argon2），不是裸奔的 demo。
- **Vue 3 + Vite 前端**：`frontend/` 含完整源码，构建产物由后端静态托管。

## 目录结构

```
graph-xiaohongshu/
├─ app/
│  ├─ api/v1/          # workflow / image / auth 三组接口
│  ├─ core/            # config · db · logger · middleware · pii_anonymizer · security · callbacks
│  ├─ graph/           # state · workflow · metrics · utils + nodes/ + subgraphs/
│  ├─ services/        # llm_service（Doubao）· image_service（Gemini）
│  ├─ models/user.py   # 用户模型
│  └─ main.py          # 应用入口（lifespan 内装配 checkpointer）
├─ frontend/           # Vue 3 + Vite（src 完整源码；构建产物不入库）
├─ scripts/init_db.sql
├─ static/images/generated/   # 运行期生成图落盘目录（占位入库，内容不入）
├─ requirements.txt    # langgraph 1.0+ / langgraph-checkpoint-postgres / fastapi / psycopg3 ...
├─ test_db_connection.py
└─ .env.example        # 复制为 .env 后填入真实 Key（.gitignore 已挡 .env，勿提交）
```

## 运行

```bash
# 1. 准备 PostgreSQL，建库
psql -U postgres -c "CREATE DATABASE langgraph_db;"

# 2. 装依赖 + 配置
pip install -r requirements.txt
copy .env.example .env      # 填入数据库密码与 LLM API Key

# 3. 起后端（FastAPI）—— 端口用 8020：上游默认 8000 与中枢 ai-gateway 冲突，
#    控制台的探针卡片也按 8020 探测
uvicorn app.main:app --reload --port 8020
# API 文档: http://localhost:8020/docs

# 4. 起前端（可选，开发模式）
cd frontend && npm install && npm run dev
```

核心 API：`POST /api/v1/workflow/start`（带主题方向启动）→
`GET /api/v1/workflow/state/{thread_id}`（查状态）→
`POST /api/v1/workflow/resume/{thread_id}`（`select_topic` / `approve` / `reject+feedback`）。

## License

MIT
