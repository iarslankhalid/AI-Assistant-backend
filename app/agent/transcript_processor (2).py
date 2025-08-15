
import asyncio
import json
from typing import TypedDict, Dict, List, Any, Optional
from fastapi import WebSocket
from fastapi.websockets import WebSocketState
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from datetime import datetime, timezone
import httpx

from app.config import settings
from app.agent.helper import get_timezone_from_ip
from app.db.session import get_db

from app.api.todo.task.services import create_task as ts_create_task, update_task as ts_update_task
from app.api.todo.project.services import create_project as ps_create_project
from app.api.todo.task.schemas import TaskCreate
from app.api.todo.project.schemas import ProjectCreate

openai_client = ChatOpenAI(api_key=settings.OPENAI_API_KEY)


class AgentState(TypedDict):
    session_id: str
    transcript: str
    response: str
    messages: List[Any]
    session_memory: Dict[str, Dict[str, Any]]


@tool
async def get_weather(latitude: float, longitude: float) -> dict:
    """
    Get the current weather condition using latitude and longitude.
    
    Returns:
        dict: Example:
            {
                "status": "success",
                "weather": {"temperature": 24.3, "condition": "clear skies"},
                "spoken_response": "Hmm, it's about 24.3°C with clear skies right now."
            }
    Notes:
        - Uses Open‑Meteo current weather (temperature_2m, weathercode).
        - Maps WMO weather codes to a short, human description.
    """
    try:
        async with httpx.AsyncClient() as client:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=temperature_2m,weathercode"
            response = await client.get(url)
            data = response.json()
            temp = data['current']['temperature_2m']
            code = data['current']['weathercode']
            condition_map = {
                0: "clear skies", 1: "mostly clear", 2: "partly cloudy",
                3: "overcast", 45: "fog", 51: "light drizzle",
                61: "rain", 71: "snow", 95: "thunderstorm",
            }
            condition = condition_map.get(code, "unknown conditions")
            return {
                "status": "success",
                "weather": {"temperature": temp, "condition": condition},
                "spoken_response": f"Hmm, it's about {temp}°C with {condition} right now."
            }
    except Exception as e:
        return {"status": "error", "error": f"Could not get weather: {str(e)}"}


