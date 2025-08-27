from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    color = Column(String, default="charcoal")
    order = Column(Integer, default=0)
    is_shared = Column(Boolean, default=False)
    is_favorite = Column(Boolean, default=False)
    is_inbox_project = Column(Boolean, default=False)
    is_team_inbox = Column(Boolean, default=False)
    view_style = Column(String, default="list")
    url = Column(String, nullable=True)

    # Foreign key to User
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    sections = relationship(
        "Section", back_populates="project", cascade="all, delete")
    tasks = relationship("Task", back_populates="project",
                         cascade="all, delete")
    comments = relationship(
        "Comment", back_populates="project", cascade="all, delete")
    collaborators = relationship(
        "Collaborator", back_populates="project", cascade="all, delete")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "order": self.order,
            "is_shared": self.is_shared,
            "is_favorite": self.is_favorite,
            "is_inbox_project": self.is_inbox_project,
            "is_team_inbox": self.is_team_inbox,
            "view_style": self.view_style,
            "url": self.url,
            "user_id": self.user_id
        }
