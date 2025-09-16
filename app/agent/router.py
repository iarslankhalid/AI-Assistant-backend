import asyncio
import os
from fastapi import APIRouter, Request, WebSocket
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from dotenv import load_dotenv
from app.agent.websocket_handler import websocket_endpoint, get_active_sessions


load_dotenv()


agentRouter = APIRouter()


templates = Jinja2Templates(directory="app/agent/templates")


@agentRouter.get("/")
async def get_root(request: Request):
    """Render the main page for the Jarvis Task Manager."""
    return templates.TemplateResponse("index.html", {"request": request})


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


@agentRouter.websocket("/ws")
async def wsp(websocket: WebSocket):
    await websocket_endpoint(websocket=websocket)
