from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
from ..session import Base

class OutlookToken(Base):
    __tablename__ = "outlook_tokens"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="outlook_token")
