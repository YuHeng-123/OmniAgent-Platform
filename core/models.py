"""
OmniAgent Platform - 企业级请求/响应契约模型 (Core Models)
使用 Pydantic BaseModel 规范化各端点入参与出参格式。
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class GuideChatRequest(BaseModel):
    message: str = ""
    history: Optional[List[Dict[str, Any]]] = None


class GenerateMarketingRequest(BaseModel):
    product_name: str = ""
    target_platform: str = "xiaohongshu"
    keywords: str = ""
    selling_points: str = ""


class AnalysisQueryRequest(BaseModel):
    query_text: str = ""


class OpenAIChatMessage(BaseModel):
    role: str = "user"
    content: str = ""


class OpenAIChatRequest(BaseModel):
    model: Optional[str] = "qwen-max"
    messages: List[OpenAIChatMessage] = []
    temperature: Optional[float] = 0.7
    stream: Optional[bool] = False


class LabsXhsGenerateRequest(BaseModel):
    product_name: str = ""
    tone: str = "闺蜜真实种草"
    keywords: str = ""
    hitl_approved_topic: str = ""


class LabsFunclipSliceRequest(BaseModel):
    sample_id: str = "sample-1"
    hotwords: str = ""
    diarization: bool = True
