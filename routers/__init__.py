"""
OmniAgent Platform - 企业级 API 路由分片模块包 (Routers Package)
"""

from routers.business import router as business_router
from routers.events import router as events_router
from routers.gateway import router as gateway_router
from routers.labs import router as labs_router
from routers.system import router as system_router

__all__ = [
    "system_router",
    "events_router",
    "gateway_router",
    "business_router",
    "labs_router",
]
