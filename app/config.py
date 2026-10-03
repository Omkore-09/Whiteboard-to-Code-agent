import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
VISION_MODEL = os.getenv("VISION_MODEL", "qwen/qwen3.8-27b")
CODE_MODEL = os.getenv("CODE_MODEL", "openai/gpt-oss-120b")
SUPABASE_DB_URL = os.environ["SUPABASE_DB_URL"]
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")