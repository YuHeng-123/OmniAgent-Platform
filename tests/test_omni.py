"""
test_omni.py —— OmniAgent 控制台的断言测试

跑法：
    .venv\\Scripts\\python.exe -m pytest -q

分五块：
  1. 拓扑配置化（services.yaml 加载 / 各种坏配置回退 / 端口一致性）
  2. 事件总线纯函数（首帧播报 + 差异驱动；不开长连接也能断言）
  3. 前端静态资源本地化（0 外部 CDN、假模型名已清除）
  4. docs/ 静态演示版（无 Jinja 残留、无绝对路径、无写死时间戳）
  5. 真实 HTTP 接口契约（真 uvicorn，见 conftest.py）
"""

import json
import os
import pathlib
import re
import sys

import httpx
import pytest

BASE = pathlib.Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

import server as S  # noqa: E402

# 1.0 时代把前端依赖挂在 4 个外部 CDN 上，断网即白屏；这些域名一个都不该再出现
CDN_MARKERS = (
    "cdn.tailwindcss.com",
    "cdn.jsdelivr.net",
    "cdnjs.cloudflare.com",
    "fonts.googleapis.com",
)

VENDOR_FILES = (
    "static/vendor/tailwind.js",
    "static/vendor/chart.umd.js",
    "static/vendor/fontawesome/css/all.min.css",
    "static/vendor/fontawesome/webfonts/fa-solid-900.woff2",
    "static/omni-api.js",
)


def read(rel: str) -> str:
    return (BASE / rel).read_text(encoding="utf-8")


# =========================================================================== #
# 1. 拓扑配置化
# =========================================================================== #
def test_topology_loaded_from_yaml():
    assert S.CONFIG_SOURCE == "services.yaml", "拓扑没有从 services.yaml 加载"
    assert len(S.SERVICES_META) == 7


def test_topology_ports_exact():
    assert S.ALL_PORTS == [8000, 8001, 8002, 8510, 8501, 8765, 7860]


def test_every_service_has_event_tag():
    ids = {s["id"] for s in S.SERVICES_META}
    assert ids <= set(S.EVENT_TAGS), "有服务没配事件标签，事件总线会显示成裸 id"


def test_yaml_and_builtin_fallback_agree():
    """yaml 与内置兜底必须同构 —— 否则配置读不到时控制台会静默换个拓扑。"""
    assert S.ALL_PORTS == [s["port"] for s in S._BUILTIN_SERVICES]
    assert {s["id"] for s in S.SERVICES_META} == {s["id"] for s in S._BUILTIN_SERVICES}
    assert set(S.EVENT_TAGS) == set(S._BUILTIN_EVENT_TAGS)


def test_probe_params_sane():
    assert S.EVENT_INTERVAL_SEC > 0
    assert 0 < S.PROBE_TIMEOUT < 3
    assert S.HEARTBEAT_EVERY >= 1


def test_missing_yaml_falls_back(tmp_path):
    services, tags, probe, source = S.load_topology(str(tmp_path / "nope.yaml"))
    assert source.startswith("builtin-defaults")
    assert len(services) == 7
    assert probe == S._BUILTIN_PROBE


def test_broken_yaml_falls_back(tmp_path):
    bad = tmp_path / "services.yaml"
    bad.write_text("services:\n  - id: broken\n", encoding="utf-8")  # 缺 port
    services, tags, probe, source = S.load_topology(str(bad))
    assert source.startswith("builtin-defaults"), "坏配置必须回退，不能让控制台起不来"
    assert len(services) == 7


def test_empty_services_list_falls_back(tmp_path):
    bad = tmp_path / "services.yaml"
    bad.write_text("services: []\n", encoding="utf-8")
    _, _, _, source = S.load_topology(str(bad))
    assert source.startswith("builtin-defaults")


# =========================================================================== #
# 2. 事件总线纯函数
# =========================================================================== #
def test_sse_frame_is_valid():
    frame = S._sse({"ts": "00:00:01", "tag": "MASTER", "msg": "中文消息"})
    assert frame.startswith("data: ")
    assert frame.endswith("\n\n")
    assert json.loads(frame[len("data: ") :].strip())["msg"] == "中文消息"


