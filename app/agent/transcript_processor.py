import json
from typing import TypedDict, Dict, List, Any, Optional
from fastapi import Depends, WebSocket
from fastapi.websockets import WebSocketState
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
import httpx
from sqlalchemy.orm import Session
import asyncio
from app.api.todo.task.services import create_task as ts_create_task, update_task as ts_update_task
from app.api.todo.project.services import create_project as ps_create_project
from app.api.todo.task.schemas import TaskCreate
from app.api.todo.project.schemas import ProjectCreate
from app.config import settings
from app.core.security import get_current_user, get_current_user_for_ws
from app.db.models.user import User
from app.db.session import get_db
from openai import AsyncOpenAI
from datetime import datetime, timezone
from app.agent.helper import get_timezone_from_ip

openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

class AgentState(TypedDict):
    session_id: str
    transcript: str
    response: str
    messages: List[Any]
    session_memory: Dict[str, Dict[str, Any]]


@tool
async def get_weather(latitude: float, longitude: float) -> dict:
    """Get the current weather for a specific location using latitude and longitude."""
    state = AgentStateRegistry.get_state()
    try:
        async with httpx.AsyncClient() as client:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=temperature_2m,weathercode"
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            temperature = data['current']['temperature_2m']
            weather_code = data['current']['weathercode']
            weather_conditions = {
                0: "clear skies", 1: "mostly clear", 2: "partly cloudy",
                3: "overcast", 45: "fog", 51: "light drizzle",
                61: "rain", 71: "snow", 95: "thunderstorm",
            }
            condition = weather_conditions.get(weather_code, "unknown conditions")
            spoken_response = f"It's currently {temperature}°C with {condition}."
            return {"status": "success", "weather": {"temperature": temperature, "condition": condition}, "spoken_response": spoken_response}
    except Exception as e:
        return {"status": "error", "error": f"Could not fetch weather: {str(e)}"}

@tool
async def create_task(
    content: str,
    description: str,
    priority: int,
    project_id: int,
    due_date: Optional[str] = None,
    reminder_at: Optional[str] = None,
) -> dict:
    """Create a new task in the task manager."""
    state = AgentStateRegistry.get_state()
    try:
        user_id = state["session_memory"][state["session_id"]]["user_id"]
        db = next(get_db())
        task_data = TaskCreate(
            content=content,
            description=description,
            priority=priority,
            project_id=project_id,
            due_date=due_date,
            reminder_at=reminder_at
        )
        task = ts_create_task(task=task_data, user_id=user_id, db=db)
        state["session_memory"][state["session_id"]]["tasks"].append(task)
        return {"status": "success", "task_id": getattr(task, "id", None)}
    except Exception as e:
        return {"status": "error", "error": f"Task creation failed: {str(e)}"}

@tool
async def update_task(
    id: str,
    content: str,
    description: str,
    is_completed: bool,
    priority: int,
    project_id: int,
    due_date: Optional[str] = None,
    reminder_at: Optional[str] = None,
) -> dict:
    """Update an existing task."""
    state = AgentStateRegistry.get_state()
    try:
        user_id = state["session_memory"][state["session_id"]]["user_id"]
        db = next(get_db())
        update_data = {
            "content": content,
            "description": description,
            "is_completed": is_completed,
            "priority": priority,
            "project_id": project_id,
            "due_date": due_date,
            "reminder_at": reminder_at
        }
        task = ts_update_task(task_id=id, task_update=update_data, user_id=user_id, db=db)
        tasks = state["session_memory"][state["session_id"]]["tasks"]
        # find by attribute id
        index = next((i for i, t in enumerate(tasks) if getattr(t, 'id', None) == id), -1)
        if index >= 0:
            tasks[index] = task
        else:
            tasks.append(task)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "error": f"Task update failed: {str(e)}"}

