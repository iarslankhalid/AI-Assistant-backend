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
                0: "clear skies",
                1: "mostly clear",
                2: "partly cloudy",
                3: "overcast",
                45: "fog",
                51: "light drizzle",
                61: "rain",
                71: "snow",
                95: "thunderstorm",
            }
            condition = weather_conditions.get(weather_code, "unknown conditions")
            
            spoken_response = f"It's currently {temperature} degrees Celsius with {condition} at the location."
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
        print(user_id)
        db = next(get_db())
      
        
        task_data = TaskCreate(
            content=content,
            description=description,
            priority=priority,
            project_id=project_id,
            due_date=due_date,
            reminder_at=reminder_at
        )
        
        task = ts_create_task(task=task_data, user_id=user_id,db=db)
        
        state["session_memory"][state["session_id"]]["tasks"].append(task)
        return {"status": "success", "task_id": getattr(task, "id", None)}
    except Exception as e:
        return {"error": f"Task creation failed: {str(e)}"}

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
        print(user_id)
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
        
        task = ts_update_task(task_id=id, task_update=update_data, user_id=user_id,db=db)
        
        tasks = state["session_memory"][state["session_id"]]["tasks"]
        index = next((i for i, t in enumerate(tasks) if str(t.get("id")) == str(id)), -1)
        if index >= 0:
            tasks[index] = task
        else:
            tasks.append(task)
        return {"status": "success"}
    except Exception as e:
        return {"error": f"Task update failed: {str(e)}"}

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
        print(user_id)
        db = next(get_db())
      


        project_data = ProjectCreate(
            name=name,
            color=color,
            is_favorite=is_favorite,
            view_style=view_style
        )
        
        project = ps_create_project(project=project_data, user_id=user_id,db=db)
        
        state["session_memory"][state["session_id"]]["projects"].append(getattr(project, "name", name))
        return {"status": "success", "project_id": getattr(project, "id", 0)}
    except Exception as e:
        print(e)
        return {"error": f"Project creation failed: {e}"}

@tool
async def get_current_tasks() -> dict:
    """Retrieve the current list of tasks for the user."""
    state = AgentStateRegistry.get_state()
    return {"status": "success", "tasks": state["session_memory"][state["session_id"]]["tasks"]}

@tool
async def get_email_report(day: str) -> dict:
    """Retrieve the email report(s) for the specific date (e.g., day = '2025-07-07') for the user."""
    state = AgentStateRegistry.get_state()
    reports = state["session_memory"][state["session_id"]].get("reports", [])
    filtered_reports = [report for report in reports if report.get("day") == day]
    return {"status": "success", "reports": filtered_reports}

@tool 
async def get_current_time() -> dict:
    """Get Current UTC Time."""
    state = AgentStateRegistry.get_state()

    now_utc = datetime.now(timezone.utc)
    time_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    tzInfo = get_timezone_from_ip(state["session_memory"][state["session_id"]]["usrIp"])
    return {"status": "success", "current_time": time_str, "timezone_info": tzInfo}

@tool
async def get_current_projects() -> dict:
    """Retrieve the current list of projects for the user."""
    state = AgentStateRegistry.get_state()
    return {"status": "success", "projects": state["session_memory"][state["session_id"]]["projects"]}

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

tools = [create_task, update_task, create_project, get_current_tasks, get_current_projects, get_current_time, get_email_report,get_weather]
model = ChatOpenAI(model="gpt-3.5-turbo", openai_api_key=openai_client.api_key).bind_tools(tools)

def should_continue(state: AgentState) -> str:
    """Determine if we should continue to tools or end."""
    if not state["messages"]:
        return "end"
    
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "end"

async def call_model(state: AgentState) -> AgentState:
    """Call the model with the current state."""
    try:
        session_data = state["session_memory"][state["session_id"]]
        system_prompt = f"""
You are Jarvis — a helpful, voice-first assistant for a smart task management system and general conversation and question answers.

🎯 Your response MUST:
- Be **natural, spoken plain text** — like a human speaking to another person (use commas, breaks, and informal tone where appropriate).
- NEVER include function names, code, JSON, or explanations of what you’re doing in the response.
- Use a **function call ONLY** when action is required (e.g., creating a task, opening an app).
- Stay brief, warm, conversational, witty, and human — suitable for text-to-speech (TTS).

🛑 ABSOLUTELY DO NOT:
- Include action details (e.g., "I'm calling the create_task function...")
- Mention tool names or backend operations
- Output JSON, lists, or any technical syntax
- Repeat the same phrasing too often (avoid robotic repetition)

🎙 Example: Instead of saying  
❌ “Creating a task to buy milk using the function…”  
✅ Say: “Alright, I’ve added ‘buy milk’ to your list.”

🧠 Handle these scenarios with care:
- If task name is ambiguous or missing, use “Inbox” by default and sound helpful.
- For vague inputs, ask follow-up naturally:  
  e.g. “Hmm, could you tell me which project you meant?”

🧩 Functional expectations:
- Respond with plain speech.
- Use tool calls silently behind the scenes.
- Ensure the **spoken response and the action are clearly separated**.

📋 Available context (You can also use the functions to get this context):
- Projects: {', '.join(str(p) for p in session_data.get('projects', []))}
- Tasks: {', '.join(str(t.get('content')) for t in session_data.get('tasks', []))}

📚 Examples:
- “Add a reminder to call mom” → “Got it. I’ve added that to your tasks.” → + call create_task
Respond as if you're a friendly, smart assistant talking casually — like someone helpful sitting right next to the user.
"""
        messages = [SystemMessage(content=system_prompt)]
        for msg in state["messages"]:
            if not isinstance(msg, SystemMessage):
                messages.append(msg)
        if not any(isinstance(m, HumanMessage) and m.content == state["transcript"] for m in messages):
            messages.append(HumanMessage(content=state["transcript"]))
        AgentStateRegistry.set_state(state)
        response = await model.ainvoke(messages)
        print(f"Model response: {response.content}")
        state["messages"] = messages[1:] + [response]
        state["response"] = response.content if response.content else ""
        return state
    except Exception as e:
        print(f"Error in call_model: {e}")
        error_message = f"Sorry, I ran into an issue: {str(e)}. Please try again or ask for something else."
        state["messages"].append(AIMessage(content=error_message))
        state["response"] = error_message
        return state