def test_initial_events_all_online():
    prev = {p: True for p in S.ALL_PORTS}
    evs = S.build_initial_events(prev)
    assert len(evs) == 1 + len(S.SERVICES_META)
    assert evs[0]["tag"] == "MASTER"
    assert "7/7" in evs[0]["msg"]
    assert all(e["level"] == "ok" for e in evs[1:])
    assert all("已就绪" in e["msg"] for e in evs[1:])


def test_initial_events_all_offline():
    prev = {p: False for p in S.ALL_PORTS}
    evs = S.build_initial_events(prev)
    assert "0/7" in evs[0]["msg"]
    assert all(e["level"] == "warn" for e in evs[1:])
    assert all("离线" in e["msg"] for e in evs[1:])


def test_diff_events_empty_when_stable():
    snap = {p: True for p in S.ALL_PORTS}
    assert S.diff_events(snap, dict(snap)) == [], "状态没变就不该产生事件"


def test_diff_events_detects_going_offline():
    prev = {p: True for p in S.ALL_PORTS}
    cur = dict(prev)
    cur[7860] = False
    evs = S.diff_events(prev, cur)
    assert len(evs) == 1
    assert evs[0]["level"] == "err"
    assert "下线" in evs[0]["msg"]


def test_diff_events_detects_coming_online():
    prev = {p: False for p in S.ALL_PORTS}
    cur = dict(prev)
    cur[8001] = True
    evs = S.diff_events(prev, cur)
    assert len(evs) == 1
    assert evs[0]["level"] == "ok"
    assert "上线" in evs[0]["msg"]


# =========================================================================== #
# 3. 前端本地化 / 去假
# =========================================================================== #
def test_template_has_zero_external_cdn():
    html = read("templates/index.html")
    leaked = [m for m in CDN_MARKERS if m in html]
    assert leaked == [], "模板仍引用外部 CDN(断网会白屏): %s" % leaked


def test_template_references_local_assets():
    html = read("templates/index.html")
    for rel in (
        "static/vendor/tailwind.js",
        "static/vendor/chart.umd.js",
        "static/omni-api.js",
        "static/vendor/fontawesome/css/all.min.css",
    ):
        assert rel in html, "模板未引用本地资源 %s" % rel


@pytest.mark.parametrize("rel", VENDOR_FILES)
def test_vendor_assets_present_and_nonempty(rel):
    p = BASE / rel
    assert p.exists(), "本地依赖缺失: %s" % rel
    assert p.stat().st_size > 500, "本地依赖疑似空文件: %s" % rel


def test_omni_api_js_wires_real_sse_with_fallback():
    js = read("static/omni-api.js")
    assert "EventSource" in js
    assert "/api/v1/events/stream" in js
    assert "示例事件流" in js, "降级路径的角标文案不能丢（否则冒充实时）"


# 编造模型名曾在 server.py 的仿真端点与网关页卡片里各残留几处（2.0 只查了前端
# 两个文件，漏了后端）—— 现在把全部交付代码文件都纳入断言，README 的历史对照除外。
CODE_DELIVERABLES = (
    "server.py",
    "templates/index.html",
    "static/omni-api.js",
    "docs/index.html",
    "docs/static/omni-api.js",
)


@pytest.mark.parametrize("rel", CODE_DELIVERABLES)
def test_no_fabricated_model_name_anywhere(rel):
    txt = read(rel)
    assert "Gemini-3.8-Flash" not in txt
    assert "DeepSeek-V3" not in txt, "编造模型名残留在 %s（README 的历史对照除外）" % rel


def test_template_no_hardcoded_latency():
    """单步耗时必须是「实测后填」，不能预设一个 38 ms 的假数。"""
    html = read("templates/index.html")
    assert ">38 ms<" not in html


# =========================================================================== #
# 4. docs/ 静态演示版（GitHub Pages）
# =========================================================================== #
def test_docs_index_staticized():
    html = read("docs/index.html")
    assert "{{" not in html and "{%" not in html, "docs 里残留 Jinja2 标记"
    assert '"/static/' not in html and "'/static/" not in html, "docs 里残留绝对路径"
    assert not any(m in html for m in CDN_MARKERS)