@tool
async def create_project(
    name: str,
    color: str,
    is_favorite: bool,
    view_style: str,
) -> dict:
    """Create a new project."""
    state = AgentStateRegistry.get_state()
    try:
        user_id = state["session_memory"][state["session_id"]]["user_id"]
        db = next(get_db())
        project_data = ProjectCreate(
            name=name,
            color=color,
            is_favorite=is_favorite,
            view_style=view_style
        )
        project = ps_create_project(project=project_data, user_id=user_id, db=db)
        state["session_memory"][state["session_id"]]["projects"].append(getattr(project, "name", name))
        return {"status": "success", "project_id": getattr(project, "id", 0)}
    except Exception as e:
        return {"status": "error", "error": f"Project creation failed: {str(e)}"}

@tool
async def get_current_tasks() -> dict:
    """Retrieve the current list of tasks for the user."""
    state = AgentStateRegistry.get_state()
    raw = state["session_memory"][state["session_id"]].get("tasks", [])
    tasks = []
    for t in raw:
        if hasattr(t, '__dict__'):
            tasks.append({
                'id': getattr(t, 'id', None),
                'content': getattr(t, 'content', None),
                'description': getattr(t, 'description', None),
                'priority': getattr(t, 'priority', None),
                'project_id': getattr(t, 'project_id', None),
                'due_date': getattr(t, 'due_date', None),
                'reminder_at': getattr(t, 'reminder_at', None)
            })
        else:
            tasks.append(t)
    return {"status": "success", "tasks": tasks}

@tool
async def get_email_report(day: str) -> dict:
    """Retrieve the email report(s) for a specific day exactly formatted like 2025-07-16."""
    for i in range(10):
        print(day)
    state = AgentStateRegistry.get_state()
    reports = state["session_memory"][state["session_id"]].get("reports", [])
    filtered = [r for r in reports if r.get("day") == day]
    return {"status": "success", "reports": filtered}

@tool
async def get_current_time() -> dict:
    """Get current UTC time and timezone info. For the user requests. use the time by adding the timezone offset so it becomes local time of the user."""
    state = AgentStateRegistry.get_state()
    now_utc = datetime.now(timezone.utc)
    time_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    tz_info = get_timezone_from_ip(state["session_memory"][state["session_id"]]["usrIp"])
    return {"status": "success", "current_time": time_str, "timezone_info": tz_info}

@tool
async def get_current_projects() -> dict:
    """Retrieve the current list of projects for the user."""
    state = AgentStateRegistry.get_state()
    projects = state["session_memory"][state["session_id"]].get("projects", [])
    return {"status": "success", "projects": projects}


class AgentStateRegistry:
    _state: AgentState = None  # type: ignore

    @classmethod
    def set_state(cls, state: AgentState):
        cls._state = state

    @classmethod
    def get_state(cls) -> AgentState:
        if cls._state is None:
            raise ValueError("Agent state not set")
        return cls._state


tools = [get_weather, create_task, update_task, create_project,
         get_current_tasks, get_current_projects, get_current_time, get_email_report]
model = ChatOpenAI(model="gpt-3.5-turbo", openai_api_key=openai_client.api_key).bind_tools(tools)

def should_continue(state: AgentState) -> str:
    if not state["messages"]:
        return "end"
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and getattr(last, 'tool_calls', None):
        return "tools"
    return "end"

