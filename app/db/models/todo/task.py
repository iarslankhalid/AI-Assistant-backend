from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String, nullable=False)
    description = Column(String, nullable=True)
    is_completed = Column(Boolean, default=False)
    order = Column(Integer, default=0)
    priority = Column(Integer, default=1)
    is_deleted = Column(Boolean, default=False)

    due_date = Column(DateTime, nullable=True)           # 🗓 Due Date
    reminder_at = Column(DateTime, nullable=True)        # ⏰ Reminder
    recurrence = Column(String, nullable=True)           # 🔁 Recurrence (e.g., daily, weekly)

    # Foreign Keys
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=True)
    parent_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)  # sub-task
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigner_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    project = relationship("Project", back_populates="tasks")
    section = relationship("Section", back_populates="tasks")
    creator = relationship("User", foreign_keys=[creator_id])
    assignee = relationship("User", foreign_keys=[assignee_id])
    assigner = relationship("User", foreign_keys=[assigner_id])

    parent = relationship("Task", remote_side=[id], backref="sub_tasks")

    labels = relationship("TaskLabel", back_populates="task", cascade="all, delete")
    comments = relationship("Comment", back_populates="task", cascade="all, delete")
