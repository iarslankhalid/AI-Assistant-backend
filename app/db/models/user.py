from sqlalchemy import Column, Integer, String
from app.db.session import Base
from sqlalchemy.orm import relationship

from .outlook_token import OutlookToken

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    outlook_token = relationship("OutlookToken", back_populates="user", uselist=False)