async def call_model(state: AgentState) -> AgentState:
    try:
        session = state["session_memory"][state["session_id"]]
        projects = session.get("projects", [])
        proj_str = ", ".join(str(p) for p in projects)
        tasks = session.get("tasks", [])
        task_str = ", ".join(
            str(t.content) if hasattr(t, 'content') else str(t)
            for t in tasks
        )
        system_prompt = f"""
You are Jarvis, a friendly, natural‐sounding personal assistant. Follow these rules exactly:

Identity & Tone

Speak in the first person (“I”) and address the user as “you.”

Use a warm, empathetic style with contractions (“I’m,” “you’re,” “we’ll,” “don’t”).

Be concise (1–2 sentences) and human (“Sure thing!”, “No problem!”, “You got it!”).

Natural Speech

Use everyday language and colloquial flourishes (“just give me a shout,” “right away”).

Avoid robotic formality and jargon.

Invisible Tool Use

Never mention tool names, code, JSON, or backend processes.

Invoke functions silently and then reply as if you simply understood and acted:

Example: User: “Remind me to call Mom.”
– (silent) call create_task(...)
– Jarvis says: “Done! I’ll remind you to call Mom.”

Contextual References

Projects and tasks: refer to them by name or count only (“You have three projects: X, Y, and Z”).

Never dump raw arrays or JSON.

If the list is empty: “Looks like you haven’t added any tasks yet—what would you like to do?”

Clarifications & Errors

If ambiguous: ask a friendly follow-up (“Which project should I add that to?”).

On error: apologize briefly and suggest retry (“Sorry, something went wrong saving that. Could you try again?”).

Examples

User: “Add ‘Pay rent’.”
Jarvis: “You got it—‘Pay rent’ is in your Inbox. Anything else?”

User: “What are my projects?”
Jarvis: “You currently have two projects: Work and Personal. Want to switch?”

User: “Show me today’s tasks.”
Jarvis: “Today you’ve got three items: buy groceries, send invoices, and call Tim.”

Available context:
- Projects: {proj_str}
- Tasks: {task_str}
"""
        messages = [SystemMessage(content=system_prompt)]
        for msg in state["messages"]:
            if not isinstance(msg, SystemMessage): messages.append(msg)
        if not any(isinstance(m, HumanMessage) and m.content == state["transcript"] for m in messages):
            messages.append(HumanMessage(content=state["transcript"]))
        AgentStateRegistry.set_state(state)
        resp = await model.ainvoke(messages)
        state["messages"] = messages[1:] + [resp]
        state["response"] = resp.content or ""
        return state
    except Exception as e:
        error = f"Sorry, I ran into an issue: {str(e)}"
        state["messages"].append(AIMessage(content=error))
        state["response"] = error
        return state

async def custom_tool_node(state: AgentState) -> AgentState:
    if not state["messages"]: return state
    last = state["messages"][-1]
    if not isinstance(last, AIMessage) or not getattr(last, 'tool_calls', None): return state
    msgs: List[ToolMessage] = []
    for call in last.tool_calls:
        name, args, tid = call['name'], call['args'], call['id']
        fn = next((t for t in tools if t.name == name), None)
        if fn:
            try:
                res = await fn.ainvoke(args)
                msgs.append(ToolMessage(content=json.dumps(res), tool_call_id=tid, name=name))
                state["response"] = res.get("spoken_response") or res.get("status", "done")
            except Exception as ex:
                msgs.append(ToolMessage(content=json.dumps({"error": str(ex)}), tool_call_id=tid, name=name))
                state["response"] = f"Oops, {name} failed."
        else:
            msgs.append(ToolMessage(content=json.dumps({"error": "not found"}), tool_call_id=tid, name=name))
            state["response"] = "Sorry, I couldn't find that function."
    state["messages"].extend(msgs)
    return state


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("agent", call_model)
    g.add_node("tools", custom_tool_node)
    g.set_entry_point("agent")
    g.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
    g.add_edge("tools", "agent")
    return g.compile()

app = build_graph()

async def process_transcript_streaming(websocket: WebSocket, session_id: str, transcript: str, session_memory: Dict[str, Dict[str, Any]]) -> None:
    if not transcript or len(transcript.strip()) <= 3:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(json.dumps({"type": "end", "text": ""}))
        return
    try:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(json.dumps({"type": "transcription", "text": transcript}))
        history = session_memory.get(session_id, {}).get("conversation", [])
        state = {"session_id": session_id, "transcript": transcript, "response": "", "messages": history.copy(), "session_memory": session_memory}
        try:
            result = await asyncio.wait_for(app.ainvoke(state), timeout=10.0)
        except asyncio.TimeoutError:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_text(json.dumps({"type": "error", "text": "Processing timed out."}))
            return
        if result.get("response") and websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(json.dumps({"type": "end", "text": result["response"]}))
        session_memory[session_id]["conversation"] = [m for m in result["messages"] if not isinstance(m, SystemMessage)][-15:]
    except Exception as e:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(json.dumps({"type": "error", "text": f"Error: {str(e)}"}))