def test_docs_event_bus_not_hardcoded():
    html = read("docs/index.html")
    assert "19:15:02" not in html, "docs 里还残留写死的事件时间戳"
    assert "startEvents" in html


def test_docs_assets_selfcontained():
    for rel in (
        "docs/static/omni-api.js",
        "docs/static/vendor/tailwind.js",
        "docs/static/vendor/chart.umd.js",
        "docs/static/vendor/fontawesome/css/all.min.css",
    ):
        assert (BASE / rel).exists(), "docs 不自包含，缺 %s" % rel
    assert (BASE / "docs" / ".nojekyll").exists()


def test_docs_matches_source_static_copy():
    """docs/static 必须是 static/ 的忠实副本，否则线上演示与源码行为会漂移。"""
    for rel in VENDOR_FILES:
        src = (BASE / rel).read_bytes()
        dst = (BASE / "docs" / rel).read_bytes()
        assert src == dst, "docs 与源码不一致: %s" % rel


# =========================================================================== #
# 5. 真实 HTTP 接口契约
# =========================================================================== #
def test_index_page_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "OmniAgent" in r.text
    assert not any(m in r.text for m in CDN_MARKERS)


def test_overview_stats_contract(client):
    d = client.get("/api/v1/overview/stats").json()
    assert d["status"] == "ok"
    assert d["total_count"] == 7
    assert len(d["services"]) == 7
    assert d["config_source"] == "services.yaml"
    assert d["metrics_source"] == "demo-sample", "演示指标必须如实标注来源"


def test_guide_chat_reports_backend_and_latency(client):
    d = client.post("/api/v1/guide/chat", json={"message": "你们支持刻字定制吗？", "history": []}).json()
    assert d["backend"].startswith(("live:", "fallback:")), "必须如实标注这次是谁答的"
    assert isinstance(d["latency_ms"], int) and d["latency_ms"] >= 0
    assert len(d["trace"]) >= 2
    assert d["reply"]


def test_guide_self_correction_path(client):
    d = client.post("/api/v1/guide/chat", json={"message": "有500元无门槛券吗", "history": []}).json()
    assert d["self_corrected"] is True
    assert any(s["status"] == "retry" for s in d["trace"])


def test_marketing_flags_banned_words(client):
    d = client.post(
        "/api/v1/marketing/generate",
        json={
            "product_name": "全网唯一顶级和田玉吊坠",
            "target_platform": "xiaohongshu",
            "keywords": "第一",
        },
    ).json()
    words = {v["word"] for v in d["compliance"]["violations"]}
    assert {"顶级", "第一", "全网唯一"} <= words
    assert d["compliance"]["status"] == "WARNING"
    assert d["compliance"]["score"] < 100


def test_marketing_clean_copy_passes(client):
    d = client.post(
        "/api/v1/marketing/generate",
        json={
            "product_name": "和田碧玉平安扣吊坠",
            "target_platform": "douyin",
            "keywords": "",
        },
    ).json()
    assert d["compliance"]["status"] == "PASS"
    assert d["compliance"]["score"] == 100
    assert "violations" in d["compliance"]


@pytest.mark.parametrize(
    "q,ctype",
    [
        ("按品类统计销售额", "bar"),
        ("各渠道成交额", "pie"),
        ("近半年销售趋势", "line"),
    ],
)
def test_analysis_query_returns_sql_and_chart(client, q, ctype):
    d = client.post("/api/v1/analysis/query", json={"query_text": q}).json()
    assert d["chart"]["type"] == ctype
    assert d["sql"].upper().lstrip().startswith("SELECT")
    assert d["conclusion"]


def test_failover_endpoint_is_marked_simulated(client):
    d = client.post("/api/v1/gateway/simulate_failover").json()
    assert d["simulated"] is True, "仿真端点必须自曝是仿真，不能装成真的熔断"
    assert "兜底" in d["failover_model"] or "Mock" in d["failover_model"]


