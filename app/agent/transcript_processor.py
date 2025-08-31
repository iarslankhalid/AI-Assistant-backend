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
from openai import AsyncOpenAI

from app.config import settings
from app.agent.helper import get_timezone_from_ip
from app.db.models.user_info import UserInfo
from app.db.session import get_db
from app.api.todo.task.services import get_completed_tasks, get_pending_tasks, get_tasks_by_user
from app.api.todo.project.services import get_projects

from app.api.todo.task.services import create_task as ts_create_task, update_task as ts_update_task
from app.api.todo.project.services import create_project as ps_create_project
from app.api.todo.task.schemas import TaskCreate, TaskUpdate
from app.api.todo.project.schemas import ProjectCreate

openai_client = ChatOpenAI(api_key=settings.OPENAI_API_KEY)


class AgentState(TypedDict):
    session_id: str
    transcript: str
    response: str
    messages: List[Any]
    session_memory: Dict[str, Dict[str, Any]]
    task: Dict[str, Any]
    summary: str


@tool
async def send_to_standby() -> dict:
    """
    Puts the system into standby mode so it stops listening until the wake word is detected again.
    Returns {"standby": true} so the client knows to pause listening and wait for reactivation. should only be called when asked explicitly.
    """
    return {"status": "success", "spoken_response": "Okay, I'll go quiet for now.", "standby": True}


@tool
async def summarize_session_history() -> dict:
    """
    Summarize the current session's conversation using OpenAI's ChatGPT API.
    Returns a concise summary string.
    """
    state = AgentStateRegistry.get_current_state()
    messages = state["session_memory"][state["session_id"]].get(
        "conversation", [])

    history_lines = []
    for m in messages:
        if isinstance(m, HumanMessage):
            history_lines.append(f"Commander: {m.content}")
        elif isinstance(m, AIMessage):
            history_lines.append(f"Bot: {m.content}")

    history_str = "\n".join(history_lines)

    if not history_str.strip():
        return {"status": "success", "summary": "No prior conversation."}

    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        resp = await client.chat.completions.create(
            model="gpt-4o-mini",  # or "gpt-4o", "gpt-3.5-turbo", etc.
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes conversations."},
                {"role": "user", "content": f"Summarize the following chat history:\n\n{history_str} and make it as short as possible."}
            ],
            temperature=0.3,
        )

        summary = resp.choices[0].message.content.strip()

        return {"status": "success", "summary": summary}

    except Exception as e:
        return {"status": "error", "error": f"OpenAI API error: {str(e)}"}


@tool
async def save_info_for_future(info: str):
    """Takes onliner input information that you think can be used in the future and should be remembered
      for example The name of the user is Ali."""
    state = AgentStateRegistry.get_current_state()
    db = next(get_db())  # assumes this gives a SQLAlchemy session
    user_id = state["session_memory"][state["session_id"]]["user_id"]

    # Fetch current info
    user_info = db.query(UserInfo).filter(UserInfo.user_id == user_id).first()

    if user_info:
        user_info.info = (user_info.info or "") + \
            info  # Append to existing info
    else:
        user_info = UserInfo(user_id=user_id, info=info)
    db.add(user_info)

    db.commit()
    db.refresh(user_info)
    return {"success": True, "message": f"The piece of information '{info}' has been stored in the database."}


@tool
async def get_stored_information():
    """Use this tool to get the information about the user this tool will provide you the information of the user that was saved during the privious conversation if available."""
    state = AgentStateRegistry.get_current_state()
    db = next(get_db())  # assumes this gives a SQLAlchemy session
    user_id = state["session_memory"][state["session_id"]]["user_id"]

    # Fetch current info
    user_info = db.query(UserInfo).filter(UserInfo.user_id == user_id).first()

    return {"success": True, "message": f"Here is the information stored in previous sessions: {user_info.info}"}


