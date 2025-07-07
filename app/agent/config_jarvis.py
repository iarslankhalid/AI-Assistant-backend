import os
from dotenv import load_dotenv
from app.config import settings
from openai import AsyncOpenAI
import assemblyai as aai

# # load_dotenv()
# assemblyai_api_key = os.getenv("ASSEMBLYAI_API_KEY")
# openai_api_key = os.getenv("OPENAI_API_KEY")

if not settings.ASSEMBLYAI_API_KEY or not settings.OPENAI_API_KEY:
    raise ValueError("API keys not properly set in .env")

aai.settings.api_key = settings.ASSEMBLYAI_API_KEY
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)