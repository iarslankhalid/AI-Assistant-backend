from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from app.db.session import Base


class UserInfo(Base):
    __tablename__ = "user_info"
    user_id = Column(Integer,
                     index=True, primary_key=True)
    info = Column(String)
