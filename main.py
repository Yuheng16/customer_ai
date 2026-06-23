from fastapi import FastAPI, Depends,HTTPException,Request
from models import AnalyzeRequest, AnalyzeResponse
from service import analyze_order
from database import supabase
from auth import get_current_user, check_usage
from pydantic import BaseModel
from datetime import datetime, timedelta
import secrets, string

app = FastAPI(title="电商AI客服助手")

def generate_activation_code(length=16):
    """生成随机激活码"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))

@app.post("/api/payment/mbd-webhook")
async def mbd_webhook(request: Request):
    """接收面包多支付成功通知"""
    # 验证签名（面包多官方文档提供验证方法）
    payload = await request.json()
    # 这里简化示例：实际应验证 sign 字段，防止伪造请求
    # 参考面包多文档：https://mbd.pub/docs/api/order/notify

    order_id = payload.get("order_id")
    product_id = payload.get("product_id")
    buyer_email = payload.get("buyer_email")  # 注意面包多可能不提供邮箱，需自行处理

    # 根据 product_id 判断购买的是什么套餐（可事先在数据库配置）
    tier_map = {
        "商品ID_pro": "pro",
        "商品ID_premium": "premium",
    }
    tier = tier_map.get(product_id, "pro")
    duration_days = 30  # 月卡

    # 在 activation_codes 表中插入一个未使用的激活码
    code = generate_activation_code()
    supabase.table("activation_codes").insert({
        "code": code,
        "tier": tier,
        "duration_days": duration_days
    }).execute()

    # TODO: 可将激活码通过邮件发送给买家（需要配置邮件服务）
    # 最简单的做法：在官网上提供一个“查询订单激活码”页面，输入订单号即可显示

    return {"status": "ok", "code": code if buyer_email else "please check order page"}

@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest, user=Depends(get_current_user), usage=Depends(check_usage)):
    # 调用 AI 分析
    result = await analyze_order(req.order_text, req.image_urls)

    # 记录本次调用（插入一条新行到 user_usage 表）
    supabase.table("user_usage").insert({"user_id": usage["user_id"]}).execute()

    return AnalyzeResponse(analysis=result["analysis"], suggested_reply=result["suggested_reply"])

class RedeemRequest(BaseModel):
    code: str

@app.post("/api/redeem")
async def redeem_code(req: RedeemRequest, user=Depends(get_current_user)):
    # 查询激活码
    print(f"Looking for code: {req.code}")  # 打印激活码
    try:
        res = supabase.table("activation_codes").select("*").eq("code", req.code).execute()
        print(f"Query result: {res.data}")  # 打印查询结果
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(500, "数据库查询失败")
    if not res.data:
        raise HTTPException(404, "激活码不存在")
    code_data = res.data[0]
    if code_data["is_used"]:
        raise HTTPException(400, "激活码已被使用")
    
    # 标记为已使用
    supabase.table("activation_codes").update({
        "is_used": True,
        "used_by": user.id,
        "used_at": datetime.utcnow().isoformat()
    }).eq("code", req.code).execute()
    
    # 更新用户的订阅等级和到期时间
    now = datetime.utcnow()
    expiry = now + timedelta(days=code_data["duration_days"])
    supabase.table("profiles").update({
        "subscription_tier": code_data["tier"],
        "subscription_expiry": expiry.isoformat()
    }).eq("id", user.id).execute()
    
    return {"message": f"已激活{code_data['tier']}套餐，到期时间 {expiry.strftime('%Y-%m-%d')}"}