"""
build_docs.py —— 把控制台导出为「纯静态、自包含」的 GitHub Pages 演示版

做三件事：
1. 复用 server.py 里同一份 SERVICES_META 拓扑，用 Jinja2 渲染 templates/index.html
   （单一数据源，避免拓扑在两处各写一份而对不上）。
2. 把绝对路径 /static/... 改写成相对路径 ./static/...
   —— 否则部署在 https://<user>.github.io/<repo>/ 这种子路径下会 404。
3. 把 static/ 整个复制进 docs/static/，让 docs/ 目录自包含，可直接作为
   GitHub Pages 的发布目录（Settings → Pages → Branch: main / root: /docs）。

用法：
    .venv\\Scripts\\python.exe build_docs.py
"""
import os
import re
import shutil
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from jinja2 import Environment, FileSystemLoader  # noqa: E402

from server import SERVICES_META  # noqa: E402  单一拓扑来源

DOCS_DIR = os.path.join(BASE_DIR, "docs")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_SRC = os.path.join(BASE_DIR, "static")
STATIC_DST = os.path.join(DOCS_DIR, "static")


def build():
    # ---------- 1. 渲染 ----------
    # 静态演示版按「集群全在线」的完整形态渲染，视觉效果与本地跑满 7 个服务时一致；
    # 页面顶栏的运行模式角标会在拿不到后端时自动改标为「静态演示模式 · 内置样例数据」，
    # 不会把演示态冒充成线上态。
    services = []
    for s in SERVICES_META:
        item = dict(s)
        item["status"] = "online"
        services.append(item)

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=False)
    tpl = env.get_template("index.html")
    html = tpl.render(
        services=services,
        online_count=len(services),
        total_count=len(services),
        static_demo=True,
    )

    # ---------- 2. 绝对路径 → 相对路径 ----------
    before = html
    html = html.replace('"/static/', '"./static/')
    html = html.replace("'/static/", "'./static/")
    html = html.replace('"/api/', '"./api/')      # 静态托管下必定 404 → 前端降级
    html = html.replace("'/api/", "'./api/")
    html = html.replace('href="/"', 'href="./"')
    html = html.replace("url('/static/", "url('./static/")
    path_fix = sum(1 for a, b in [(before, html)] if a != b)

    # ---------- 3. 写出 ----------
    os.makedirs(DOCS_DIR, exist_ok=True)
    out_html = os.path.join(DOCS_DIR, "index.html")
    with open(out_html, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)

    if os.path.isdir(STATIC_DST):
        shutil.rmtree(STATIC_DST)
    shutil.copytree(STATIC_SRC, STATIC_DST)

    # 阻止 GitHub Pages 的 Jekyll 处理（避免下划线目录/文件被忽略）
    with open(os.path.join(DOCS_DIR, ".nojekyll"), "w", encoding="utf-8") as f:
        f.write("")

    # ---------- 4. 自检 ----------
    report = []
    report.append("html bytes           = %d" % len(html.encode("utf-8")))
    report.append("path rewritten       = %s" % bool(path_fix))
    report.append("残留绝对 /static/    = %d" % len(re.findall(r'["\'(]/static/', html)))
    report.append("残留绝对 /api/       = %d" % len(re.findall(r'["\'(]/api/', html)))
    report.append("未渲染的模板标记数   = " + str(len(re.findall(r"\{\{|\{%", html))))
    n_static = sum(len(fs) for _, _, fs in os.walk(STATIC_DST))
    n_static_bytes = sum(
        os.path.getsize(os.path.join(r, fn))
        for r, _, fs in os.walk(STATIC_DST) for fn in fs
    )
    report.append("docs/static 文件数   = %d (%d bytes)" % (n_static, n_static_bytes))
    report.append("docs/index.html      = %s" % os.path.exists(out_html))
    report.append("docs/.nojekyll       = %s" % os.path.exists(os.path.join(DOCS_DIR, ".nojekyll")))

    print("\n".join(report))
    return 0 if (len(re.findall(r"\{\{|\{%", html)) == 0
                 and len(re.findall(r'["\'(]/static/', html)) == 0) else 1


if __name__ == "__main__":
    sys.exit(build())
