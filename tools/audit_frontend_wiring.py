"""前端接线审计：HTML 里调用的东西，是否真的存在实现。

动机：pytest 验的是 HTTP 契约与文件存在性，抓不到「按钮点了没反应」这类
**死接线**（onclick 指向不存在的函数、OmniAPI.xxx 没有实现、getElementById 找不到元素）。
这类问题一旦发生就是演示现场最尴尬的失败，所以单独做一层静态审计。

跑法：
    .venv/Scripts/python tools/audit_frontend_wiring.py [输出文件]

注意：本脚本里的标记名**全部取自实际代码**，不靠记忆猜。
（初版凭记忆写了 `chart-history` / `stopService` 之类并不存在的名字，报了 4 条假 FAIL；
  另有一次把「未配置」记成「没有配置」。凡断言字面量，务必先 grep 确认原文。）
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "evidence" / "frontend-wiring.txt"

def load_template_with_includes(path: pathlib.Path) -> str:
    """读取模板并递归展开 {% include '...' %} 子组件，保持静态审计覆盖率。"""
    text = path.read_text(encoding="utf-8")

    def repl(m):
        inc_name = m.group(1).strip()
        inc_path = ROOT / "templates" / inc_name
        if inc_path.exists():
            return load_template_with_includes(inc_path)
        return m.group(0)

    return re.sub(r'\{%\s*include\s+["\']([^"\']+)["\']\s*%\}', repl, text)


tpl = load_template_with_includes(ROOT / "templates" / "index.html")
docs = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
api = (ROOT / "static" / "omni-api.js").read_text(encoding="utf-8")
docs_api = (ROOT / "docs" / "static" / "omni-api.js").read_text(encoding="utf-8")

L: list[str] = []
fails: list[str] = []
L.append("=" * 72)
L.append("前端接线审计（静态分析）")
L.append("=" * 72)

# ---------- 1. OmniAPI.<method> 调用 vs omni-api.js 里的实现 ----------
used = set(re.findall(r"OmniAPI\.([A-Za-z_$][\w$]*)\s*\(", tpl))
defined = set(re.findall(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(", api))  # IIFE 内声明
defined |= set(re.findall(r"^\s*([A-Za-z_$][\w$]*)\s*:\s*\1\s*,", api, re.M))  # 导出表 `x: x,`
defined |= set(re.findall(r"^\s*([A-Za-z_$][\w$]*)\s*:\s*function", api, re.M))  # 内联写法
L.append("\n[1] OmniAPI 调用 vs 实现")
L.append("    页面调用    : %s" % ", ".join(sorted(used)))
missing = sorted(used - defined)
if missing:
    fails.append("调用了未实现的方法：%s" % ", ".join(missing))
L.append("    缺失        : %s" % (", ".join(missing) or "无 ✅"))

# ---------- 2. getElementById 引用 vs 真实存在的 id ----------
# id 可能来自静态 DOM，也可能由 JS 动态创建（`host.id = 'x'`），两者都算存在。
ids = set(re.findall(r'id="([^"]+)"', tpl)) | set(re.findall(r"\.id\s*=\s*['\"]([^'\"]+)['\"]", tpl))
refs = set(re.findall(r"getElementById\(\s*['\"]([^'\"]+)['\"]\s*\)", tpl))
dangling = sorted(r for r in refs if r not in ids)
L.append("\n[2] getElementById 引用 vs 已定义 id（含动态创建）")
L.append("    已知 id 数  : %d" % len(ids))
L.append("    被引用 id 数: %d" % len(refs))
if dangling:
    fails.append("引用了不存在的元素 id：%s" % ", ".join(dangling))
L.append("    悬空引用    : %s" % (", ".join(dangling) or "无 ✅"))

# ---------- 3. onclick 调用的函数是否已定义 ----------
called = set(re.findall(r'onclick="([A-Za-z_$][\w$]*)\s*\(', tpl))
defined_fns = set(re.findall(r"function\s+([A-Za-z_$][\w$]*)\s*\(", tpl))
defined_fns |= set(
    re.findall(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function|\()", tpl)
)
undef = sorted(called - defined_fns)
L.append("\n[3] onclick 调用 vs 已定义函数")
L.append("    onclick 函数: %s" % ", ".join(sorted(called)))
if undef:
    fails.append("onclick 调用了未定义函数：%s" % ", ".join(undef))
L.append("    未定义      : %s" % (", ".join(undef) or "无 ✅"))

# ---------- 4. 2.2 新功能在模板与静态版里都出现（标记名来自实际代码） ----------
TPL_MARKERS = [
    "nav-history",
    "tab-history",  # 侧边栏入口与页签容器
    "history-uptime-canvas",
    "history-latency-canvas",  # 两条曲线画布
    "history-event-list",  # 事件回放列表
    "controlService",
    "fetchHistory",
    "fetchRecentEvents",
    "services.yaml 未配置 start_cmd",  # 未配置时的禁用提示
]
# 静态版按设计把 7 张卡片都渲染成「在线」（页面顶栏已标注静态演示模式），
# 所以走的是「停止」分支，不出现上面的禁用提示 —— 这里只断言它确实接上了管控。
DOCS_MARKERS = [
    "nav-history",
    "tab-history",
    "history-uptime-canvas",
    "history-latency-canvas",
    "controlService",
    "fetchHistory",
    "fetchRecentEvents",
]
for name, txt, markers in (
    ("templates/index.html", tpl + api, TPL_MARKERS),
    ("docs/index.html", docs + docs_api, DOCS_MARKERS),
):
    absent = [m for m in markers if m not in txt]
    if absent:
        fails.append("%s 缺少 2.2 标记：%s" % (name, ", ".join(absent)))
    L.append("\n[4] %s 2.2 标记齐全 = %s" % (name, "✅" if not absent else "❌ " + str(absent)))

# ---------- 5. docs 里的前端交付物必须与源码一字不差 ----------
same = api == docs_api
if not same:
    fails.append("docs/static/omni-api.js 与源码不一致（请重跑 build_docs.py）")
L.append("\n[5] docs 静态副本与源码一致 = %s" % ("✅" if same else "❌"))

# ---------- 6. 诚实性：静态版必须标注「示例事件流」，不能假装 LIVE ----------
has_demo = "示例事件流" in tpl and "示例事件流" in docs
L.append("\n[6] 静态版事件总线角标含「示例事件流」= %s" % ("✅" if has_demo else "❌"))
if not has_demo:
    fails.append("静态演示没标注「示例事件流」，有假装实时的风险")

# ---------- 7. 未配置 start_cmd 时必须禁用而非假装能启动 ----------
has_stop_btn = "serviceControl" in tpl and "停止" in tpl
has_disabled = "services.yaml 未配置 start_cmd" in tpl and "disabled" in tpl
L.append("\n[7] 起停按钮接线")
L.append("    停止按钮 + serviceControl = %s" % ("✅" if has_stop_btn else "❌"))
L.append("    未配置时禁用并说明        = %s" % ("✅" if has_disabled else "❌"))
if not (has_stop_btn and has_disabled):
    fails.append("起停按钮接线不完整")

# ---------- 汇总 ----------
L.append("\n" + "=" * 72)
if fails:
    L.append("结论：FAIL（%d 项）" % len(fails))
    for f in fails:
        L.append("  ✗ %s" % f)
else:
    L.append("结论：PASS —— 无悬空调用，2.2 起停/历史功能在模板与静态版都齐全")
L.append("=" * 72)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(L), encoding="utf-8")
print("\n".join(L))
sys.exit(1 if fails else 0)
