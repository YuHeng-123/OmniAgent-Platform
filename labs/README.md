# OmniAgent Platform · Labs —— 收编进中枢的纵深模块

> 本目录存放「从独立项目收编进中枢」的源码快照。中枢（OmniAgent-Platform 主控台）负责
> 集群编排与可视化，Labs 里是支撑业务纵深的具体 Agent 实现 —— 两者合起来才是完整的故事：
> **广度在控制台，深度在这里。**

| 模块 | 定位 | 核心技术 |
|---|---|---|
| [graph-xiaohongshu](./graph-xiaohongshu/) | 基于 LangGraph 1.0+ 的小红书营销内容流水线 | StateGraph 图编排 · `interrupt()` 人在环路 · Postgres Checkpointer 状态持久化 · PII 日志脱敏 |
| [funclip-studio](./funclip-studio/) | FunClip 的 Windows 工程化封装（中枢 7 服务中的 `:7860`） | FunASR 语音识别 · 视频时间戳对齐 · 热词感知 · 按说话人分段剪辑 |

## 边界（如实说明）

- **CI 只验证主控台**：`pytest.ini` 把 `labs/` 整树排除出测试收集，`ruff.toml` 把它排除出
  lint，`.dockerignore` 不把它打进镜像 —— labs 模块有各自的重依赖
  （torch / funasr / langgraph / PostgreSQL），控制台不装、不跑、不假装跑。
- **快照会滞后于各模块的独立开发**。graph-xiaohongshu 的完整开发历史（含 v1 / v2-vedio
  分支）在作者的原仓库中维护。
- **funclip-studio 的上游版权**：FunClip 由阿里巴巴达摩院 FunASR 团队开发并以 MIT 协议开源
  （`LICENSE` 与上游 README 均随目录保留），热词感知、按说话人分段剪辑、双语字幕等核心能力
  全部来自上游；本仓作者的贡献是 Windows 启停工程化与兼容性测试，见
  [funclip-studio/README.md](./funclip-studio/) 的归属说明。
