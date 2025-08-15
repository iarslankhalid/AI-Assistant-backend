import json
from queue import PriorityQueue
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI
from requests import Session
from app.db.session import SessionLocal, get_db
from app.db.models.email import Email
from app.db.models.email_thread import EmailThread
from openai import OpenAI
from os import getenv
from dotenv import load_dotenv
from sqlalchemy.orm import joinedload
from app.api.todo.task import schemas
from app.db.models.todo.task import Task
from app.db.models.todo.project import Project


load_dotenv()
client = OpenAI(api_key=getenv("OPENAI_API_KEY"))



def create_task(db: Session, user_id: int, content: str, description: Optional[str] = None, 
                priority: Optional[int] = None, project_id: int = 1, due_date: Optional[str] = None,
                reminder_at: Optional[str] = None, recurrence: Optional[str] = None,
                order: Optional[int] = None, section_id: Optional[int] = None, 
                parent_id: Optional[int] = None):
    """
    Create a task in the database with comprehensive fields.

    Args:
        db: The database session.
        content: The content of the task.
        description: An optional description of the task.
        priority: An optional priority level (1-4) for the task.
        project_id: The ID of the project the task belongs to.
        user_id: The ID of the user creating the task.
        due_date: An optional due date for the task.
        reminder_at: An optional reminder time for the task.
        recurrence: An optional recurrence pattern for the task.
        order: An optional order in which the task should be sorted.
        section_id: An optional section ID if the task is part of a specific section.
        parent_id: An optional parent task ID if this task is a subtask.

    Returns:
        The created task object.
    """
    task_data = {
        "content": content,
        "description": description,
        "priority": priority,
        "project_id": project_id,
        "creator_id": user_id,
        "due_date": due_date,
        "reminder_at": reminder_at,
        "recurrence": recurrence,
        "order": order or 0,
        "section_id": section_id,
        "parent_id": parent_id,
    }
    # Remove None values
    task_data = {k: v for k, v in task_data.items() if v is not None}
    
    db_task = Task(**task_data)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    print(f"[INFO] -- Task: {content} added for user: {user_id}")
    return db_task





def process_email_with_ai(email_id: str, user_id: int, background_tasks: BackgroundTasks):
    db = SessionLocal()
    try:
        email = db.query(Email).filter(Email.id == email_id).first()
        if not email or not email.body_plain:
            return

        # Complete Task schema structure based on the actual model
        task_schema_example = {
            "content": "string (required) - main title/summary of the task",
            "description": "string (optional) - detailed description of the task",
            "priority": "integer (optional) - 1=low, 2=normal, 3=high, 4=urgent (default: 1)",
            "due_date": "string (optional) - ISO format date (YYYY-MM-DD) if deadline mentioned",
            "reminder_at": "string (optional) - ISO format datetime for reminders",
            "recurrence": "string (optional) - daily, weekly, monthly, yearly if task repeats",
            "order": "integer (optional) - task ordering within project (default: 0)",
            "is_completed": "boolean (optional) - completion status (default: false)",
            "section_id": "integer (optional) - specific section within project if mentioned",
            "parent_id": "integer (optional) - parent task ID if this is a subtask"
        }

        response = client.chat.completions.create(
            model="gpt-4-1106-preview",
            messages=[
                {
                    "role": "system",
                    "content": "You are a personal email assistant that analyzes emails and extracts actionable tasks with comprehensive metadata. Extract tasks that require the recipient's action and populate all relevant fields from the task schema.",
                },
                {
                    "role": "user",
                    "content": f"""
Analyze the email below and extract meaningful insights and actionable tasks.

Generate:
1. ai_draft (professional response draft)
2. summary (concise email summary)
3. quick_replies (3-4 professional, short response options)
4. topic (generalized category for grouping similar emails)
5. priority (0-100 based on urgency and importance)

For task extraction:
- Only extract genuine actionable tasks (ignore promotional/marketing content)
- Use this complete task schema: {json.dumps(task_schema_example, indent=2)}
- Extract due dates, reminders, and recurrence patterns if mentioned
- Identify if tasks are related (parent-child relationships)
- Set appropriate priority levels based on urgency indicators
- If no actionable tasks exist, return empty array

Email Details:
Sender: {email.sender_name}
Subject: {email.subject}
Body: {email.body_plain}
""",
                },
            ],
            functions=[
                {
                    "name": "store_email_analysis",
                    "description": "Extracts structured insights and tasks from an email",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ai_draft": {"type": "string"},
                            "summary": {"type": "string"},
                            "quick_replies": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "topic": {"type": "string"},
                            "priority_score": {"type": "integer"},
                            "extracted_tasks": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "content": {"type": "string"},
                                        "description": {"type": "string"},
                                        "priority": {"type": "integer"},
                                        "due_date": {"type": "string"},
                                        "reminder_at": {"type": "string"},
                                        "recurrence": {"type": "string"},
                                        "order": {"type": "integer"},
                                        "is_completed": {"type": "boolean"},
                                        "section_id": {"type": "integer"},
                                        "parent_id": {"type": "integer"}
                                    },
                                    "required": ["content"],
                                },
                            },
                        },
                        "required": ["summary", "topic", "priority_score", "extracted_tasks"],
                    },
                }
            ],
            function_call={"name": "store_email_analysis"},
            temperature=0.3,
        )

        function_args = response.choices[0].message.function_call.arguments
        ai_data = json.loads(function_args)

        # Store AI fields to Email
        email.ai_draft = ai_data.get("ai_draft")
        email.summary = ai_data.get("summary")
        email.quick_replies = ai_data.get("quick_replies")
        email.topic = ai_data.get("topic")
        email.priority_score = ai_data.get("priority_score")
        extracted_tasks = ai_data.get("extracted_tasks")

        email.extracted_tasks = extracted_tasks
        db.commit()

        if extracted_tasks:
            inbox_project = db.query(Project).filter(
                Project.is_inbox_project == True,
                Project.user_id == user_id
            ).first()

            if inbox_project is None:
                raise HTTPException(status_code=404, detail="Inbox project not found")

            inbox_id = inbox_project.id
            print(f"[INFO] -- Inbox project found: {inbox_project.name} (ID: {inbox_id})")
            for task_data in extracted_tasks:
                background_tasks.add_task(
                    create_task,
                    content=task_data["content"],
                    description=task_data.get("description"),
                    priority=task_data.get("priority"),
                    project_id=inbox_id,
                    user_id=user_id,
                    db=db,
                    due_date=task_data.get("due_date"),
                    reminder_at=task_data.get("reminder_at"),
                    recurrence=task_data.get("recurrence"),
                    order=task_data.get("order"),
                    section_id=task_data.get("section_id"),
                    parent_id=task_data.get("parent_id")
                )

        return ai_data

    except Exception as e:
        print(f"AI process failed for email {email_id}: {e}")
        db.rollback()
    finally:
        db.close()



