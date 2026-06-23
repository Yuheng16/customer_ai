from pydantic import BaseModel
from typing import Optional, List


class ChatMessage(BaseModel):
    """单条聊天消息"""
    role: str = "buyer"       # buyer / seller
    content: str


class ReplyOption(BaseModel):
    """单条话术选项"""
    style: str = ""           # 话术风格名称（如"热情专业"）
    text: str = ""            # 话术内容


class AnalyzeRequest(BaseModel):
    order_text: str                # 千牛抓取的订单备注、买家消息等
    image_urls: Optional[List[str]] = []  # 图片链接
    scenario: Optional[str] = "general"   # 场景模式
    history: Optional[List[ChatMessage]] = []  # 历史对话上下文


class AnalyzeResponse(BaseModel):
    buyer_intent: str = ""               # 买家意图（一句话）
    buyer_emotion: str = ""              # 买家情绪状态
    solution: str = ""                   # 建议的解决方案
    reply_options: List[ReplyOption] = []  # 多种话术选项（3种风格）
