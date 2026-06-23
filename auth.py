from fastapi import FastAPI, Depends, HTTPException, Request
from database import supabase
import traceback
from datetime import datetime,timezone
import os
# 依赖项：获取当前登录用户（用于需要登录的接口）
async def get_current_user(request: Request):
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供令牌")
    token = auth.split(" ")[1]
    try:
        # 强制打印 token 前10位，确认是否正确传递
        print(f"Received token (first 10 chars): {token[:10]}...")
        user_response = supabase.auth.get_user(token)
        print("Supabase get_user success")
        return user_response.user
    except Exception as e:
        # 打印完整堆栈
        print("Supabase get_user failed:")
        traceback.print_exc()
        # 把真实错误信息临时返回给客户端，方便调试（上线后删除）
        raise HTTPException(status_code=401, detail=f"无效令牌: {str(e)}")

async def check_usage(user=Depends(get_current_user)):
    # 1. 查询 profiles 表获取订阅等级
    profile_res = supabase.table("profiles").select("*").eq("id", user.id).execute()
    if not profile_res.data:
        # 如果没有 profile，创建一个（兜底）
        supabase.table("profiles").insert({"id": user.id}).execute()
        tier = "free"
        expiry = None
    else:
        profile = profile_res.data[0]
        tier = profile.get("subscription_tier", "free")
        expiry = profile.get("subscription_expiry")

    # 2. 检查订阅是否过期
    if expiry:
        if isinstance(expiry, str):
            expiry = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
        if expiry < datetime.now(timezone.utc):
            # 降级为 free
            supabase.table("profiles").update({
                "subscription_tier": "free",
                "subscription_expiry": None
            }).eq("id", user.id).execute()
            tier = "free"

    # 3. 设置不同等级的限制
    limits = {
        "free": 10,
        "pro": 100,
        "premium": 99999
    }
    daily_limit = limits.get(tier, 10)

    # 4. 统计今日已用次数（从 user_usage 表按行数计算）
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    usage_res = supabase.table("user_usage") \
        .select("*", count="exact") \
        .eq("user_id", user.id) \
        .gte("created_at", today_start) \
        .execute()
    today_calls = usage_res.count if usage_res.count else 0

    # 5. 检查是否超限
    if today_calls >= daily_limit:
        raise HTTPException(
            status_code=429,
            detail=f"今日调用次数已达上限（{tier}套餐每日 {daily_limit} 次），请升级套餐或明日再试"
        )

    # 6. 返回信息给后续路由使用
    return {
        "tier": tier,
        "limit": daily_limit,
        "today_used": today_calls,
        "user_id": user.id
    }