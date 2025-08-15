from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings
import app.db.models

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"options": "-csearch_path=public"}
)

print("DATABASE_URL:", settings.DATABASE_URL)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()