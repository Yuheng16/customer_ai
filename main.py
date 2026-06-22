from fastapi import FastAPI, Depends,HTTPException
from models import AnalyzeRequest, AnalyzeResponse
from service import analyze_order
from database import supabase
from auth import get_current_user, check_usage
from pydantic import BaseModel
from datetime import datetime, timedelta
app = FastAPI(title="电商AI客服助手")

@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(
    req: AnalyzeRequest,
    user=Depends(get_current_user),
    usage=Depends(check_usage)
):
    # 调用 AI 分析
    result = await analyze_order(req.order_text, req.image_urls)
    
    # 调用成功后，递增调用次数
    new_count = usage["api_calls"] + 1
    supabase.table("user_usage").update({"api_calls": new_count}).eq("user_id", user.id).execute()
    
    return AnalyzeResponse(analysis=result["analysis"], suggested_reply=result["suggested_reply"])

class RedeemRequest(BaseModel):
    code: str

@app.post("/api/redeem")
async def redeem_code(req: RedeemRequest, user=Depends(get_current_user)):
    # 查询激活码
    res = supabase.table("activation_codes").select("*").eq("code", req.code).execute()
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