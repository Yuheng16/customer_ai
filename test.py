import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()  # .env 中 SUPPABASE_URL 和 SUPABASE_KEY 为正确的值
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

res = supabase.table("activation_codes").select("*").eq("code", "TEST-CODE-123456").execute()
print(res.data)