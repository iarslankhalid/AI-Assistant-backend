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


load_dotenv()
client = OpenAI(api_key=getenv("OPENAI_API_KEY"))



def create_task(db: Session, user_id: int, content: str, description: Optional[str] = None, priority: Optional[int] = None, project_id: int = 1):
    """
    Create a task in the database.

    Args:
        db: The database session.
        content: The content of the task.
        description: An optional description of the task.
        priority: An optional priority level (1-4) for the task.
        project_id: The ID of the project the task belongs to.
        user_id: The ID of the user creating the task.

    Returns:
        The created task object.
    """
    task_data = {
        "content": content,
        "description": description,
        "priority": priority,
        "project_id": project_id,
        "creator_id": user_id,
    }
    db_task = Task(**task_data)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    print(f"[INFO] -- Task: {content} added for user: {user_id}")





def process_email_with_ai(email_id: str, user_id: int, background_tasks: BackgroundTasks):
    db = SessionLocal()
    try:
        email = db.query(Email).filter(Email.id == email_id).first()
        if not email or not email.body_plain:
            return

        response = client.chat.completions.create(
            model="gpt-4-1106-preview",
            messages=[
                {
                    "role": "system",
                    "content": "You are a personal email assistant that analyzes emails sent to me and labels them with useful metadata and tasks.",
                },
                {
                    "role": "user",
                    "content": f"""
Analyze the email below. Generate ai_draft (professional), summary of the email, quick replies that I can send to email (Professional, Concise and short), topic of the email (Generalized, to group emails of similar topics), priority (0 - 100)

If the email contains any tasks or actions to perform (make sure this email is not a promotiontional email), extract them and return a structured JSON. if there is no task, return an empty list

For each task, include:
- `content`: the main title/summary of the task (mandatory)
- `description`: optional details if available
- `priority`: an integer from 1 to 4 based on urgency (1=low, 4=high)

Only return tasks if they are mentioned or implied in the email.

Sender Name: {email.sender_name}
Subject: {email.subject}
Body:
{email.body_plain}
""",
                },
            ],
            functions=[
                {
                    "name": "store_email_analysis",
                    "description": "Extracts structured insights from an email",
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
                                    },
                                    "required": ["content"],
                                },
                            },
                        },
                        "required": ["summary", "topic", "priority_score"],
                    },
                }
            ],
            function_call={"name": "store_email_analysis"},
            temperature=0.4,
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
            for task_data in extracted_tasks:
                #changed from task to task_data
                background_tasks.add_task(
                    create_task,
                    content=task_data["content"],
                    description=task_data.get("description"),
                    priority=task_data.get("priority"),
                    project_id=1,
                    user_id=user_id,
                    db=db
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
            model="gpt-4-1106-preview",
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