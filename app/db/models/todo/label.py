from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base

class Label(Base):
    __tablename__ = "labels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    color = Column(String, default="charcoal")
    order = Column(Integer, default=0)
    is_favorite = Column(Boolean, default=False)
    is_shared = Column(Boolean, default=False)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    user = relationship("User", backref="labels")
    tasks = relationship("TaskLabel", back_populates="label", cascade="all, delete")
