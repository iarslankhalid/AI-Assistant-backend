from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
from ..session import Base

class OutlookCredentials(Base):
    __tablename__ = "outlook_credentials"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    token_type = Column(String, nullable=True)
    scope = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    last_refreshed_at = Column(DateTime, nullable=True, default=None)

    user = relationship("User", back_populates="outlook_credentials")
