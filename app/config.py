from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ENV: str = "local"  # Environment setting

    # Outlook OAuth settings
    OUTLOOK_CLIENT_ID: str
    OUTLOOK_CLIENT_SECRET: str
    OUTLOOK_REDIRECT_URI: str
    
    # Open-AI Key
    OPENAI_API_KEY: str
    ASSEMBLYAI_API_KEY: str
    class Config:
        env_file = ".env"

settings = Settings()
