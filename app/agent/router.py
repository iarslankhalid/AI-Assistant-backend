import asyncio
import os
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from websocket_handler import websocket_endpoint, get_active_sessions


load_dotenv()


agentRouter = APIRouter(title="Jarvis Task Manager", version="1.0.0")


templates = Jinja2Templates(directory="templates")


if os.path.exists("static"):
    agentRouter.mount("/static", StaticFiles(directory="static"), name="static")

@agentRouter.get("/")
async def get_root(request: Request):
    """Serve the main page."""
    return templates.TemplateResponse("index.html", context={"request": request})

@agentRouter.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "message": "Jarvis Task Manager is running",
        "sessions": get_active_sessions()
    }

@agentRouter.get("/sessions")
async def get_sessions():
    """Get active sessions info for debugging."""
    return get_active_sessions()


agentRouter.websocket("/ws")(websocket_endpoint)
