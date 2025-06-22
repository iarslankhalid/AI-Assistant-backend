from fastapi import FastAPI, Request
from app.api.auth.routes import router as auth_router
from app.api.email.routes import router as email_router
from app.api.chat.routes import router as chat_router

from app.api.todo.project.routes import router as todo_project_router
from app.api.todo.section.routes import router as todo_section_router
from app.api.todo.task.routes import router as todo_task_router
from app.api.todo.label.routes import router as todo_label_router
from app.api.todo.task_label.routes import router as todo_task_label_router
from app.api.todo.comment.routes import router as comment_router

from app.api.settings.routes import router as settings_router

# Scheduler for Sync
from contextlib import asynccontextmanager
from app.core.scheduler import start_scheduler

import requests


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield

app = FastAPI(lifespan=lifespan)

# Routers
app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(email_router, prefix="/email", tags=["Email"])
app.include_router(chat_router, prefix="/chat", tags=["Chat"])

app.include_router(todo_project_router, prefix="/todo/projects", tags=["Todo Projects"])
app.include_router(todo_section_router, prefix="/todo/sections", tags=["Todo Sections"])
app.include_router(todo_task_router, prefix="/todo/tasks", tags=["Todo Tasks"])
app.include_router(todo_label_router, prefix="/todo/labels", tags=["Todo Labels"])
app.include_router(todo_task_label_router, prefix="/todo/task-labels", tags=["Todo Task Labels"])
app.include_router(comment_router, prefix="/todo/comments", tags=["Todo Comments"])

app.include_router(settings_router, prefix="/settings", tags=["Settings"])

@app.get("/ping")
def ping():
    return {"message": "pong"}



def get_timezone_from_ip(ip: str) -> dict:
    try:
        # Get timezone name
        timezone_response = requests.get(f"https://ipapi.co/{ip}/timezone/")
        # Get UTC offset
        utc_offset_response = requests.get(f"https://ipapi.co/{ip}/utc_offset/")
        
        timezone = "Unknown"
        utc_offset = "Unknown"
        
        if timezone_response.status_code == 200:
            timezone = timezone_response.text.strip()
        
        if utc_offset_response.status_code == 200:
            utc_offset = utc_offset_response.text.strip()
            
        return {
            "timezone": timezone,
            "utc_offset": utc_offset
        }
    except Exception as e:
        return {
            "timezone": "Unknown",
            "utc_offset": "Unknown",
            "error": str(e)
        }

@app.get("/timezone")
async def get_user_timezone(request: Request):
    # Try getting real client IP (considering proxies/load balancers)
    forwarded_for = request.headers.get("X-Forwarded-For")
    client_ip = forwarded_for.split(",")[0] if forwarded_for else request.client.host

    timezone = get_timezone_from_ip(client_ip)
    return {"ip": client_ip, "timezone": timezone}


# Required for Vercel
    # Removed Mangum for now
# from mangum import Mangum
# handler = Mangum(app)
