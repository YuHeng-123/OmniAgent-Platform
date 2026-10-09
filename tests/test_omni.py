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
import pathlib
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
    bad.write_text("services:\n  - id: broken\n", encoding="utf-8")   # 缺 port
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
    assert json.loads(frame[len("data: "):].strip())["msg"] == "中文消息"


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
    for rel in ("static/vendor/tailwind.js", "static/vendor/chart.umd.js",
                "static/omni-api.js", "static/vendor/fontawesome/css/all.min.css"):
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


@pytest.mark.parametrize("rel", ["templates/index.html", "static/omni-api.js"])
def test_no_fabricated_driver_model(rel):
    txt = read(rel)
    assert "Gemini-3.8-Flash" not in txt
    assert "DeepSeek-V3 / Flash" not in txt, "前端不该硬写一个并不存在的驱动模型"


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
    for rel in ("docs/static/omni-api.js", "docs/static/vendor/tailwind.js",
                "docs/static/vendor/chart.umd.js",
                "docs/static/vendor/fontawesome/css/all.min.css"):
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
    d = client.post("/api/v1/guide/chat",
                    json={"message": "你们支持刻字定制吗？", "history": []}).json()
    assert d["backend"].startswith(("live:", "fallback:")), "必须如实标注这次是谁答的"
    assert isinstance(d["latency_ms"], int) and d["latency_ms"] >= 0
    assert len(d["trace"]) >= 2
    assert d["reply"]


def test_guide_self_correction_path(client):
    d = client.post("/api/v1/guide/chat",
                    json={"message": "有500元无门槛券吗", "history": []}).json()
    assert d["self_corrected"] is True
    assert any(s["status"] == "retry" for s in d["trace"])


def test_marketing_flags_banned_words(client):
    d = client.post("/api/v1/marketing/generate", json={
        "product_name": "全网唯一顶级和田玉吊坠",
        "target_platform": "xiaohongshu",
        "keywords": "第一",
    }).json()
    words = {v["word"] for v in d["compliance"]["violations"]}
    assert {"顶级", "第一", "全网唯一"} <= words
    assert d["compliance"]["status"] == "WARNING"
    assert d["compliance"]["score"] < 100


def test_marketing_clean_copy_passes(client):
    d = client.post("/api/v1/marketing/generate", json={
        "product_name": "和田碧玉平安扣吊坠",
        "target_platform": "douyin",
        "keywords": "",
    }).json()
    assert d["compliance"]["status"] == "PASS"
    assert d["compliance"]["score"] == 100
    assert "violations" in d["compliance"]


@pytest.mark.parametrize("q,ctype", [
    ("按品类统计销售额", "bar"),
    ("各渠道成交额", "pie"),
    ("近半年销售趋势", "line"),
])
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
                    got.append(json.loads(line[len("data:"):].strip()))
                if len(got) >= 1 + len(S.SERVICES_META):
                    break
    assert len(got) >= 1 + len(S.SERVICES_META)
    assert got[0]["tag"] == "MASTER"
    assert len(got[1:1 + len(S.SERVICES_META)]) == len(S.SERVICES_META)