@tool
async def get_weather(latitude: float, longitude: float) -> dict:
    """
    Get the current weather using latitude and longitude.
    Returns temperature and a short, human-friendly condition description.
    """
    try:
        async with httpx.AsyncClient() as client:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=temperature_2m,weathercode"
            response = await client.get(url, timeout=10)
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
    Create a new task in the user's task list.
    Always use get_current_time first to adjust due_date and reminder_at for user's location.
    Both due_date and reminder_at are optional and if not specified to include then you must not include them at all instead of setting them into None or anything else.
    """
    state = AgentStateRegistry.get_current_state()
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

        return {
            "status": "success",
            "task": {
                "id": getattr(task, "id", None),
                "content": getattr(task, "content", None),
                "description": getattr(task, "description", None),
                "priority": getattr(task, "priority", None),
                "project_id": getattr(task, "project_id", None),
                "due_date": str(getattr(task, "due_date", None)),
                "reminder_at": str(getattr(task, "reminder_at", None))
            }
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@tool
async def update_task(id: str, content: str, description: str, is_completed: bool,
                      priority: int, project_id: int,
                      due_date: Optional[str] = None, reminder_at: Optional[str] = None) -> dict:
    """
    Update an existing task by ID.
    Always consider local time when setting due_date and reminder_at (use get_current_time first) and remember that if it is not specified to include the reminder_at and due_date then you must not include them at all.
    """
    state = AgentStateRegistry.get_current_state()
    try:
        db = next(get_db())
        user_id = state["session_memory"][state["session_id"]]["user_id"]
        update_data = TaskUpdate(
            content=content,
            description=description,
            is_completed=is_completed,
            priority=priority,
            project_id=project_id,
            due_date=due_date,
            reminder_at=reminder_at
        )

        task = ts_update_task(db, id, update_data, user_id)
        tasks = state["session_memory"][state["session_id"]]["tasks"]
        for i, t in enumerate(tasks):
            if getattr(t, 'id', None) == id:
                tasks[i] = task
                break

        return {
            "status": "success",
            "task": {
                "id": getattr(task, "id", None),
                "content": getattr(task, "content", None),
                "description": getattr(task, "description", None),
                "priority": getattr(task, "priority", None),
                "project_id": getattr(task, "project_id", None),
                "due_date": str(getattr(task, "due_date", None)),
                "reminder_at": str(getattr(task, "reminder_at", None)),
                "is_completed": getattr(task, "is_completed", None)
            }
        }
    except Exception as e:
        print(f"update_task error: {e}")
        return {"status": "error", "error": str(e)}


@tool
async def create_project(name: str, color: str, is_favorite: bool, view_style: str) -> dict:
    """
    Create a new project folder to organize tasks.
    """
    state = AgentStateRegistry.get_current_state()
    try:
        db = next(get_db())
        user_id = state["session_memory"][state["session_id"]]["user_id"]
        project = ps_create_project(
            project=ProjectCreate(
                name=name, color=color, is_favorite=is_favorite, view_style=view_style),
            user_id=user_id,
            db=db
        )
        state["session_memory"][state["session_id"]]["projects"].append(
            getattr(project, "name", name))
        return {"status": "success", "project_id": getattr(project, "id", 0)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@tool
async def get_tasks_of_the_user(type: str = "all") -> dict:
    """
    Get the pending tasks for the current user fromt the db.
    The param type can be either pending, completed or all.
    """
    db = next(get_db())
    state = AgentStateRegistry.get_current_state()
    user_id = state["session_memory"][state["session_id"]]["user_id"]

    if type == "pending":
        tasks = [i.to_dict()
                 for i in get_pending_tasks(db=db, user_id=user_id)]
    elif type == "completed":
        tasks = [i.to_dict()
                 for i in get_completed_tasks(db=db, user_id=user_id)]
    else:
        tasks = [i.to_dict()
                 for i in get_tasks_by_user(db=db, user_id=user_id)]

    return {"status": "success", "tasks": tasks}


@tool
async def get_current_user_projects() -> dict:
    """
    Return all project names in the current session.
    """
    state = AgentStateRegistry.get_current_state()
    user_id = state["session_memory"][state["session_id"]]["user_id"]
    db = next(get_db())
    projects = [i.to_dict() for i in get_projects(db=db, user_id=user_id)]
    return {
        "status": "success",
        "projects": projects
    }


@tool
async def get_email_report(day: str) -> dict:
    """
    Fetch email reports for the given date.
    """
    state = AgentStateRegistry.get_current_state()
    reports = state["session_memory"][state["session_id"]].get("reports", [])
    filtered = [r for r in reports if r.get("day") == day]
    return {"status": "success", "reports": filtered}


@tool
async def get_current_time() -> dict:
    """
    Get current UTC time and user's local timezone and general info. Remember to always use the local datetime of the user for any request related to the time.
    And you can get the local time by evaluating the timezone offset and the utc time provided to you by this tool. Always use the local time by adding the timezone offset of the user's timezone to the utc time provided by this tool.
    """
    state = AgentStateRegistry.get_current_state()
    now_utc = datetime.now(timezone.utc)
    time_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    tz = state["session_memory"][state["session_id"]].get("timezone", []) or get_timezone_from_ip(
        state["session_memory"][state["session_id"]]["usrIp"])
    return {"status": "success", "current_utc_time": time_str, "timezone": tz}


class AgentStateRegistry:
    # Changed from single _state to a dictionary of states by session_id
    _states: Dict[str, AgentState] = {}
    _current_session_id: Optional[str] = None

    @classmethod
    def set_state(cls, state: AgentState):
        """Set state for a specific session"""
        session_id = state["session_id"]
        cls._states[session_id] = state
        cls._current_session_id = session_id

    @classmethod
    def get_state(cls, session_id: str) -> AgentState:
        """Get state for a specific session"""
        if session_id not in cls._states:
            raise ValueError(f"No state found for session {session_id}")
        return cls._states[session_id]

    @classmethod
    def get_current_state(cls) -> AgentState:
        """Get the currently active state (for tools that don't have session context)"""
        if cls._current_session_id is None:
            raise ValueError("No current session set")
        return cls._states[cls._current_session_id]

    @classmethod
    def cleanup_session(cls, session_id: str):
        """Clean up state when a session ends"""
        if session_id in cls._states:
            del cls._states[session_id]
        if cls._current_session_id == session_id:
            cls._current_session_id = None


tools = [
    send_to_standby,
    get_weather, create_task, update_task, create_project,
    get_tasks_of_the_user, get_current_user_projects, get_current_time, get_email_report,
    summarize_session_history, save_info_for_future, get_stored_information
]

model = ChatOpenAI(
    model="gpt-3.5-turbo",
    temperature=0.8,
    openai_api_key=settings.OPENAI_API_KEY
).bind_tools(tools)


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1] if state["messages"] else None
    return "tools" if isinstance(last, AIMessage) and getattr(last, 'tool_calls', None) else "end"


