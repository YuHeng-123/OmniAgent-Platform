"""
OmniAgent Platform — 网关鉴权与配额：证明"真的拦得住"

三条断言思路，都不看日志、只看响应：
  1. 不带 Token / 带坏 Token → 401（以前坏 Token 会降级成默认 admin）
  2. 超配额 → 429，带 Retry-After 与剩余额度头，且**没有 choices**（说明没走生成）
  3. 配额按租户隔离：A 用完不影响 B
"""

import pytest
from fastapi.testclient import TestClient

from core.quota import quota
from core.security import create_tenant_jwt
from server import app

client = TestClient(app)

PAYLOAD = {
    "model": "qwen-max",
    "messages": [{"role": "user", "content": "帮我看一下今天的订单"}],
}


def _token(tenant="tenant-quota-test", role="operator"):
    return {"Authorization": f"Bearer {create_tenant_jwt(tenant_id=tenant, role=role)}"}


@pytest.fixture(autouse=True)
def clean_quota():
    quota.reset()
    yield
    quota.reset()


def test_proxy_requires_a_token():
    resp = client.post("/v1/chat/completions", json=PAYLOAD)
    assert resp.status_code == 401
    detail = resp.json()["detail"]
    assert detail["error"] == "AUTH_REQUIRED"
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


def test_invalid_token_does_not_fall_back_to_admin():
    """旧行为：坏 Token → 落到默认开发租户（admin）。这是真洞。"""

    resp = client.post(
        "/v1/chat/completions",
        json=PAYLOAD,
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert resp.status_code == 401


def test_header_only_identity_is_not_enough_for_the_proxy():
    """X-Tenant-ID 谁都能编。只读接口用它图方便，花钱的接口不能认。"""

    resp = client.post(
        "/v1/chat/completions",
        json=PAYLOAD,
        headers={"X-Tenant-ID": "tenant-hq", "X-Role": "admin"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"] == "JWT_REQUIRED"


def test_valid_token_passes_and_reports_tenant():
    resp = client.post("/v1/chat/completions", json=PAYLOAD, headers=_token("tenant-hq"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["tenant_id"] == "tenant-hq"
    assert body["upstream"] == "simulated", "上游仍是仿真，必须在响应里说清楚"
    assert resp.headers["X-Quota-Remaining"].isdigit()


def test_quota_blocks_with_429_and_headers(monkeypatch):
    monkeypatch.setattr(quota, "per_minute", 2)
    headers = _token("tenant-tight")

    assert client.post("/v1/chat/completions", json=PAYLOAD, headers=headers).status_code == 200
    assert client.post("/v1/chat/completions", json=PAYLOAD, headers=headers).status_code == 200

    blocked = client.post("/v1/chat/completions", json=PAYLOAD, headers=headers)
    assert blocked.status_code == 429
    detail = blocked.json()["detail"]
    assert detail["error"] == "TENANT_QUOTA_EXCEEDED"
    assert detail["limit"] == 2
    assert blocked.headers["Retry-After"].isdigit()
    assert blocked.headers["X-Quota-Remaining"] == "0"
    assert "choices" not in blocked.json(), "被拦的请求不该走生成，所以没有 choices"


def test_quota_is_per_tenant(monkeypatch):
    monkeypatch.setattr(quota, "per_minute", 1)
    a, b = _token("tenant-a"), _token("tenant-b")

    assert client.post("/v1/chat/completions", json=PAYLOAD, headers=a).status_code == 200
    assert client.post("/v1/chat/completions", json=PAYLOAD, headers=a).status_code == 429
    # b 有自己的额度
    assert client.post("/v1/chat/completions", json=PAYLOAD, headers=b).status_code == 200


def test_quota_endpoint_is_read_only():
    headers = _token("tenant-peek")
    first = client.get("/api/v1/gateway/quota", headers=headers).json()
    assert first["used_last_minute"] >= 0

    client.post("/v1/chat/completions", json=PAYLOAD, headers=headers)
    after = client.get("/api/v1/gateway/quota", headers=headers).json()
    assert after["used_last_minute"] == first["used_last_minute"] + 1

    # 只是查询，不该再涨
    again = client.get("/api/v1/gateway/quota", headers=headers).json()
    assert again["used_last_minute"] == after["used_last_minute"]


def test_security_sensitive_action_still_403_for_viewer():
    """加固之后，原来的 RBAC 断言不能松：viewer 依旧不能起停服务。"""

    viewer = {"Authorization": f"Bearer {create_tenant_jwt(tenant_id='tenant-ro', role='viewer')}"}
    resp = client.post("/api/v1/services/ai-gateway/stop", headers=viewer)
    assert resp.status_code == 403
