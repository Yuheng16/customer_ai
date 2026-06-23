from llm_client import call_deepseek, parse_ai_response
from prompts import get_scenario_prompt


async def analyze_order(
    order_text: str,
    image_urls: list = None,
    scenario: str = "general",
    history: list = None
) -> dict:
    """
    分析订单/聊天文本，返回 AI 分析和多风格建议话术

    Returns:
        dict: {
            "buyer_intent": 买家意图,
            "buyer_emotion": 买家情绪,
            "solution": 解决方案,
            "reply_options": [{"style": "风格名", "text": "话术内容"}, ...]
        }
    """

    # 1. 根据场景获取专属系统提示词
    system_prompt = get_scenario_prompt(scenario)

    # 2. 构建完整的用户提示词
    prompt_parts = []

    # 历史对话上下文
    if history and len(history) > 0:
        prompt_parts.append("=== 历史对话记录 ===")
        for msg in history:
            role_label = "买家" if msg.get("role") == "buyer" else "客服"
            prompt_parts.append(f"[{role_label}]: {msg.get('content', '')}")
        prompt_parts.append("")

    # 当前消息
    prompt_parts.append("=== 需要回复的消息 ===")
    prompt_parts.append(order_text)

    if image_urls and len(image_urls) > 0:
        prompt_parts.append(f"\n📷 含 {len(image_urls)} 张图片，请结合图片内容分析")

    prompt = "\n".join(prompt_parts)

    # 3. 调用大模型
    raw_result = await call_deepseek(
        prompt=prompt,
        system_prompt=system_prompt,
        image_urls=image_urls,
        temperature=0.7,
        max_tokens=1024
    )

    # 4. 解析 AI 返回结果
    return parse_ai_response(raw_result)
