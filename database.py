import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")  # 建议先用 service_role key，方便开发
print(f"Supabase URL: {url}")    # 确认 URL 正确
print(f"Supabase Key starts with: {key[:20]}...")  # 确认 key 非空
supabase = create_client(url, key)