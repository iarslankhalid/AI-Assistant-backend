from sqlalchemy.orm import Session
from app.db.models.todo import Project, Section, Task, Label, TaskLabel
from app.db.models.user import User
from datetime import datetime

def seed_test_tasks(db: Session, user: User):
    # 🗂️ Create Projects
    work = Project(name="Work", user_id=user.id)
    personal = Project(name="Personal", user_id=user.id)
    db.add_all([work, personal])
    db.flush()  # to get IDs

    # 📦 Create Sections
    work_planning = Section(name="Planning", project_id=work.id)
    work_bugs = Section(name="Bug Fixes", project_id=work.id)
    personal_errands = Section(name="Errands", project_id=personal.id)
    personal_goals = Section(name="Goals", project_id=personal.id)
    db.add_all([work_planning, work_bugs, personal_errands, personal_goals])
    db.flush()

    # 🏷️ Create Labels
    urgent = Label(name="Urgent", color="red", user_id=user.id)
    chill = Label(name="Chill", color="blue", user_id=user.id)
    followup = Label(name="Follow Up", color="orange", user_id=user.id)
    bug = Label(name="Bug", color="purple", user_id=user.id)
    db.add_all([urgent, chill, followup, bug])
    db.flush()

    # ✅ Create Tasks
    tasks = [
        Task(content="Fix login issue", project_id=work.id, section_id=work_bugs.id, creator_id=user.id, is_completed=False, priority=4),
        Task(content="Plan Q3 roadmap", project_id=work.id, section_id=work_planning.id, creator_id=user.id, is_completed=True, priority=2),
        Task(content="Buy groceries", project_id=personal.id, section_id=personal_errands.id, creator_id=user.id, is_completed=False),
        Task(content="Pay bills", project_id=personal.id, section_id=personal_errands.id, creator_id=user.id, is_completed=True),
        Task(content="Research AI tools", project_id=work.id, section_id=work_planning.id, creator_id=user.id),
        Task(content="Fix password reset bug", project_id=work.id, section_id=work_bugs.id, creator_id=user.id, priority=3),
        Task(content="Meditate", project_id=personal.id, section_id=personal_goals.id, creator_id=user.id, priority=1),
        Task(content="Email HR", project_id=work.id, section_id=work_planning.id, creator_id=user.id, is_completed=False),
        Task(content="Clean garage", project_id=personal.id, section_id=personal_goals.id, creator_id=user.id, is_completed=False),
        Task(content="Submit expense report", project_id=work.id, section_id=work_planning.id, creator_id=user.id),
        Task(content="Review PR #42", project_id=work.id, section_id=work_planning.id, creator_id=user.id, priority=2, is_completed=False),
        Task(content="Refactor old code", project_id=work.id, section_id=work_bugs.id, creator_id=user.id, priority=1),
        Task(content="Plan birthday party", project_id=personal.id, section_id=personal_goals.id, creator_id=user.id, priority=3),
        Task(content="Fix dark mode toggle", project_id=work.id, section_id=work_bugs.id, creator_id=user.id, is_completed=True, priority=4),
        Task(content="Read a book", project_id=personal.id, section_id=personal_goals.id, creator_id=user.id, is_completed=False),

    ]
    db.add_all(tasks)
    db.flush()

    # 🔗 Attach labels
    task_label_map = [
        (tasks[0], [urgent, bug]),
        (tasks[1], [followup]),
        (tasks[2], [chill]),
        (tasks[5], [bug]),
        (tasks[6], [chill]),
        (tasks[8], [urgent]),
    ]

    for task, labels in task_label_map:
        for label in labels:
            db.add(TaskLabel(task_id=task.id, label_id=label.id))

    db.commit()

if __name__ == "__main__":
    from app.db.session import SessionLocal
    from app.db.models import outlook_credentials  # Ensure all models are registered

    db = SessionLocal()

    # ✅ Get test user (ID 1)
    user = db.query(User).filter(User.id == 1).first()
    if user:
        print(f"Seeding data for user: {user.email}")
        seed_test_tasks(db, user)
    else:
        print("User with ID 1 not found!")
