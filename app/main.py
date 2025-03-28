from fastapi import FastAPI
from app.api.auth.routes import router as auth_router
from app.api.email.routes import router as email_router
from app.api.todo.project.routes import router as todo_project_router
from app.api.todo.section.routes import router as todo_section_router
from app.api.todo.task.routes import router as todo_task_router
from app.api.todo.label.routes import router as todo_label_router

app = FastAPI()

app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(email_router, prefix="/email", tags=["Email"])
app.include_router(todo_project_router, prefix="/todo/projects", tags=["Todo Projects"])
app.include_router(todo_section_router, prefix="/todo/sections", tags=["Todo Sections"])
app.include_router(todo_task_router, prefix="/todo/tasks", tags=["Todo Tasks"])
app.include_router(todo_label_router, prefix="/todo/labels", tags=["Todo Labels"])

@app.get("/ping")
def ping():
    return {"message": "pong"}