import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")  # 建议先用 service_role key，方便开发

supabase: Client = create_client(url, key)