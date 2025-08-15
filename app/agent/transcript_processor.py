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
    
    Returns the temperature in Celsius and a description like "clear skies" or "rain".
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
    Create a new task in the user’s task list with given details like title, description, priority, and dates.
    Add Optional Details Like reminder_at and due_date if told to.
    Returns the task ID if successful.
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
    Update an existing task by ID. Can modify its text, completion status, dates, or priority.
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
    Create a new project folder with a name, color, favorite flag, and layout style.
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
    Return all project names in the current session (includes both active and archived if present).
    """
    state = AgentStateRegistry.get_state()
    return {
        "status": "success",
        "projects": state["session_memory"][state["session_id"]].get("projects", [])
    }

@tool
async def get_email_report(day: str) -> dict:
    """
    Fetch the email reports that match a given date (format: YYYY-MM-DD) and use the get_current_time function and add the timezone offset to to get the correct day.
    If no reports found, returns an empty list.
    """
    state = AgentStateRegistry.get_state()
    reports = state["session_memory"][state["session_id"]].get("reports", [])
    filtered = [r for r in reports if r.get("day") == day]
    return {"status": "success", "reports": filtered}

@tool
async def get_current_time() -> dict:
    """
    Get the current time in UTC and also fetch the timezone and offset based on user's IP. For queries regarding time, add the timezone offset to the utc time
    """
    state = AgentStateRegistry.get_state()
    now_utc = datetime.now()
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

        # Only add system prompt once, it should be at the start
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

        # Reuse the existing conversation history
        messages = state["messages"]

        # Add system message if it's not already in the list
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages.insert(0, system_prompt)

        # Check if the last message is not already a HumanMessage
        last = messages[-1] if messages else None
        if not isinstance(last, HumanMessage) and state["transcript"]:
            messages.append(HumanMessage(content=state["transcript"]))

        # Update state before model call (if any tools need it)
        AgentStateRegistry.set_state(state)

        # Call the model with updated message history
        reply = await model.ainvoke(messages)

        # Append reply to message history
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
                # Add tool message using correct format
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

    # Extend messages in state with tool responses
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

        session_memory[session_id]["conversation"] = [
            m for m in result["messages"] if not isinstance(m, SystemMessage)
        ][-12:]

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