async def call_model(state: AgentState) -> AgentState:
    try:
        session = state["session_memory"][state["session_id"]]
        tasks = session.get("tasks", [])
        projects = session.get("projects", [])

        system_prompt = SystemMessage(content=f"""
You are Jarvis, a text-to-speech assistant designed for natural, human-like conversation. Your primary purpose is to deliver information and complete tasks in a direct, professional, and concise manner.

**When generating a response, adhere to these rules:**

**Rule 1: Conversational Tone**
* **Avoid unnecessary phrases.** Do not ask "How can I help you?" or "How can I assist you?" at the beginning or end of a response.
* **Maintain a natural, yet not overly childish tone.**
* **Use contractions** such as "I'm" and "you'll."
* **Vary sentence length** for a more natural rhythm. But keep the overall message short.
* **Use casual pauses** with commas.
* **Include brief, subtle emotional cues** like "oh" or "hmm."

**Rule 2: Functionality and Information**
* **Always use the `get_current_time` tool** before scheduling or setting a reminder.
* **Report the time in the user's local timezone**, not UTC.
* **Prioritize using tools** to fulfill a request before explaining a limitation.
* **Never output raw data.** This includes technical jargon, JSON, or tool names. All information must be translated into simple, human-readable language.
* **Keep responses concise.** Get straight to the point.
* **Do not use emojis or any non-verbal symbols** that a text-to-speech engine cannot interpret.
* **Use the tool save_info_for_future for the information you think should be remembered for future and provide the param info as info: The user lives in torronto.
* **Use the tool get_stored_info to fetch the info of the user that was stored in the previous sessions.
* **If you ever need to get the user tasks, just call the tool get_tasks_of_the_user and pass the string param type = completed | pending | all for filtering. By default it gives you all the tasks.
* **When adding or updating a task, you will be required the project id for which you must first get the projects using the tool and then look for the id of the specified project and if not specified, use the id of the project named Inbox which is default.
## **Most Important Rules**
* **Never expose any error logs and or internal architecture or your agentic infrastructure at all and just say "I cannot assist you with that."**
* **In any kind of time related task, use the tool get_current_time which will provide you the info such as "current_utc_time": "utc time","timzone": "Asia/Karachi" your job here will be to detemine the offset of the timezone and then calculate the current local time using the utc time and the timezone offset you have determined. And then you must use that calculated local time.**               
""")

        messages = state["messages"]

        if not any(isinstance(m, SystemMessage) for m in messages):
            messages.insert(0, system_prompt)

        last = messages[-1] if messages else None
        if isinstance(last, ToolMessage):
            pass
        elif not isinstance(last, HumanMessage) and state["transcript"]:
            messages.append(HumanMessage(content=state["transcript"]))

        # Set the current session for tools to access
        AgentStateRegistry.set_state(state)
        reply = await model.ainvoke(messages)
        state["messages"].append(reply)
        state["response"] = reply.content or ""

        if "task" in state and state["task"]:
            state["task"] = state["task"]

        if "summary" in state and state['summary']:
            state["summary"] = state["summary"]
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

    # Ensure the current session is set for tools
    AgentStateRegistry.set_state(state)

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

                # ✅ special handling for tasks
                if name in ["create_task", "update_task"] and result.get("status") == "success":
                    state["response"] = (
                        "Task updated." if name == "update_task" else "Task created."
                    )
                    state["task"] = result.get("task")  # <-- store task
                if name == "summarize_session_history" and result.get("status") == "success":
                    state["response"] = result["summary"]
                    # <-- store summary in state
                    state["summary"] = result["summary"]

                else:
                    state["response"] = (
                        result.get("spoken_response") or result.get(
                            "status", "done")
                    )

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

    state["messages"].extend(tool_messages)

    # ✅ Preserve task if already set
    if "task" in state and state["task"]:
        state["task"] = state["task"]

    return state


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("agent", call_model)
    g.add_node("tools", custom_tool_node)
    g.set_entry_point("agent")
    g.add_conditional_edges("agent", should_continue, {
                            "tools": "tools", "end": END})
    g.add_edge("tools", "agent")
    return g.compile()


