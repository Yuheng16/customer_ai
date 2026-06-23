from pydantic import BaseModel
from typing import Optional, List


class ChatMessage(BaseModel):
    """单条聊天消息"""
    role: str = "buyer"
    content: str


class ReplyOption(BaseModel):
    """单条话术选项"""
    style: str = ""
    text: str = ""


class AnalyzeRequest(BaseModel):
    order_text: str
    image_urls: Optional[List[str]] = []   # 图片 URL 或 base64 data URL
    scenario: Optional[str] = "general"
    history: Optional[List[ChatMessage]] = []


class AnalyzeResponse(BaseModel):
    buyer_intent: str = ""                  # 买家意图
    buyer_emotion: str = ""                 # 买家情绪
    product_highlight: str = ""             # 商品核心卖点
    practical_point: str = ""               # 商品实用价值
    solution: str = ""                      # 综合解决方案
    reply_options: List[ReplyOption] = []   # 3种风格话术
