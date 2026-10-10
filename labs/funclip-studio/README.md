# FunClip Studio —— FunClip 的 Windows 工程化封装

> **归属声明（重要，请先读这段）**：本目录内的 `funclip/` 包、`LICENSE`、
> `README_upstream.md`（英文版）与 `README_zh.md`（中文版）来自
> **阿里巴巴达摩院 FunASR 团队的开源项目 [FunClip](https://github.com/alibaba-damo-academy/FunClip)**
> （MIT License，Copyright (c) 2023 Alibaba，随目录原样保留）。
> 语音识别（FunASR Paraformer）、热词感知、按说话人分段剪辑、双语字幕等**核心能力全部属于上游**。
> 本仓作者在这个上游快照之上做的是 **Windows 工程化封装与测试**（见下节），
> 本模块对应 OmniAgent-Platform 中枢 7 服务矩阵中的 `:7860 多模态音视频智能体`。

## 它是什么

FunClip 是一个完全开源、本地部署的自动视频剪辑工具：对视频跑语音识别得到带时间戳的
字幕文本，用户圈选文本片段（或按说话人），一键切出对应视频并烧录字幕 ——
这是直播录播切片、播客精选等场景的生产力工具。

## 本仓作者的封装层（在 MIT 上游之上）

| 内容 | 说明 |
|---|---|
| `start_funclip.ps1` / `.bat` | 一键启动：先探测 `:7860` 避免重复起进程，隐藏窗口后台拉起 `funclip/launch.py`，stdout/stderr 重定向到日志，轮询就绪（最长 180s）后自动打开浏览器；失败时直接打印错误日志尾部用于排障 |
| `stop_funclip.ps1` / `.bat` | 一键停止 |
| `tests/test_recognition_result_compat.py` | **不加载真实 ASR 模型**的兼容性单测：用 `DummyASRModel` 注入构造的识别结果，验证 FunASR nano 版返回格式（缺 `sentence_info` / `raw_connectors` 等字段）时 `VideoClipper.recog()` 仍能正确产出文本与 SRT 字幕 |
| `tests/test_twelvelabs_pegasus.py` | Twelve Labs Pegasus 视频理解接口的兼容性测试 |

## 目录结构

```
funclip-studio/
├─ funclip/               # 上游源码快照（launch / videoclipper / llm/* / utils/*）
├─ tests/                 # 本仓作者添加的兼容性单测（注入式，无需模型文件）
├─ docs/images/           # 上游 README 引用的官方示意图
├─ start_funclip.ps1/.bat # 本仓作者的 Windows 启动封装
├─ stop_funclip.ps1/.bat
├─ README_upstream.md     # 上游英文 README（原样保留）
├─ README_zh.md           # 上游中文 README（原样保留）
├─ LICENSE                # MIT，Copyright (c) 2023 Alibaba（原样保留）
└─ requirements.txt       # 上游依赖
```

## 运行（Windows）

```powershell
# 首次：建虚拟环境并安装依赖（funasr / torch 体积较大，首次识别时还会下载模型）
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# 启动（探测端口 → 后台拉起 → 轮询就绪 → 自动开浏览器）
./start_funclip.ps1        # 或双击 start_funclip.bat

# 用完停止
./stop_funclip.ps1
```

网页入口 `http://127.0.0.1:7860`：上传视频 → 识别字幕 → 圈选文本/说话人 → 生成切片，
产物落在 `output/`（运行期产物，不入库）。

> 重依赖提醒：`funasr + torch` 安装体积大，首次启动与首次识别需要加载/下载模型，
> 属正常现象。普通切片功能不需要任何 API Key；「AI 智能裁剪」需要自备 LLM Key。

## License

上游 FunClip：MIT License © 2023 Alibaba（见 `LICENSE`）。
封装层代码遵循同仓库根级的 MIT 许可。