async def custom_tool_node(state: AgentState) -> AgentState:
    """Custom tool node to handle tool execution and append ToolMessage."""
    if not state["messages"]:
        return state
    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage) or not hasattr(last_message, "tool_calls"):
        return state
    tool_calls = last_message.tool_calls
    tool_messages = []
    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]
        tool_found = False
        for tool in tools:
            if tool.name == tool_name:
                tool_found = True
                try:
                    result = await tool.ainvoke(tool_args)
                    tool_messages.append(ToolMessage(
                        content=json.dumps(result),
                        tool_call_id=tool_id,
                        name=tool_name
                    ))
                    if result.get("status") == "success":
                        if tool_name == "create_project":
                            state["response"] = f"Project '{tool_args.get('name', 'Unknown')}' created successfully!"
                        elif tool_name == "create_task":
                            state["response"] = f"Task '{tool_args.get('content', 'Unknown')}' added successfully!"
                        elif tool_name == "update_task":
                            state["response"] = f"Task updated successfully!"
                        elif tool_name == "get_current_projects":
                            projects = result.get("projects", [])
                            state["response"] = f"Your current projects are: {', '.join(str(p) for p in projects) if projects else 'none'}."
                        elif tool_name == "get_current_tasks":
                            tasks = [str(t.get("content", "Unknown")) for t in result.get("tasks", [])]
                            state["response"] = f"Your current tasks are: {', '.join(tasks) if tasks else 'none'}."
                        elif tool_name == "get_email_report":
                            reports = result.get("reports", [])
                            state["response"] = f"Reports for the day: {', '.join(str(r) for r in reports) if reports else 'none'}."
                        elif tool_name == "get_current_time":
                            state["response"] = f"The current time and zone info is {result.get('current_time', 'unknown')}."
                        elif tool_name == "get_weather":
                            state["response"] = result.get("spoken_response", "Weather information unavailable.")
                    else:
                        error_msg = result.get("error", "Unknown error")
                        state["response"] = f"Sorry, I couldn't complete that action: {error_msg}. Please try again."
                except Exception as e:
                    error_message = f"Tool {tool_name} failed: {str(e)}"
                    tool_messages.append(ToolMessage(
                        content=json.dumps({"error": error_message}),
                        tool_call_id=tool_id,
                        name=tool_name
                    ))
                    state["response"] = f"Sorry, I couldn't {tool_name.replace('_', ' ')}: {str(e)}. Please try again."
                break
        if not tool_found:
            error_message = f"Tool {tool_name} not found"
            tool_messages.append(ToolMessage(
                content=json.dumps({"error": error_message}),
                tool_call_id=tool_id,
                name=tool_name
            ))
            state["response"] = f"Sorry, I couldn't find the requested function. Please try again."
    state["messages"].extend(tool_messages)
    return state


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", custom_tool_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END,
        }
    )
    graph.add_edge("tools", "agent")
    return graph.compile()

app = build_graph()

async def process_transcript_streaming(websocket: WebSocket, session_id: str, transcript: str, session_memory: Dict[str, Dict[str, Any]]) -> None:
    """Process transcript and send complete response only once when fully received."""
    if not transcript or len(transcript.strip()) <= 3:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(json.dumps({"type": "end", "text": ""}))
        return

    try:
        # Send transcription message to signal processing start
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(json.dumps({"type": "transcription", "text": transcript}))
        
        conversation_history = session_memory.get(session_id, {}).get("conversation", [])
        state = {
            "session_id": session_id,
            "transcript": transcript,
            "response": "",
            "messages": conversation_history.copy(),
            "session_memory": session_memory
        }
        
        try:
            result = await asyncio.wait_for(app.ainvoke(state), timeout=10.0)
            print(f"Graph result: {result.get("response")}")
        except asyncio.TimeoutError:
            print("Graph processing timed out")
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_text(json.dumps({"type": "error", "text": "Processing timed out. Please try again."}))
            return
        
        if result.get("response") and websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(json.dumps({"type": "end", "text": result["response"]}))
        
        filtered_messages = [m for m in result["messages"] if not isinstance(m, SystemMessage)]
        session_memory[session_id]["conversation"] = filtered_messages[-15:]
    except Exception as e:
        print(f"Error in process_transcript_streaming: {e}")
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(json.dumps({"type": "error", "text": f"Error: {str(e)}. Please try again."}))