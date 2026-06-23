import os
import json
import re
import httpx
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

# deepseek-chat 是纯文本模型，不支持图片多模态
# 如需视觉分析，改为 deepseek-vl2 或其他视觉模型
VISION_MODEL = os.getenv("VISION_MODEL", None)  # 设为 "deepseek-vl2" 启用视觉
TEXT_MODEL = "deepseek-chat"


async def call_deepseek(
    prompt: str,
    system_prompt: str = "你是一个专业的电商客服专家",
    image_urls: list = None,
    temperature: float = 0.7,
    max_tokens: int = 1024
) -> str:
    """
    调用 DeepSeek API。有图片时优先用视觉模型，否则用纯文本模型。
    """
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    has_images = image_urls and len(image_urls) > 0
    use_vision = has_images and VISION_MODEL

    if use_vision:
        # 视觉模型：多模态格式
        content_parts = [{"type": "text", "text": prompt}]
        for url in image_urls:
            # 跳过过大的 base64（>500KB），避免 400
            if url.startswith("data:") and len(url) > 500_000:
                continue
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": url}
            })
        user_message = {"role": "user", "content": content_parts}
        model = VISION_MODEL
    else:
        # 纯文本模型：图片信息拼入文本
        if has_images:
            prompt += f"\n\n📷 买家发送了 {len(image_urls)} 张图片。请根据文字内容分析，并假设你能看到这些图片来给出建议。"
        user_message = {"role": "user", "content": prompt}
        model = TEXT_MODEL

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

        # 400 错误时打印详细信息用于调试
        if resp.status_code == 400:
            body = resp.text
            print(f"DeepSeek 400 错误: {body[:500]}")
            raise Exception(f"DeepSeek API 400: {body[:300]}")

        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


def parse_ai_response(raw_text: str) -> dict:
    """
    解析 AI 返回的 JSON 结果。
    """
    parsed = None

    try:
        parsed = json.loads(raw_text)
    except (json.JSONDecodeError, ValueError):
        pass

    if parsed is None:
        m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw_text, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(1))
            except (json.JSONDecodeError, ValueError):
                pass

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

    return {
        "buyer_intent": "",
        "buyer_emotion": "",
        "product_highlight": "",
        "practical_point": "",
        "solution": "",
        "reply_options": [{"style": "通用回复", "text": raw_text.strip()}]
    }