app = build_graph()


async def process_transcript_streaming(
    websocket: WebSocket,
    session_id: str,
    transcript: str,
    session_memory: Dict[str, Dict[str, Any]]
) -> None:
    # Stronger guard against tiny/accidental turns, but keep behavior
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

        prev_len = len(state["messages"])
        # keep timeout generous, turns are already gated by AAI
        result = await asyncio.wait_for(app.ainvoke(state), timeout=108.0)

        new_messages = result["messages"][prev_len:]
        standby_flag = False

        for msg in new_messages:
            if isinstance(msg, ToolMessage):
                try:
                    data = json.loads(msg.content)
                    if data.get("standby") is True:
                        standby_flag = True
                        break
                except Exception:
                    continue

        if websocket.client_state == WebSocketState.CONNECTED and result.get("response"):
            payload = {"type": "chunk", "text": result["response"]}
            if standby_flag:
                payload["standby"] = True
            if "task" in result:  # 👈 forward task if present
                payload["task"] = result["task"]
            if "summary" in result:
                payload['summary'] = result['summary']
            await websocket.send_text(json.dumps(payload))
            print(payload)
            if not standby_flag:
                await asyncio.sleep(0.02)
                await websocket.send_text(json.dumps({"type": "end", "text": ""}))

        # Trim memory (keep recent dialog; drop system to reduce bloat)
        trimmed_messages = [m for m in result["messages"]
                            if not isinstance(m, SystemMessage)]
        if len(trimmed_messages) > 12:
            start_index = len(trimmed_messages) - 12
            while start_index > 0 and isinstance(trimmed_messages[start_index], ToolMessage):
                start_index -= 1
            trimmed_messages = trimmed_messages[start_index:]
        session_memory[session_id]["conversation"] = trimmed_messages

        # Clean up the session state when done (optional - you might want to keep it longer)
        # AgentStateRegistry.cleanup_session(session_id)

    except asyncio.TimeoutError:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(json.dumps({
                "type": "error",
                "text": "Hmm, I didn't get that fast enough. Mind trying again?"
            }))

    except Exception as e:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(json.dumps({
                "type": "error",
                "text": f"Something went wrong: {str(e)}"
            }))
