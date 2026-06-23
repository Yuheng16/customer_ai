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
    # 获取 profile
    profile_res = supabase.table("profiles").select("*").eq("id", user.id).execute()
    if not profile_res.data:
        # 理论上新建用户会自动创建 profile，这里兜底
        supabase.table("profiles").insert({"id": user.id}).execute()
        profile = {"subscription_tier": "free", "subscription_expiry": None}
    else:
        profile = profile_res.data[0]
    
    # 检查订阅是否过期
    if profile["subscription_expiry"]:
        expiry = datetime.fromisoformat(profile["subscription_expiry"].replace("Z","+00:00"))
        if expiry < datetime.utcnow():
            # 过期降级为 free
            supabase.table("profiles").update({"subscription_tier": "free", "subscription_expiry": None}).eq("id", user.id).execute()
            profile["subscription_tier"] = "free"
    
    tier = profile["subscription_tier"]
    # 定义限制：free每日10次，pro每日100次，premium不限
    limits = {"free": 10, "pro": 100, "premium": float("inf")}
    daily_limit = limits.get(tier, 10)
    
    # 获取今日调用次数（可新建 daily_usage 表，这里简化为从 user_usage 读取当日计数，需要额外逻辑）
    # 暂时略，可后期实现。先只做简单返回 tier。
    return {"tier": tier, "limit": daily_limit}