def process_email_thread_with_ai(conversation_id: str):
    db = SessionLocal()
    try:
        thread = db.query(EmailThread).filter(EmailThread.conversation_id == conversation_id).first()
        if not thread:
            print(f"Email thread with ID {conversation_id} not found.")
            return

        emails = (
            db.query(Email).filter(Email.conversation_id == conversation_id).order_by(Email.sent_at).all()
        )
        if not emails:
            print(f"No emails found in thread {conversation_id}.")
            return

        # Construct the conversation history for the AI
        conversation_history = []
        conversation_history.append(
            {
                "role": "system",
                "content": "You are a personal email assistant that analyzes email thread conversations and provides a summary(clear and concise), overall topic [generalized to group similar emails together], priority score(0-100), and category of the thread [urgent, normal or informational].",
            }
        )

        for email in emails:
            conversation_history.append(
                {
                    "role": "user",
                    "content": f"""
Sender Name: {email.sender_name}
Subject: {email.subject}
Body:
{email.body_plain}
""",
                }
            )

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=conversation_history,
            functions=[
                {
                    "name": "store_thread_analysis",
                    "description": "Extracts structured insights from an email thread conversation",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "summary": {"type": "string"},
                            "topic": {"type": "string"},
                            "category": {"type": "string"},
                            "priority_score": {"type": "integer"},
                        },
                        "required": ["summary", "topic", "priority_score, category"],
                    },
                }
            ],
            function_call={"name": "store_thread_analysis"},
            temperature=0.5,
        )

        function_args = response.choices[0].message.function_call.arguments
        ai_thread_data = json.loads(function_args)

        # Store AI fields to EmailThread
        thread.summary = ai_thread_data.get("summary")
        thread.topic = ai_thread_data.get("topic")
        thread.category = ai_thread_data.get("category")
        thread.priority_score = ai_thread_data.get("priority_score")

        db.commit()
        return ai_thread_data

    except Exception as e:
        print(f"AI enrichment failed for email thread {conversation_id}: {e}")
        db.rollback()
    finally:
        db.close()



if __name__ == "__main__":
    app = FastAPI()
    @app.get("/test")
    async def test_endpoint(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
        test_email_id = 1 
        test_user_id = 1
        process_email_with_ai(test_email_id, test_user_id, background_tasks)
        return {"message": "AI processing started in the background"}