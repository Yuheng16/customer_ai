"""
OCR 服务：调用 DeepSeek 视觉模型从千牛退款详情页截图中提取结构化订单字段。
"""
import json
import re
from llm_client import call_deepseek_ocr


async def ocr_extract_fields(image_base64: str) -> dict:
    """
    从截图 base64 中提取订单结构化字段。

    Args:
        image_base64: 截图的 base64 编码字符串（可带或不带 data URI 前缀）

    Returns:
        dict: {
            order_number, product_name, refund_amount, refund_reason,
            application_time, logistics_number, logistics_status, raw_text
        }
    """
    raw_result = await call_deepseek_ocr(image_base64)

    # 解析 AI 返回的 JSON
    parsed = _parse_ocr_json(raw_result)

    # 标准化字段值
    result = {
        "order_number": _clean_field(parsed.get("order_number", "")),
        "product_name": _clean_field(parsed.get("product_name", "")),
        "refund_amount": _extract_amount(parsed.get("refund_amount", "")),
        "refund_reason": _normalize_reason(parsed.get("refund_reason", "")),
        "application_time": _clean_field(parsed.get("application_time", "")),
        "logistics_number": _clean_field(parsed.get("logistics_number", "")),
        "logistics_status": _normalize_logistics(parsed.get("logistics_status", "")),
        "raw_text": parsed.get("raw_text", raw_result[:500]),
    }

    return result


def _parse_ocr_json(raw_text: str) -> dict:
    """解析 OCR 返回的 JSON，处理 markdown 代码块包裹等情况"""
    parsed = None

    # 直接解析
    try:
        parsed = json.loads(raw_text)
    except (json.JSONDecodeError, ValueError):
        pass

    # 尝试提取 markdown 代码块
    if parsed is None:
        m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw_text, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(1))
            except (json.JSONDecodeError, ValueError):
                pass

    # 尝试提取第一个 JSON 对象
    if parsed is None:
        m = re.search(r'\{[^{}]*\}', raw_text, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except (json.JSONDecodeError, ValueError):
                pass

    return parsed if isinstance(parsed, dict) else {"raw_text": raw_text}


def _clean_field(value: str) -> str:
    """清理字段值：去除多余空格、换行、特殊字符"""
    if not value:
        return ""
    return value.strip().replace("\n", " ").replace("\r", "")


def _extract_amount(value: str) -> str:
    """从退款金额文本中提取纯数字金额"""
    if not value:
        return ""
    # 匹配数字部分，如 ¥12.34, 12.34元, 12.34
    m = re.search(r'[\d.]+', str(value))
    if m:
        return m.group(0)
    return _clean_field(str(value))


def _normalize_reason(value: str) -> str:
    """标准化退款原因"""
    if not value:
        return ""
    value = _clean_field(str(value))
    reason_map = {
        "仅退款": "仅退款",
        "退货退款": "退货退款",
        "退货": "退货退款",
        "退款": "仅退款",
        "换货": "换货",
        "补发": "补发",
        "维修": "其他",
        "未收到货": "仅退款",
        "已收到货": "退货退款",
        "协商一致": "其他",
    }
    for key, normalized in reason_map.items():
        if key in value:
            return normalized
    # 如果没有匹配到已知类型，返回原始值（限制在已知选项中）
    if value in ["仅退款", "退货退款", "换货", "补发", "其他"]:
        return value
    return "其他" if value else ""


def _normalize_logistics(value: str) -> str:
    """标准化物流状态"""
    if not value:
        return ""
    value = _clean_field(str(value))
    status_map = {
        "未发货": "未发货",
        "运输中": "运输中",
        "已签收": "已签收",
        "签收": "已签收",
        "已收货": "已签收",
        "未签收": "未签收",
        "派送中": "运输中",
        "已揽收": "运输中",
        "无物流": "无物流",
        "无": "无物流",
    }
    for key, normalized in status_map.items():
        if key in value:
            return normalized
    return "无物流" if value else ""
