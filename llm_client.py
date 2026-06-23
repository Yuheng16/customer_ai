import os
import json
import re
import httpx
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")


async def call_deepseek(
    prompt: str,
    system_prompt: str = "你是一个专业的电商客服专家",
    image_urls: list = None,
    temperature: float = 0.7,
    max_tokens: int = 1024
) -> str:
    """
    调用 DeepSeek API（支持纯文本和多模态图片分析）
    """
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    if image_urls and len(image_urls) > 0:
        content_parts = [{"type": "text", "text": prompt}]
        for url in image_urls:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": url}
            })
        user_message = {"role": "user", "content": content_parts}
        model = "deepseek-chat"
    else:
        user_message = {"role": "user", "content": prompt}
        model = "deepseek-chat"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            user_message
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            json=payload,
            headers=headers
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


def parse_ai_response(raw_text: str) -> dict:
    """
    解析 AI 返回的 JSON 结果。
    预期格式：
    {
      "buyer_intent": "...",
      "buyer_emotion": "...",
      "solution": "...",
      "reply_options": [{"style": "...", "text": "..."}, ...]
    }
    """
    parsed = None

    # 1. 直接解析 JSON
    try:
        parsed = json.loads(raw_text)
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. 提取 JSON 代码块
    if parsed is None:
        m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw_text, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(1))
            except (json.JSONDecodeError, ValueError):
                pass

    # 3. 如果解析成功，提取字段
    if isinstance(parsed, dict):
        reply_options = parsed.get("reply_options", [])
        if isinstance(reply_options, list):
            reply_options = [
                {"style": r.get("style", ""), "text": r.get("text", "")}
                if isinstance(r, dict) else {"style": "", "text": str(r)}
                for r in reply_options
            ]
        else:
            reply_options = []

        return {
            "buyer_intent": parsed.get("buyer_intent", ""),
            "buyer_emotion": parsed.get("buyer_emotion", ""),
            "product_highlight": parsed.get("product_highlight", ""),
            "practical_point": parsed.get("practical_point", ""),
            "solution": parsed.get("solution", ""),
            "reply_options": reply_options
        }

    # 4. 兜底
    return {
        "buyer_intent": "",
        "buyer_emotion": "",
        "product_highlight": "",
        "practical_point": "",
        "solution": "",
        "reply_options": [{"style": "通用回复", "text": raw_text.strip()}]
    }
