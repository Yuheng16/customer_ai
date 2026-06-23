import os
import json
import re
import base64
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


async def call_deepseek_ocr(image_base64: str) -> str:
    """
    调用 DeepSeek 视觉模型进行 OCR 识别，从千牛退款详情页截图中提取结构化字段。
    如果 VISION_MODEL 未设置，回退到纯文本模型并提示不可用。
    """
    if not VISION_MODEL:
        return json.dumps({
            "order_number": "", "product_name": "", "refund_amount": "",
            "refund_reason": "", "application_time": "", "logistics_number": "",
            "logistics_status": "",
            "raw_text": "OCR 不可用：未配置 VISION_MODEL 环境变量"
        }, ensure_ascii=False)

    system_prompt = (
        "你是一个专业的电商OCR识别助手。你的任务是从淘宝/天猫千牛卖家中心的退款详情页截图中，"
        "准确提取以下字段的信息。\n\n"
        "提取规则：\n"
        "1. 订单编号：通常是一串纯数字，长度约15-20位，标签可能是「订单编号」「订单号」「交易号」\n"
        "2. 商品名称：退款涉及的商品标题文字\n"
        "3. 退款金额：退款金额数字，格式如 ¥XX.XX 或 XX.XX元，只提取数字部分\n"
        "4. 退款原因：买家选择的退款原因，如「仅退款」「退货退款」「换货」等\n"
        "5. 申请时间：退款申请的时间，格式如 2024-01-15 14:30:25 或 2024年1月15日\n"
        "6. 物流单号：如果有物流信息，提取快递单号\n"
        "7. 物流状态：提取物流状态，如「未发货」「运输中」「已签收」「未签收」等\n\n"
        "重要：\n"
        "- 只提取截图中实际存在的信息，字段留空比填错更好\n"
        "- 如果某个字段在截图中找不到，对应字段返回空字符串\n"
        "- 同时返回截图中所有识别到的文本内容（raw_text字段），供人工核对\n"
        "- 严格按照以下 JSON 格式输出，不要添加任何其他内容"
    )

    ocr_output_format = (
        '{\n'
        '  "order_number": "提取到的订单编号",\n'
        '  "product_name": "提取到的商品名称",\n'
        '  "refund_amount": "提取到的退款金额数字",\n'
        '  "refund_reason": "提取到的退款原因",\n'
        '  "application_time": "提取到的申请时间",\n'
        '  "logistics_number": "提取到的物流单号",\n'
        '  "logistics_status": "提取到的物流状态",\n'
        '  "raw_text": "从截图中识别到的所有文本内容，保留换行"'
        '\n}'
    )

    prompt = f"请从这张千牛退款详情页截图中提取订单信息。\n\n请严格按照以下 JSON 格式输出：\n{ocr_output_format}"

    # 处理 base64 图片：如果太大（>1MB），压缩提示
    img_size_kb = len(image_base64) / 1024
    if img_size_kb > 1000:
        print(f"OCR 警告：图片较大 ({img_size_kb:.0f}KB)，可能导致请求失败")

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    # 确保 base64 有 data URI 前缀
    img_url = image_base64
    if not image_base64.startswith("data:"):
        # 检测图片格式（默认 jpeg）
        if image_base64.startswith("/9j/"):
            img_url = f"data:image/jpeg;base64,{image_base64}"
        elif image_base64.startswith("iVBOR"):
            img_url = f"data:image/png;base64,{image_base64}"
        else:
            img_url = f"data:image/png;base64,{image_base64}"

    payload = {
        "model": VISION_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": img_url}}
                ]
            }
        ],
        "temperature": 0.1,  # 低温度以提高提取准确性
        "max_tokens": 1024
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            json=payload,
            headers=headers
        )

        if resp.status_code == 400:
            body = resp.text
            print(f"DeepSeek OCR 400 错误: {body[:500]}")
            raise Exception(f"DeepSeek OCR API 400: {body[:300]}")

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