def test_events_stream_first_frame_is_real(base_url):
    """真开一条 SSE，断言首帧 = 1 条接入说明 + 7 条服务就绪。"""
    got = []
    with httpx.Client(trust_env=False, timeout=httpx.Timeout(30.0, connect=5.0, read=8.0)) as c:
        with c.stream("GET", base_url + "/api/v1/events/stream") as r:
            assert r.status_code == 200
            assert "text/event-stream" in r.headers.get("content-type", "")
            for line in r.iter_lines():
                if line.startswith("data:"):
                    got.append(json.loads(line[len("data:") :].strip()))
                if len(got) >= 1 + len(S.SERVICES_META):
                    break
    assert len(got) >= 1 + len(S.SERVICES_META)
    assert got[0]["tag"] == "MASTER"
    assert len(got[1 : 1 + len(S.SERVICES_META)]) == len(S.SERVICES_META)


# =========================================================================== #
# 6. 2.1 细节契约：健康检查 / 诚实标注 / 配置化最后一公里 / 标准件
# =========================================================================== #
def test_healthz_contract(client):
    d = client.get("/healthz").json()
    assert d["status"] == "ok"
    assert d["version"] == S.APP_VERSION
    assert d["config_source"] == "services.yaml"
    assert d["services_total"] == 7
    assert 0 <= d["services_online"] <= 7
    assert isinstance(d["uptime_sec"], (int, float)) and d["uptime_sec"] >= 0
    assert len(d["services"]) == 7


def test_404_returns_hint_json(client):
    r = client.get("/api/v1/definitely-not-here")
    assert r.status_code == 404
    d = r.json()
    assert d["status"] == "not_found"
    assert d["path"].endswith("definitely-not-here")
    assert "hint" in d, "404 必须带人话提示，不能是裸 detail"


def test_analysis_overview_marks_source_and_latency(client):
    d = client.get("/api/v1/analysis/overview").json()
    assert d["metrics_source"] == "demo-sample", "经营数字必须标注是样例"
    assert isinstance(d["latency_ms"], int) and d["latency_ms"] >= 0


def test_failover_primary_model_is_placeholder(client):
    d = client.post("/api/v1/gateway/simulate_failover").json()
    assert d["primary_model"] == "上游主模型（仿真占位）", "仿真端点不得冒充真实模型名"
    assert d["token_usage_note"], "token 用量必须注明是样例"


def test_guide_upstream_comes_from_topology():
    """导购链路的上游端口/路径必须取自拓扑，而不是硬编码 —— 2.1 之前的漏洞。"""
    meta = {s["id"]: s for s in S.SERVICES_META}
    guide = meta["ecom-ai-guide"]
    assert S.GUIDE_PORT == guide["port"]
    assert S.GUIDE_CHAT_PATH == guide.get("chat_path", "/api/chat")


def test_favicon_present_and_wired_everywhere():
    p = BASE / "static" / "favicon.svg"
    assert p.exists() and p.stat().st_size > 200
    assert 'rel="icon"' in read("templates/index.html")
    assert "/static/favicon.svg" in read("templates/index.html")
    # docs 是渲染产物：路径应已被改写为相对路径且文件被复制
    assert "./static/favicon.svg" in read("docs/index.html")
    assert (BASE / "docs" / "static" / "favicon.svg").exists()


def test_version_single_source():
    """版本号只允许写在 APP_VERSION 一处 —— 页面标题/角标必须是渲染出来的。

    注意：这里【不】写死某个具体版本号（2.0/2.1/2.2…），否则每次发版都会假 FAIL。
    断言写成「模板零写死 + 渲染产物必然带当前 APP_VERSION」，版本怎么升都不会误报。
    """
    v = S.APP_VERSION
    assert v and v[0].isdigit(), "APP_VERSION 应形如 2.2.0"
    tpl = read("templates/index.html")
    # 模板里不允许出现任何「OmniAgent Platform <数字>」形态的写死版本号
    assert not re.search(r"OmniAgent Platform \d", tpl), "模板里写死了版本号"
    assert not re.search(r"Platform v\d", tpl), "侧边栏角标写死了版本号"
    docs = read("docs/index.html")
    assert "OmniAgent Platform %s" % v in docs, "渲染产物 title 应带当前 APP_VERSION"
    # 侧边栏角标只显示主次版本号（模板里 [:3] 截断），所以这里比对的也是截短后的
    assert "Platform v%s" % v[:3] in docs, "渲染产物角标应带当前 APP_VERSION"


