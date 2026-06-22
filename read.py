from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# 尝试查询一个不存在的表，看能否连通（会报错，但能看到网络是否正常）
try:
    data = supabase.table("nonexistent").select("*").execute()
except Exception as e:
    print("连接成功，返回错误（正常）:", e)