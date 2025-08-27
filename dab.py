# init_db.py

from app.db.session import Base, engine
from sqlalchemy.engine import create_engine
from app.config import settings
from app.db.models.user_info import UserInfo


def init():
    print("Connecting to database...")
    engine = create_engine(settings.DATABASE_URL)

    print("Creating tables (if not exist)...")
    Base.metadata.create_all(bind=engine)

    print("✅ Done.")


if __name__ == "__main__":
    init()
