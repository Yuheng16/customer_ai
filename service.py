from llm_client import call_deepseek

async def analyze_order(order_text: str, image_urls: list) -> dict:
    # 构建完整提示词
    prompt = f"""请根据以下电商订单信息，分析买家状态并给出客服回复建议。

订单/聊天文本：
{order_text}
"""
    if image_urls:
        prompt += f"\n相关图片链接：{', '.join(image_urls)}\n（请假设图片内容能正常读取，结合文本分析）"
    
    prompt += "\n请输出：\n1. 客户意图分析\n2. 建议的回复话术"

    # 调用大模型
    result = await call_deepseek(prompt)
    
    # 简单解析（实际可要求模型返回JSON，再用正则提取）
    # 这里简化处理，直接返回整个结果
    return {
        "analysis": result,
        "suggested_reply": result  # 真实场景可拆分
    }