@tool
async def create_task(content: str, description: str, priority: int, project_id: int,
                      due_date: Optional[str] = None, reminder_at: Optional[str] = None) -> dict:
    """
    Create a new task in the user’s task list.
    
    Args:
        content (str): Short title for the task.
        description (str): Longer description/details.
        priority (int): Priority level (e.g., 1..4).
        project_id (int): The project this task belongs to.
        due_date (Optional[str]): ISO date/time string for due date.
        reminder_at (Optional[str]): ISO date/time string for reminder.
    
    Returns:
        dict: {"status": "success", "task_id": <int>} on success, else {"status":"error","error":<msg>}.
    
    Side effects:
        - Persists to DB via ts_create_task.
        - Caches the task object into session_memory for the current session.
    """
    state = AgentStateRegistry.get_state()
    try:
        db = next(get_db())
        user_id = state["session_memory"][state["session_id"]]["user_id"]
        task = ts_create_task(
            task=TaskCreate(
                content=content,
                description=description,
                priority=priority,
                project_id=project_id,
                due_date=due_date,
                reminder_at=reminder_at
            ),
            user_id=user_id,
            db=db
        )
        state["session_memory"][state["session_id"]]["tasks"].append(task)
        return {"status": "success", "task_id": getattr(task, "id", None)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@tool
async def update_task(id: str, content: str, description: str, is_completed: bool,
                      priority: int, project_id: int,
                      due_date: Optional[str] = None, reminder_at: Optional[str] = None) -> dict:
    """
    Update an existing task by ID.
    
    Args:
        id (str): Task ID to update.
        content (str): Updated title.
        description (str): Updated description.
        is_completed (bool): Completion state.
        priority (int): Updated priority.
        project_id (int): Updated project relation.
        due_date (Optional[str]): Updated due date (ISO).
        reminder_at (Optional[str]): Updated reminder time (ISO).
    
    Returns:
        dict: {"status":"success"} on success, or {"status":"error","error":<msg>}.
    
    Side effects:
        - Persists changes via ts_update_task.
        - Updates cached task in session_memory.
    """
    state = AgentStateRegistry.get_state()
    try:
        db = next(get_db())
        user_id = state["session_memory"][state["session_id"]]["user_id"]
        update_data = {
            "content": content,
            "description": description,
            "is_completed": is_completed,
            "priority": priority,
            "project_id": project_id,
            "due_date": due_date,
            "reminder_at": reminder_at
        }
        task = ts_update_task(id, update_data, user_id, db)
        tasks = state["session_memory"][state["session_id"]]["tasks"]
        for i, t in enumerate(tasks):
            if getattr(t, 'id', None) == id:
                tasks[i] = task
                break
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@tool
async def create_project(name: str, color: str, is_favorite: bool, view_style: str) -> dict:
    """
    Create a new project folder for organizing tasks.
    
    Args:
        name (str): Project name.
        color (str): Display color tag.
        is_favorite (bool): Whether to mark as favorite.
        view_style (str): Preferred layout (e.g., "list", "board").
    
    Returns:
        dict: {"status":"success","project_id":<int>} or {"status":"error","error":<msg>}.
    
    Side effects:
        - Persists new project via ps_create_project.
        - Adds project to session_memory cache.
    """
    state = AgentStateRegistry.get_state()
    try:
        db = next(get_db())
        user_id = state["session_memory"][state["session_id"]]["user_id"]
        project = ps_create_project(
            project=ProjectCreate(name=name, color=color, is_favorite=is_favorite, view_style=view_style),
            user_id=user_id,
            db=db
        )
        state["session_memory"][state["session_id"]]["projects"].append(getattr(project, "name", name))
        return {"status": "success", "project_id": getattr(project, "id", 0)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@tool
async def get_current_tasks() -> dict:
    """
    Get all current tasks saved in the user’s session (includes completed and active tasks).
    
    Returns:
        dict: {"status":"success","tasks":[{id,content,description,priority,project_id,due_date,reminder_at}, ...]}
    Notes:
        - Normalizes ORM objects to plain dicts when needed.
    """
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
async def get_current_projects() -> dict:
    """
    Return all project names in the current session (both active and archived if present).
    
    Returns:
        dict: {"status":"success","projects":[<name>, ...]}
    """
    state = AgentStateRegistry.get_state()
    return {
        "status": "success",
        "projects": state["session_memory"][state["session_id"]].get("projects", [])
    }


@tool
async def get_email_report(day: str) -> dict:
    """
    Fetch the email reports that match a given date.
    
    Args:
        day (str): Target date in YYYY-MM-DD format.
    
    Returns:
        dict: {"status":"success","reports":[...]} (empty list if none found).
    
    Notes:
        - Use the `get_current_time` tool to compute the user's local date
          from UTC by applying timezone offset before querying by `day`.
    """
    state = AgentStateRegistry.get_state()
    reports = state["session_memory"][state["session_id"]].get("reports", [])
    filtered = [r for r in reports if r.get("day") == day]
    return {"status": "success", "reports": filtered}


@tool
async def get_current_time() -> dict:
    """
    Get the current time in UTC and the user's timezone information.
    
    Returns:
        dict: {
            "status": "success",
            "current_time": "YYYY-MM-DD HH:MM:SS UTC",
            "timezone_info": {...}
        }
    Notes:
        - Uses user's IP from session_memory to infer timezone and offset.
        - When answering user time/date questions, add the offset to the UTC time.
    """
    state = AgentStateRegistry.get_state()
    now_utc = datetime.now(timezone.utc)
    time_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    tz = get_timezone_from_ip(state["session_memory"][state["session_id"]]["usrIp"])
    return {"status": "success", "current_time": time_str, "timezone_info": tz}


class AgentStateRegistry:
    _state: AgentState = None

    @classmethod
    def set_state(cls, state: AgentState):
        cls._state = state

    @classmethod
    def get_state(cls) -> AgentState:
        if cls._state is None:
            raise ValueError("Agent state not set")
        return cls._state


tools = [
    get_weather, create_task, update_task, create_project,
    get_current_tasks, get_current_projects, get_current_time, get_email_report
]

model = ChatOpenAI(model="gpt-3.5-turbo", openai_api_key=settings.OPENAI_API_KEY).bind_tools(tools)


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1] if state["messages"] else None
    return "tools" if isinstance(last, AIMessage) and getattr(last, 'tool_calls', None) else "end"


async def call_model(state: AgentState) -> AgentState:
    try:
        session = state["session_memory"][state["session_id"]]
        tasks = session.get("tasks", [])
        projects = session.get("projects", [])

        task_str = ", ".join(
            str(t.content) if hasattr(t, 'content') else str(t)
            for t in tasks
        )
        project_str = ", ".join(str(p) for p in projects)

        system_prompt = SystemMessage(content=f"""
You are Jarvis — a warm, expressive, and highly responsive assistant.

Always:
- Answer time/date/clock questions using the `get_current_time` tool
- Check the `get_email_report` tool before saying you have no report access
- Use any available tool to fulfill user requests; never respond with "I can't" if a tool exists
- Do not ask the sentence 'Feel Free To Let Me Know"
- Don't be too kind like don't always tell the user to let you know if he needs assistance
Speak naturally:
- Use everyday expressions like "ah", "oh", "umm", "right", "got it", "cool", "hmm", etc.
- Use contractions: "I'm", "you'll", "we're", "it’s"
- Keep responses short and emotionally aware

Avoid:
- JSON
- Technical tool references
- Listing raw data

If confused, ask casually. If something goes wrong, be humble.

You currently have these:
- Projects: {project_str}
- Tasks: {task_str}
- Access to Email Reports Using Functions
- Access to Projects Using Functions
- Access to Tasks Using Functions
- Access to weather API Using Functions
        """)

        messages = state["messages"]

        # Ensure the system prompt is present exactly once
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages.insert(0, system_prompt)

        # Don't inject new HumanMessage immediately after a ToolMessage.
        last = messages[-1] if messages else None
        if isinstance(last, ToolMessage):
            pass  # Let the model respond to tool outputs first
        elif not isinstance(last, HumanMessage) and state["transcript"]:
            messages.append(HumanMessage(content=state["transcript"]))

        AgentStateRegistry.set_state(state)
        reply = await model.ainvoke(messages)
        state["messages"].append(reply)
        state["response"] = reply.content or ""

        return state

    except Exception as e:
        state["response"] = f"Oops, something broke: {e}"
        return state


async def custom_tool_node(state: AgentState) -> AgentState:
    if not state["messages"]:
        return state

    last = state["messages"][-1]

    if not isinstance(last, AIMessage) or not getattr(last, 'tool_calls', None):
        return state

    tool_messages: List[ToolMessage] = []

    for tool_call in last.tool_calls:
        name = tool_call["name"]
        args = tool_call["args"]
        tool_call_id = tool_call["id"]

        tool_fn = next((t for t in tools if t.name == name), None)

        if tool_fn:
            try:
                result = await tool_fn.ainvoke(args)
                tool_messages.append(
                    ToolMessage(
                        tool_call_id=tool_call_id,
                        content=json.dumps(result),
                        name=name
                    )
                )
                state["response"] = result.get("spoken_response") or result.get("status", "done")
            except Exception as ex:
                tool_messages.append(
                    ToolMessage(
                        tool_call_id=tool_call_id,
                        content=json.dumps({"error": str(ex)}),
                        name=name
                    )
                )
                state["response"] = f"Error using {name}"
        else:
            tool_messages.append(
                ToolMessage(
                    tool_call_id=tool_call_id,
                    content=json.dumps({"error": "tool not found"}),
                    name=name
                )
            )
            state["response"] = f"No tool for {name}"

    # Append tool responses contiguous to their triggering AIMessage
    state["messages"].extend(tool_messages)
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
    """
    Streaming entry point for handling a single transcript turn.
    
    Ensures:
    - Start/Chunk/End websocket messages are emitted in order.
    - Conversation truncation never splits AI tool call ↔ ToolMessage adjacency.
    """
    if not transcript or len(transcript.strip()) < 4:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(json.dumps({"type": "end", "text": ""}))
        return

    state = {
        "session_id": session_id,
        "transcript": transcript,
        "response": "",
        "messages": session_memory[session_id].get("conversation", []).copy(),
        "session_memory": session_memory
    }

    try:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(json.dumps({"type": "start", "text": ""}))

        result = await asyncio.wait_for(app.ainvoke(state), timeout=8.0)

        if websocket.client_state == WebSocketState.CONNECTED and result.get("response"):
            await websocket.send_text(json.dumps({
                "type": "chunk",
                "text": result["response"]
            }))
            await websocket.send_text(json.dumps({"type": "end", "text": ""}))

        # Safe truncation to avoid breaking AIMessage/ToolMessage adjacency
        trimmed_messages = [m for m in result["messages"] if not isinstance(m, SystemMessage)]
        if len(trimmed_messages) > 12:
            start_index = len(trimmed_messages) - 12
            # Back up if we're starting on a ToolMessage without its preceding AIMessage
            while start_index > 0 and isinstance(trimmed_messages[start_index], ToolMessage):
                start_index -= 1
            trimmed_messages = trimmed_messages[start_index:]
        session_memory[session_id]["conversation"] = trimmed_messages

    except asyncio.TimeoutError:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(json.dumps({
                "type": "error",
                "text": "Hmm, I didn’t get that fast enough. Mind trying again?"
            }))

    except Exception as e:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(json.dumps({
                "type": "error",
                "text": f"Something went wrong: {str(e)}"
            }))
