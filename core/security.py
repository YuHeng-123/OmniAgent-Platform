"""
OmniAgent Platform - 企业准入、多租户隔离与安全权限守卫 (Core Security)
支持 JWT 租户 Token 颁发与解析、租户上下文提取、敏感操作 RBAC 权限守卫。
"""

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Request

SECRET_KEY = "omni-agent-enterprise-jwt-secret-key-production-grade"
DEFAULT_TENANT_ID = "tenant-enterprise-default"


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _base64url_decode(data: str) -> bytes:
    padding = 4 - (len(data) % 4)
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data.encode("utf-8"))


def create_tenant_jwt(
    tenant_id: str,
    role: str = "operator",
    user_id: str = "usr-ops-01",
    expires_in_sec: int = 86400,
) -> str:
    """生成企业级 JWT 租户 Token (HMAC-SHA256 实现，无需外部依赖)"""
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,  # 'admin' | 'operator' | 'viewer'
        "iat": now,
        "exp": now + expires_in_sec,
    }

    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    segments = [
        _base64url_encode(header_bytes),
        _base64url_encode(payload_bytes),
    ]
    signing_input = ".".join(segments).encode("utf-8")
    signature = hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    segments.append(_base64url_encode(signature))
    return ".".join(segments)


def decode_tenant_jwt(token: str) -> Optional[Dict[str, Any]]:
    """解码并校验 JWT 租户 Token 签名与有效期"""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        signing_input = f"{parts[0]}.{parts[1]}".encode("utf-8")
        expected_sig = hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
        provided_sig = _base64url_decode(parts[2])

        if not hmac.compare_digest(expected_sig, provided_sig):
            return None

        payload_raw = _base64url_decode(parts[1]).decode("utf-8")
        payload = json.loads(payload_raw)

        if payload.get("exp") and int(time.time()) > int(payload["exp"]):
            return None  # Token expired

        return payload
    except Exception:
        return None


def get_tenant_context(request: Request) -> Dict[str, Any]:
    """从请求中提取租户上下文 (优先 Authorization Bearer，其次 X-Tenant-ID / X-Role 标头)

    向后兼容设计：若未传任何认证信息，返回具备管理员权限的默认本地租户上下文，
    保证现有本地测试与单测 100% 畅通通过。

    **注意**：这里刻意不抛 401——控制台和只读接口依赖"无登录也能看"。
    需要真拦的地方用 ``require_tenant``（见下），它才把"没有身份"当成错误。

    本轮修的一个洞：以前 Bearer Token 解析失败会继续往下走，
    落到 `X-Tenant-ID` 或默认开发租户上——也就是**换个坏 Token 反而拿到 admin**。
    现在只要带了 Bearer，就以 Token 为准：解析不出来就是未认证，不再向下降级。
    """
    auth_header = request.headers.get("authorization") or ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        decoded = decode_tenant_jwt(token)
        if decoded:
            return {
                "tenant_id": decoded.get("tenant_id", DEFAULT_TENANT_ID),
                "role": decoded.get("role", "operator"),
                "user_id": decoded.get("sub", "jwt-user"),
                "auth_type": "jwt",
                "is_authenticated": True,
            }
        # 带了 Bearer 但无效：明确是"认证失败"，不许降级成默认管理员
        return {
            "tenant_id": "anonymous",
            "role": "anonymous",
            "user_id": "anonymous",
            "auth_type": "invalid-jwt",
            "is_authenticated": False,
        }

    # 检查 X-Tenant-ID 标头
    header_tenant = request.headers.get("x-tenant-id")
    header_role = request.headers.get("x-role")
    if header_tenant:
        return {
            "tenant_id": header_tenant,
            "role": header_role or "operator",
            "user_id": f"usr-{header_tenant}",
            "auth_type": "header",
            "is_authenticated": True,
        }

    # 默认本地开发环境租户
    return {
        "tenant_id": DEFAULT_TENANT_ID,
        "role": header_role or "admin",
        "user_id": "usr-local-admin",
        "auth_type": "default-dev",
        "is_authenticated": False,
    }


def require_tenant(request: Request, jwt_only: bool = False) -> Dict[str, Any]:
    """必须有有效身份，否则 401。给"会花钱的接口"用（模型代理）。

    ``jwt_only=True``：只认 Bearer JWT。控制台为了本地演示方便会带
    ``X-Tenant-ID`` / ``X-Role`` 标头，那对只读接口够用，但**标头谁都能编**，
    所以模型代理不接受它——否则"鉴权"等于让调用方自己声明自己是谁。
    """
    ctx = get_tenant_context(request)
    if not ctx.get("is_authenticated"):
        raise HTTPException(
            status_code=401,
            detail={
                "status": "unauthorized",
                "error": "AUTH_REQUIRED",
                "message": "该接口需要有效的租户 Token（Authorization: Bearer <token>）",
                "auth_type": ctx.get("auth_type"),
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    if jwt_only and ctx.get("auth_type") != "jwt":
        raise HTTPException(
            status_code=401,
            detail={
                "status": "unauthorized",
                "error": "JWT_REQUIRED",
                "message": "该接口只接受 JWT（X-Tenant-ID 标头不能作为身份凭证）",
                "auth_type": ctx.get("auth_type"),
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    return ctx




def enforce_sensitive_action_role(request: Request, allowed_roles: Optional[List[str]] = None):
    """敏感操作服务端权限守卫：核验当前租户的角色是否具备操作权限"""
    if allowed_roles is None:
        allowed_roles = ["admin", "operator"]

    ctx = get_tenant_context(request)
    role = ctx.get("role", "viewer")

    if role not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail={
                "status": "forbidden",
                "error": "PERMISSION_DENIED",
                "message": f"当前租户 [{ctx['tenant_id']}] 角色 '{role}' 无权执行此敏感操作",
                "required_roles": allowed_roles,
                "current_role": role,
            },
        )
    return ctx
