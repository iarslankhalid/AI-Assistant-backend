import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from assemblyai.streaming.v3 import (
    StreamingClient,
    StreamingClientOptions,
    StreamingParameters,
    StreamingEvents,
    TurnEvent,
)

from app.agent.transcript_processor import process_transcript_streaming
from app.config import settings
from app.core.security import get_current_user_for_ws
from app.db.session import get_db

# Global session memory
session_memory: Dict[str, Dict[str, Any]] = {}

async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections for real-time transcription and processing."""
    print("recived request")
    session_id: Optional[str] = None
    transcriber: Optional[StreamingClient] = None
    user_id: Optional[int] = None
    db = next(get_db())
    auth_token = websocket._query_params.get("token")

    try:
        user = await get_current_user_for_ws(token=auth_token, db=db)
        if user:
            user_id = user.id
        else:
            print("User not found or token is invalid")
            return
    except Exception as e:
        print(f"Error verifying token: {e}")
        return

    try:
        await websocket.accept()
        print(f"WebSocket connection accepted at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            preProcessData: dict = await websocket.receive_json()
            print(preProcessData)
            print(auth_token)
            projects = preProcessData.get('projects', [])
            tasks = preProcessData.get('tasks', [])
            reports: list[dict] = preProcessData.get('reports', [])

            print(
                f"Received data - Tasks: {len(tasks)}, Projects: {len(projects)}, "
                f"AuthToken: {'***' if auth_token else 'None'}\n Summaries: {reports}"
            )

        except Exception as e:
            print(f"Error receiving initial data: {e}")
            await websocket.close(code=1002, reason="Invalid initial data")
            return

        # Create session
        session_id = str(uuid.uuid4())
        session_memory[session_id] = {
            "user_id": user_id,
            "projects": projects,
            "tasks": tasks,
            "reports": reports,
            "usrIp": websocket.client.host,
            "conversation": [],
            # per-session ASR partial buffer
            "partial_buffer": "",
        }

        print(f"Session created with ID: {session_id}")

        # Setup transcription handling
        loop = asyncio.get_running_loop()
        last_transcript = None
        is_processing = False
        processing_lock = asyncio.Lock()

        async def handle_turn(event: TurnEvent):
            """
            Called for each TurnEvent emitted by StreamingEvents.Turn.
            We must ignore intermediate partials for agent invocation,
            buffer them for live captions, and only call the agent on finals.
            """
            nonlocal last_transcript, is_processing

            # defensive fetch of transcript text
            text = ""
            try:
                # TurnEvent may expose .transcript or .text depending on sdk shape
                text = getattr(event, "transcript", None) or getattr(event, "text", "") or ""
                if text is None:
                    text = ""
                text = str(text).strip()
            except Exception:
                text = ""

            # Determine whether this event is final / end_of_turn.
            # Different SDK versions/structures use different fields: be defensive.
            is_final = False
            try:
                if getattr(event, "is_final", None) is not None:
                    is_final = bool(getattr(event, "is_final"))
                elif getattr(event, "end_of_turn", None) is not None:
                    is_final = bool(getattr(event, "end_of_turn"))
                elif getattr(event, "final", None) is not None:
                    is_final = bool(getattr(event, "final"))
                else:
                    # sometimes event has a 'type' or 'event' string
                    etype = (getattr(event, "type", "") or "").lower()
                    if "final" in etype or "completed" in etype or "turn" in etype and "end" in etype:
                        is_final = True
            except Exception:
                is_final = False

            # If it's a partial or empty, buffer and optionally send partial captions to client
            if not is_final:
                # buffer partials (keep last partial for session)
                if text:
                    session = session_memory.get(session_id)
                    if session is not None:
                        # keep a running partial buffer (overwrite with newest partial)
                        session["partial_buffer"] = text
                        # Optionally forward partial captions to client without invoking agent:
                        if websocket.client_state == WebSocketState.CONNECTED:
                            try:
                                await websocket.send_text(json.dumps({"type": "asr_partial", "text": text}))
                            except Exception:
                                pass
                return  # do NOT call the agent on partials

            # At this point this event is final: combine buffer + final defensively
            session = session_memory.get(session_id)
            if session is None:
                return

            # Combine any buffered partial with final text for robustness
            buffered = session.get("partial_buffer", "") or ""
            if buffered and buffered != text:
                # sometimes final includes the full text already; avoid duplication
                full_text = (buffered + " " + text).strip()
            else:
                full_text = text

            # Clear buffer now that final has arrived
            session["partial_buffer"] = ""

            # Ignore tiny/empty finals
            if not full_text or len(full_text.strip()) < 4:
                # still send an end marker so client can progress
                if websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        await websocket.send_text(json.dumps({"type": "end", "text": ""}))
                    except Exception:
                        pass
                return

            # De-duplication
            if full_text == last_transcript:
                return

            # concurrency guard: only one in-flight model call per session
            async with processing_lock:
                if is_processing:
                    # if already processing, drop this final (or you could enqueue)
                    return
                # mark processing inside lock
                nonlocal_is_processing_marker = True

            # We'll set is_processing via a small local pattern (to ensure release)
            try:
                # set flag
                is_processing = True
                last_transcript = full_text

                print(f"Processing final transcript: {full_text}")
                await process_transcript_streaming(
                    websocket, session_id, full_text, session_memory
                )
            except Exception as e:
                print(f"Error processing transcript: {e}")
                if websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        await websocket.send_text(json.dumps({"type": "error", "text": f"Processing error: {str(e)}"}))
                    except Exception:
                        pass
            finally:
                is_processing = False
                # small yield so rapid back-to-back turns don’t collide
                await asyncio.sleep(0.08)

        def on_error(_client, error):
            print(f"AssemblyAI error: {error}")

        # Create and start transcriber (v3)
        try:
            transcriber = StreamingClient(
                StreamingClientOptions(api_key=settings.ASSEMBLYAI_API_KEY)
            )

            # Event handlers
            transcriber.on(
                StreamingEvents.Turn,
                lambda c, e: asyncio.run_coroutine_threadsafe(handle_turn(e), loop),
            )
            transcriber.on(StreamingEvents.Error, on_error)

            # Connect with tuned parameters (keep format_turns True)
            transcriber.connect(
                StreamingParameters(
                    sample_rate=16000,
                    encoding="pcm_s16le",
                    format_turns=True,
                    end_of_turn_confidence_threshold=0.75,
                    min_end_of_turn_silence_when_confident=500,
                    max_turn_silence=2000,
                )
            )

            print("Transcriber connected successfully (v3)")
        except Exception as e:
            print(f"Error creating v3 transcriber: {e}")
            await websocket.close(code=1011, reason="Transcriber setup failed")
            return

        # Main message loop
        try:
            # Packetizer parameters (same as previous fixes)
            SAMPLE_RATE = 16000
            BYTES_PER_SAMPLE = 2
            BYTES_PER_MS = (SAMPLE_RATE * BYTES_PER_SAMPLE) // 1000
            TARGET_MS = 100
            MIN_FLUSH_MS = 60
            TARGET_BYTES = TARGET_MS * BYTES_PER_MS
            MIN_FLUSH_BYTES = MIN_FLUSH_MS * BYTES_PER_MS
            audio_buffer = bytearray()
            IDLE_FLUSH_MS = 180
            IDLE_FLUSH_TIMEOUT = IDLE_FLUSH_MS / 1000.0

            while True:
                if websocket.client_state != WebSocketState.CONNECTED:
                    print("WebSocket disconnected, breaking loop")
                    break

                try:
                    data = await asyncio.wait_for(websocket.receive_bytes(), timeout=IDLE_FLUSH_TIMEOUT)
                    if not data:
                        print("Received empty data, breaking loop")
                        break
                    audio_buffer.extend(data)
                except asyncio.TimeoutError:
                    if transcriber and len(audio_buffer) >= MIN_FLUSH_BYTES:
                        try:
                            transcriber.stream(bytes(audio_buffer))
                        except Exception as e:
                            print(f"Error streaming audio chunk on idle flush: {e}")
                        audio_buffer.clear()
                    continue

                # Send full TARGET_BYTES frames
                while len(audio_buffer) >= TARGET_BYTES:
                    chunk = audio_buffer[:TARGET_BYTES]
                    del audio_buffer[:TARGET_BYTES]
                    if transcriber:
                        try:
                            transcriber.stream(bytes(chunk))
                        except Exception as e:
                            print(f"Error streaming audio chunk: {e}")

        except WebSocketDisconnect:
            print("WebSocket disconnected by client")
        except Exception as e:
            print(f"Error in message loop: {e}")

    except WebSocketDisconnect:
        print("WebSocket disconnected during setup")
    except Exception as e:
        print(f"Unexpected WebSocket error: {e}")
    finally:
        print(f"Cleaning up session: {session_id} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Flush trailing audio safely
        try:
            if "audio_buffer" in locals() and transcriber and len(audio_buffer) >= (16000*2)//1000 * 50:
                try:
                    await asyncio.to_thread(transcriber.stream, bytes(audio_buffer))
                except Exception:
                    pass
        except Exception:
            pass

        if transcriber:
            try:
                await asyncio.to_thread(transcriber.disconnect)  # ✅ non-blocking
                print("Transcriber disconnected")
            except Exception as e:
                print(f"Error disconnecting transcriber: {e}")

        if session_id and session_id in session_memory:
            del session_memory[session_id]
            print(f"Session memory cleared for: {session_id}")

        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close(code=1000, reason="Session ended")
                print("WebSocket closed")
        except Exception as e:
            print(f"Error closing websocket: {e}")

        print(f"Session cleanup completed for: {session_id}")


# Health check function for debugging
def get_active_sessions():
    return {
        "active_sessions": len(session_memory),
        "session_ids": list(session_memory.keys()),
    }