def test_docs_404_page_exists():
    p = BASE / "docs" / "404.html"
    assert p.exists()
    txt = p.read_text(encoding="utf-8")
    assert "404" in txt and "返回" in txt


# =========================================================================== #
# 6. 2.2 新增：历史持久化 / 服务起停管控
# =========================================================================== #
def test_history_probes_contract(client):
    d = client.get("/api/v1/history/probes", params={"minutes": 30, "buckets": 60}).json()
    assert d["status"] == "ok"
    assert d["minutes"] == 30
    assert d["source"] in ("sqlite-history", "monitor-not-started")
    assert len(d["series"]) == len(S.SERVICES_META)
    ids = {x["id"] for x in d["series"]}
    assert ids == {s["id"] for s in S.SERVICES_META}
    for item in d["series"]:
        assert isinstance(item["points"], list)


def test_history_probes_clamps_params(client):
    """越界参数必须被夹回合法区间，而不是把窗口交给 SQL 去炸。"""
    d = client.get("/api/v1/history/probes", params={"minutes": 99999, "buckets": 0}).json()
    assert 1 <= d["minutes"] <= 1440
    assert d["bucket_sec"] > 0


def test_events_recent_contract(client):
    d = client.get("/api/v1/events/recent", params={"limit": 5}).json()
    assert d["status"] == "ok" and d["limit"] == 5
    assert d["source"] in ("sqlite-history", "monitor-not-started")
    assert isinstance(d["events"], list)
    assert len(d["events"]) <= 5
    for e in d["events"]:
        # 回放出来的事件必须能直接喂给前端渲染
        assert {"ts", "tag", "level", "msg"} <= set(e)


def test_control_capabilities_contract(client):
    d = client.get("/api/v1/services/control-capabilities").json()
    assert d["status"] == "ok" and d["can_stop"] is True
    assert len(d["services"]) == len(S.SERVICES_META)
    by_id = {x["id"]: x for x in d["services"]}
    for s in S.SERVICES_META:
        # can_start 必须如实反映 yaml 里有没有配 start_cmd —— 没配就别在前端装能启动
        assert by_id[s["id"]]["can_start"] is bool(s.get("start_cmd"))
        assert by_id[s["id"]]["port"] == s["port"]


def test_stop_unknown_service_returns_actionable_404(client):
    r = client.post("/api/v1/services/does-not-exist/stop")
    assert r.status_code == 404
    body = r.json()
    # 404 要带「人话提示 + 可选 id 清单」，而不是裸的 {"detail": "Not Found"}
    assert body.get("hint") or body.get("detail")
    assert "does-not-exist" in json.dumps(body, ensure_ascii=False)


def test_start_without_cmd_is_honest(client):
    """没在 services.yaml 里配 start_cmd 的服务，必须如实说不会启动，不能假装成功。"""
    caps = client.get("/api/v1/services/control-capabilities").json()
    target = next(x["id"] for x in caps["services"] if not x["can_start"])
    r = client.post("/api/v1/services/%s/start" % target)
    assert r.status_code == 200
    d = r.json()
    if d.get("reason") == "already-online":
        pytest.skip("该服务当前在线，跳过 not-configured 分支")
    assert d["started"] is False
    assert d["reason"] == "not-configured", "未配置启动命令时应如实返回 not-configured"
    assert d["detail"], "要告诉用户怎么才能启用启动按钮"


