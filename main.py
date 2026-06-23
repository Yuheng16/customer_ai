from fastapi import FastAPI, Depends, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from models import AnalyzeRequest, AnalyzeResponse, ReplyOption
from service import analyze_order
from database import supabase
from auth import get_current_user, check_usage
from pydantic import BaseModel
from datetime import datetime, timedelta
import secrets, string

app = FastAPI(title="电商AI客服助手")

# 允许浏览器插件跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def generate_activation_code(length=16):
    """生成随机激活码"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


# ====== 支付与激活码 ======

@app.post("/api/payment/mbd-webhook")
async def mbd_webhook(request: Request):
    """接收面包多支付成功通知"""
    payload = await request.json()

    order_id = payload.get("order_id")
    product_id = payload.get("product_id")
    buyer_email = payload.get("buyer_email", "")

    tier_map = {
        "商品ID_pro": "pro",
        "商品ID_premium": "premium",
    }
    tier = tier_map.get(product_id, "pro")
    duration_days = 30

    code = generate_activation_code()
    supabase.table("activation_codes").insert({
        "code": code,
        "tier": tier,
        "duration_days": duration_days,
        "order_id": order_id,
        "buyer_email": buyer_email,
    }).execute()

    return {"status": "ok", "code": code}


@app.get("/api/payment/lookup")
async def lookup_code(order_id: str = Query(..., description="面包多订单号")):
    """通过面包多订单号查询激活码"""
    try:
        res = supabase.table("activation_codes") \
            .select("code, tier, duration_days, is_used, used_at, created_at") \
            .eq("order_id", order_id) \
            .execute()

        if not res.data:
            raise HTTPException(404, f"未找到订单号 {order_id} 对应的激活码")

        code_data = res.data[0]
        tier_names = {"free": "免费版", "pro": "Pro版", "premium": "高级版"}

        return {
            "code": code_data["code"],
            "tier": tier_names.get(code_data["tier"], code_data["tier"]),
            "duration_days": code_data["duration_days"],
            "is_used": code_data["is_used"],
            "used_at": code_data.get("used_at"),
            "created_at": code_data.get("created_at"),
            "message": "激活码未使用" if not code_data["is_used"] else "该激活码已被使用"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Lookup error: {e}")
        raise HTTPException(500, f"查询失败: {str(e)}")


# ====== AI 分析接口 ======

@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(
    req: AnalyzeRequest,
    user=Depends(get_current_user),
    usage=Depends(check_usage)
):
    """AI 分析：返回买家意图、解决方案、多种风格话术"""
    result = await analyze_order(
        order_text=req.order_text,
        image_urls=req.image_urls,
        scenario=req.scenario or "general",
        history=[h.model_dump() for h in req.history] if req.history else None
    )

    # 记录本次调用
    supabase.table("user_usage").insert({
        "user_id": usage["user_id"]
    }).execute()

    return AnalyzeResponse(
        buyer_intent=result.get("buyer_intent", ""),
        buyer_emotion=result.get("buyer_emotion", ""),
        product_highlight=result.get("product_highlight", ""),
        practical_point=result.get("practical_point", ""),
        solution=result.get("solution", ""),
        reply_options=[ReplyOption(**opt) for opt in result.get("reply_options", [])]
    )


# ====== 场景列表 ======

@app.get("/api/scenarios")
async def list_scenarios():
    """返回所有可用的分析场景"""
    from prompts import get_scenario_list
    return {"scenarios": get_scenario_list()}


# ====== 激活码兑换 ======

class RedeemRequest(BaseModel):
    code: str


@app.post("/api/redeem")
async def redeem_code(req: RedeemRequest, user=Depends(get_current_user)):
    """兑换激活码，升级订阅"""
    print(f"Looking for code: {req.code}")

    try:
        res = supabase.table("activation_codes").select("*").eq("code", req.code).execute()
    except Exception as e:
        print(f"Database query error: {e}")
        raise HTTPException(500, "数据库查询失败")

    if not res.data:
        raise HTTPException(404, "激活码不存在")

    code_data = res.data[0]

    if code_data.get("is_used"):
        raise HTTPException(400, "激活码已被使用")

    supabase.table("activation_codes").update({
        "is_used": True,
        "used_by": user.id,
        "used_at": datetime.utcnow().isoformat()
    }).eq("code", req.code).execute()

    now = datetime.utcnow()
    expiry = now + timedelta(days=code_data.get("duration_days", 30))
    supabase.table("profiles").update({
        "subscription_tier": code_data["tier"],
        "subscription_expiry": expiry.isoformat()
    }).eq("id", user.id).execute()

    return {
        "message": f"已激活{code_data['tier']}套餐，到期时间 {expiry.strftime('%Y-%m-%d')}",
        "tier": code_data["tier"],
        "expiry": expiry.strftime("%Y-%m-%d")
    }
