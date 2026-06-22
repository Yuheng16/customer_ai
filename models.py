from pydantic import BaseModel
from typing import Optional, List

class AnalyzeRequest(BaseModel):
    order_text: str                # 千牛抓取的订单备注、买家消息等
    image_urls: Optional[List[str]] = []  # 图片链接（插件会预先上传或传可访问链接）

class AnalyzeResponse(BaseModel):
    analysis: str                  # 分析结论（如“买家犹豫不决，需逼单”）
    suggested_reply: str           # 推荐的话术