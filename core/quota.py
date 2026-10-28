"""
OmniAgent Platform — 真实配额 (Tenant Quota)

之前网关的"限流分流"是一条仿真日志：``FAILOVER_SCENARIOS`` 里写着 429，但服务端从来
没有真的拒绝过任何请求。这个模块把配额落成真的——超阈值直接 429，带剩余额度响应头。

设计取舍：
* **按租户计数**，不是按 IP：网关代理的是模型调用，成本落在租户头上；
* **双窗口**：分钟窗口挡突发（脚本全速刷），天窗口挡慢速刷穿（每秒 1 次跑一天）；
* **进程内存**：单进程够用；多副本要换 Redis，接口不用变，这一点写进 README 不藏着。

计数只在通过鉴权的请求上做——未认证的请求先被 401 挡掉，不消耗配额。
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field

MINUTE = 60.0
DAY = 86400.0


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


@dataclass(frozen=True)
class QuotaDecision:
    """一次配额判定的结果。allowed=False 时 response 该是 429。"""

    allowed: bool
    tenant_id: str
    limit: int
    remaining: int
    retry_after: int = 0
    window: str = "minute"
    used_today: int = 0

    def headers(self) -> dict[str, str]:
        headers = {
            "X-Quota-Limit": str(self.limit),
            "X-Quota-Remaining": str(self.remaining),
            "X-Quota-Window": self.window,
            "X-Quota-Tenant": self.tenant_id,
            "X-Quota-Used-Today": str(self.used_today),
        }
        if not self.allowed:
            headers["Retry-After"] = str(self.retry_after)
        return headers


@dataclass
class TenantQuota:
    per_minute: int = 30
    per_day: int = 5000
    _minute: dict[str, deque] = field(default_factory=dict, repr=False)
    _day: dict[str, deque] = field(default_factory=dict, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    blocked_total: int = 0

    @staticmethod
    def _prune(bucket: deque, now: float, window: float) -> None:
        while bucket and now - bucket[0] > window:
            bucket.popleft()

    def consume(self, tenant_id: str, now: float | None = None) -> QuotaDecision:
        """记一次调用。超了就返回 allowed=False，调用方负责回 429。"""
        now = time.time() if now is None else now
        with self._lock:
            minute = self._minute.setdefault(tenant_id, deque())
            self._prune(minute, now, MINUTE)
            day = self._day.setdefault(tenant_id, deque())
            self._prune(day, now, DAY)

            if len(minute) >= self.per_minute:
                self.blocked_total += 1
                wait = int(MINUTE - (now - minute[0])) + 1
                return QuotaDecision(False, tenant_id, self.per_minute, 0, wait, "minute", len(day))

            if self.per_day and len(day) >= self.per_day:
                self.blocked_total += 1
                wait = int(DAY - (now - day[0])) + 1
                return QuotaDecision(False, tenant_id, self.per_day, 0, wait, "day", len(day))

            minute.append(now)
            day.append(now)
            return QuotaDecision(
                allowed=True,
                tenant_id=tenant_id,
                limit=self.per_minute,
                remaining=max(self.per_minute - len(minute), 0),
                used_today=len(day),
            )

    def peek(self, tenant_id: str) -> dict:
        """只读当前用量，不扣额度——给控制台/排查用。"""
        now = time.time()
        with self._lock:
            minute = self._minute.get(tenant_id, deque())
            day = self._day.get(tenant_id, deque())
            used_minute = sum(1 for ts in minute if now - ts <= MINUTE)
            used_day = sum(1 for ts in day if now - ts <= DAY)
        return {
            "tenant_id": tenant_id,
            "limit_per_minute": self.per_minute,
            "used_last_minute": used_minute,
            "remaining": max(self.per_minute - used_minute, 0),
            "limit_per_day": self.per_day,
            "used_today": used_day,
        }

    def reset(self) -> None:
        with self._lock:
            self._minute.clear()
            self._day.clear()
            self.blocked_total = 0


# 模块级单例：进程内共享一份计数。测试可以 monkeypatch 字段或直接 reset()。
quota = TenantQuota(
    per_minute=_env_int("OMNI_QUOTA_PER_MINUTE", 30),
    per_day=_env_int("OMNI_QUOTA_PER_DAY", 5000),
)