def test_stop_kills_only_the_configured_port_listener(client):
    """端到端：自己拉一个假监听进程，点「停止」，它必须死 —— 且不能误杀别人。

    安全性：被杀的一定是本测试自己 spawn 的子进程，
    绝不会碰到老板正在跑的其它进程（stop 端只杀监听在配置端口上的 PID）。
    """
    import subprocess
    import time as _time

    online = client.get("/api/v1/overview/stats").json()
    states = {s["id"]: s for s in online["services"]}
    target = next((s for s in S.SERVICES_META if states.get(s["id"], {}).get("status") != "online"), None)
    if target is None:
        pytest.skip("7 个服务全部在线，没有空闲端口可安全演练 stop")

    port = target["port"]
    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import socket,time;s=socket.socket();"
            "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);"
            "s.bind(('127.0.0.1',%d));s.listen(1);time.sleep(90)" % port,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = _time.time() + 10
        while _time.time() < deadline:
            if client.get("/api/v1/services/control-capabilities").status_code == 200:
                st = client.get("/api/v1/overview/stats").json()
                cur = next(s for s in st["services"] if s["id"] == target["id"])
                if cur["status"] == "online":
                    break
            _time.sleep(0.3)
        else:
            pytest.skip("假监听进程未能就绪，跳过")

        d = client.post("/api/v1/services/%s/stop" % target["id"]).json()
        assert d["port"] == port
        assert d["stopped"] is True, "点了停止却没杀掉监听进程：%r" % d
        assert d["pids"], "应返回被终止的 PID 清单以便审计"
        assert os.getpid() not in d["pids"], "绝不能把控制台/测试进程自己算进去"

        child.wait(timeout=15)
        assert child.poll() is not None, "假监听进程没有被真正终止"
    finally:
        if child.poll() is None:
            child.kill()


# =========================================================================== #
# 6. 容器化与监听地址（配置漂移守卫）
#    背景：容器里进程若只 bind 127.0.0.1，Docker 的端口发布（-p 8888:8888）转发到
#    容器 eth0，宿主机打不通；而容器 healthcheck 从 loopback 打是通的 —— 于是变成
#    「显示健康、实际访问不了」的静默失败。这组断言把这条锁死。
# =========================================================================== #
def test_local_defaults_bind_loopback_only():
    """本机运行默认只监听回环 —— 不把控制台意外暴露到局域网。"""
    assert S.BIND_HOST == "127.0.0.1"
    assert S.PROBE_HOST == "127.0.0.1"


def test_uvicorn_uses_configurable_bind_host():
    """启动必须走 BIND_HOST；写死 127.0.0.1 会让容器端口发布失效。"""
    src = read("server.py")
    assert "uvicorn.run(app, host=BIND_HOST" in src, "启动未使用 BIND_HOST"
    assert 'uvicorn.run(app, host="127.0.0.1"' not in src, "启动又把监听地址写死了"


@pytest.mark.parametrize(
    "needle",
    [
        "asyncio.open_connection(PROBE_HOST",  # 端口探测
        '"http://%s:%d%s" % (PROBE_HOST',  # 导购上游
    ],
)
def test_probe_paths_use_probe_host(needle):
    """探测与导购上游都要走 PROBE_HOST，否则容器里永远探不到宿主机服务。"""
    assert needle in read("server.py")


def test_dockerfile_sets_container_networking():
    df = read("Dockerfile")
    assert "OMNI_HOST=0.0.0.0" in df, "镜像里没把监听地址设成 0.0.0.0，端口发布打不通"
    assert "OMNI_PROBE_HOST=host.docker.internal" in df, "镜像里没把探测地址指向宿主机"
    assert "HEALTHCHECK" in df
    assert "USER omni" in df, "镜像应以非 root 运行"


def test_compose_agrees_with_dockerfile_on_networking():
    yml = read("docker-compose.yml")
    assert "OMNI_HOST: 0.0.0.0" in yml
    assert "OMNI_PROBE_HOST: host.docker.internal" in yml
    # 非 root + 绑定挂载会让 uid 1000 写不进 SQLite（宿主机 data/ 被 root 创建）
    assert "omni-data:/app/data" in yml, "历史库应该用命名卷，而不是绑定挂载"
    assert "./data:/app/data" not in yml, "绑定挂载会踩非 root 写权限的坑"


def test_healthz_reports_networking(client):
    """排障用：healthz 要能一眼看出 bind 到哪、探的是谁。"""
    net = client.get("/healthz").json().get("networking") or {}
    assert net.get("bind_host") == S.BIND_HOST
    assert net.get("probe_host") == S.PROBE_HOST
