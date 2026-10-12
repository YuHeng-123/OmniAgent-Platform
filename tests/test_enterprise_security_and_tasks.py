"""
OmniAgent Platform - 企业级多租户隔离、JWT鉴权守卫与分布式异步任务测试套件
验证 Phase 2 & Phase 3 企业准入与生产级可用特性。
"""

import time

from fastapi.testclient import TestClient

from core.security import create_tenant_jwt, decode_tenant_jwt
from server import app

client = TestClient(app)


def test_jwt_token_creation_and_decoding():
    token = create_tenant_jwt(tenant_id="tenant-gold-001", role="operator", user_id="user-ops")
    assert token and "." in token
    decoded = decode_tenant_jwt(token)
    assert decoded is not None
    assert decoded["tenant_id"] == "tenant-gold-001"
    assert decoded["role"] == "operator"
    assert decoded["sub"] == "user-ops"


def test_auth_token_issuance_and_tenant_me_inspection():
    resp = client.post(
        "/api/v1/auth/token",
        json={"tenant_id": "tenant-luxury-asia", "role": "admin", "user_id": "usr-admin-hk"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["tenant_id"] == "tenant-luxury-asia"
    token = data["access_token"]

    # 使用生成的 Token 访问 /auth/me
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    ctx = me_data["tenant_context"]
    assert ctx["tenant_id"] == "tenant-luxury-asia"
    assert ctx["role"] == "admin"
    assert ctx["auth_type"] == "jwt"
    assert ctx["is_authenticated"] is True


def test_rbac_guard_blocks_unauthorized_viewer_from_stopping_service():
    # 构造只读角色 viewer 的请求
    viewer_token = create_tenant_jwt(tenant_id="tenant-readonly", role="viewer", user_id="guest-01")
    resp = client.post(
        "/api/v1/services/ai-gateway/stop",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 403
    err = resp.json()
    assert "PERMISSION_DENIED" in str(err) or "无权执行" in str(err)


def test_async_background_task_funclip_flow():
    # 发起后台异步切片任务
    resp = client.post(
        "/api/v1/labs/funclip/slice?async_task=true",
        json={"sample_id": "sample-1", "hotwords": "翡翠, 碧玉"},
        headers={"X-Tenant-ID": "tenant-media-lab"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["async"] is True
    assert data["status"] == "accepted"
    task_id = data["task_id"]
    assert task_id.startswith("task-funclip")

    # 稍等异步协程调度完成
    time.sleep(0.1)

    # 查询任务详情
    task_resp = client.get(f"/api/v1/tasks/{task_id}", headers={"X-Tenant-ID": "tenant-media-lab"})
    assert task_resp.status_code == 200
    task_data = task_resp.json()["task"]
    assert task_data["status"] in ("RUNNING", "COMPLETED")
    assert task_data["tenant_id"] == "tenant-media-lab"

    # 查询任务列表
    list_resp = client.get("/api/v1/tasks", headers={"X-Tenant-ID": "tenant-media-lab"})
    assert list_resp.status_code == 200
    tasks = list_resp.json()["tasks"]
    assert any(t["task_id"] == task_id for t in tasks)
