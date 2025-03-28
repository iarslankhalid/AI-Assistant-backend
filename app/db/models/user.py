from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.db.session import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=True)  # Nullable for OAuth users
    auth_provider = Column(String, default="local")
    provider_user_id = Column(String, nullable=True)

    # One-to-one relationship with OutlookCredentials
    outlook_credentials = relationship("OutlookCredentials", back_populates="user", uselist=False)
    
    # todo relationships
    projects = relationship("Project", backref="owner", cascade="all, delete", lazy="dynamic")
    #sections = relationship("Section", back_populates="project", cascade="all, delete")
