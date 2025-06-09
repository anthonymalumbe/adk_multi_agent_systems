import streamlit as st
import uuid
import requests
import json
import os
import time
import base64
import io
import wave
import audioop

from audio_recorder_streamlit import audio_recorder
from google.cloud import texttospeech
from google.cloud import speech

# ─── 1) PAGE CONFIG & GLOBAL CSS ────────────────────────────────────────────────

st.set_page_config(
    page_title="Context AI Chat",
    page_icon="💬",
    layout="wide"
)

# Make the title static by placing it before any conditional logic or reruns
st.title("📝 Context Is What You Need")

# Inject CSS to force a dark theme and recolor chat bubbles
st.markdown(
    """
    <style>
    /* ────── Page and Chat Background ────── */
    section.main {
        background: linear-gradient(180deg, #000000 0%, #0a1f39 100%) !important;
    }
    div[data-testid="stEmptyContainer"] {
        background: linear-gradient(180deg, #000000 0%, #0a1f39 100%) !important;
    }

    /* ────── Chat‐Bubble Overrides ────── */
    div[data-testid="stChatMessage"] [aria-label="User"]
    div[data-testid="stMarkdownContainer"] {
        background-color: #0D99FF !important;
        color: white !important;
        border-radius: 1rem !important;
        padding: 0.5rem !important;
    }
    div[data-testid="stChatMessage"] [aria-label="Assistant"]
    div[data-testid="stMarkdownContainer"] {
        background-color: #3c3f41 !important;
        color: white !important;
        border-radius: 1rem !important;
        padding: 0.5rem !important;
    }
    div[data-testid="stChatMessage"] {
        margin-bottom: 0.75rem !important;
    }

    /* ────── Chat‐Input Box Styling ────── */
    div[data-testid="stChatInput"] div[role="textbox"] {
        background-color: #1a1a1a !important;
        color: white !important;
        border-radius: 1rem !important;
        padding-left: 0.75rem  !important;
        padding-top: 0.5rem !important;
        padding-bottom: 0.5rem !important;
    }
    div[data-testid="stChatInput"] div[role="textbox"]::placeholder {
        color: #999999 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── 2) CONSTANTS & SESSION‐STATE SETUP ─────────────────────────────────────────

API_BASE_URL = "http://localhost:8000"
APP_NAME = "llm_news_agents"  # <<<< Make sure this matches your root agent's module name

if "user_id" not in st.session_state:
    st.session_state.user_id = f"user-{uuid.uuid4()}"

if "session_id" not in st.session_state:
    st.session_state.session_id = None

if "messages" not in st.session_state:
    st.session_state.messages = []

# New: keep track of the last raw “events” returned by the API
if "latest_events" not in st.session_state:
    st.session_state.latest_events = []

# New: track whether we're actively recording
if "is_recording" not in st.session_state:
    st.session_state.is_recording = False
    
if "record_start_time" not in st.session_state:
    st.session_state.record_start_time = None

# ─── 3) PILL STYLES FOR TOOL CALLS / RESPONSES ──────────────────────────────────

TOOL_CALL_STYLE = (
    "display: inline-block; "
    "padding: 0.2em 0.5em; "
    "margin: 0.1em 0.1em; "
    "font-size: 0.875em; "
    "font-weight: 500;"
    "background-color: #4B5563; "
    "color: white; "
    "border-radius: 0.75rem; "
    "border: 1px solid #374151;"
)

TOOL_RESPONSE_STYLE = (
    "display: inline-block; "
    "padding: 0.2em 0.5em; "
    "margin: 0.1em 0.1em; "
    "font-size: 0.875em; "
    "font-weight: 500;"
    "background-color: #4B5563; "
    "color: white; "
    "border-radius: 0.75rem; "
    "border: 1px solid #374151;"
)

# ─── 4) SESSION CREATION / MESSAGE SENDING ───────────────────────────────────────

def create_session():
    """Create a new session on the ADK server."""
    session_id = f"session-{int(time.time())}"
    try:
        resp = requests.post(
            f"{API_BASE_URL}/apps/{APP_NAME}/users/{st.session_state.user_id}/sessions/{session_id}",
            headers={"Content-Type": "application/json"},
            data=json.dumps({}),
            timeout=10
        )
        resp.raise_for_status()
        st.session_state.session_id = session_id
        st.session_state.messages = []
        st.success(f"New session created: {session_id}")
        return True
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to create session: {e}")
        st.error(
            f"Is your ADK server running at {API_BASE_URL} and is APP_NAME ('{APP_NAME}') correct?"
        )
        return False
    except Exception as e:
        st.error(f"An unexpected error occurred during session creation: {e}")
        return False

def send_message(message: str):
    """Send a message and process the multi-agent response, including tool calls."""
    if not st.session_state.session_id:
        st.error("No active session. Please create a session first.")
        return False

    st.session_state.messages.append({"role": "user", "content": message, "author": "user", "type": "text"})

    try:
        response = requests.post(
            f"{API_BASE_URL}/run",
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "app_name": APP_NAME,
                "user_id": st.session_state.user_id,
                "session_id": st.session_state.session_id,
                "new_message": {
                    "role": "user",
                    "parts": [{"text": message}]
                }
            }),
            timeout=90
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        st.error(f"API request failed: {e}")
        st.session_state.messages.append({
            "role": "assistant", "type": "error",
            "content": f"Error sending message: {e}", "author": "system_error"
        })
        return False

    try:
        events = response.json()
    except json.JSONDecodeError:
        st.error("Failed to decode API response.")
        st.session_state.messages.append({
            "role": "assistant", "type": "error",
            "content": "Error: Could not decode API response.", "author": "system_error"
        })
        return False

    # Store the raw events so we can display them in the sidebar
    st.session_state.latest_events = events or []

    if not events:
        st.warning("Received an empty list of events from the agent.")
        return True

    for event_data in events:
        author = event_data.get("author", "assistant")
        content = event_data.get("content", {})
        parts = content.get("parts", [])

        for part in parts:
            # ── Plain text chunk ──
            if "text" in part and part["text"]:
                text_content = part["text"].strip()
                if text_content:
                    st.session_state.messages.append({
                        "role": "assistant", "type": "text",
                        "content": text_content, "author": author, "audio_path": None
                    })

            # ── Tool Call ──
            if "functionCall" in part and part.get("functionCall"):
                fc_data = part["functionCall"]
                tool_name_val = "Unknown Tool"
                tool_args_val = {}

                if isinstance(fc_data, dict):
                    tool_name_val = fc_data.get("name", "Unknown Tool")
                    tool_args_val = fc_data.get("args", {})
                else:
                    st.warning(
                        f"Unexpected data type for functionCall: "
                        f"Expected a dictionary, but got {type(fc_data)}. "
                        f"Content: '{fc_data}'"
                    )

                st.session_state.messages.append({
                    "role": "assistant",
                    "type": "tool_call",
                    "tool_name": tool_name_val,
                    "tool_args": tool_args_val,
                    "author": author
                })

            # ── Tool Response ──
            if "functionResponse" in part and part.get("functionResponse"):
                fr = part["functionResponse"]
                tool_name = fr.get("name", "Unknown Tool")
                response_data = fr.get("response", {})

                # If the tool returned a dict with a "result" key, grab that; otherwise treat response_data itself as “result.”
                summary_text = f"Tool '{tool_name}' processed."
                result_field_value = None

                if isinstance(response_data, dict) and "result" in response_data:
                    result_field_value = response_data.get("result")

                # 1) If result is a dict-of-dicts (old behavior), try to extract a text chunk:
                if isinstance(result_field_value, dict):
                    rc_list = result_field_value.get("content", [])
                    if isinstance(rc_list, list) and len(rc_list) > 0 and isinstance(rc_list[0], dict):
                        text_val = rc_list[0].get("text")
                        if isinstance(text_val, str) and text_val.strip():
                            summary_text = text_val.strip()
                        else:
                            summary_text = f"Tool '{tool_name}' returned an empty text item."
                    else:
                        summary_text = f"Tool '{tool_name}' returned a dict, but no 'content'→[{{'text': ...}}] to extract."

                # 2) If result is a string → display it directly
                elif isinstance(result_field_value, str):
                    if result_field_value.strip():
                        summary_text = result_field_value.strip()
                    else:
                        summary_text = f"Tool '{tool_name}' returned an empty string."

                # 3) If result is a list → iterate and build a Markdown list of headlines/URLs
                elif isinstance(result_field_value, list):
                    if len(result_field_value) == 0:
                        summary_text = "No items returned."
                    else:
                        lines = []
                        for idx, item in enumerate(result_field_value, start=1):
                            author_name = item.get("author") or "Unknown author"
                            headline = item.get("headline") or item.get("title") or "No headline"
                            url = item.get("url") or ""
                            if url:
                                lines.append(f"{idx}. [{headline}]({url}) — *by {author_name}*")
                            else:
                                lines.append(f"{idx}. {headline} — *by {author_name}*")
                        summary_text = "\n".join(lines)

                # 4) If result is None but "result" key was absent → generic “processed”
                elif result_field_value is None and not isinstance(response_data, list) and "result" not in response_data:
                    summary_text = f"Tool '{tool_name}' processed (no 'result' field)."

                # 5) If result exists but is neither dict, str, nor list → unexpected scalar/etc.
                elif result_field_value is not None:
                    summary_text = f"Tool '{tool_name}' processed ('result' field is of unexpected type: {type(result_field_value).__name__})."

                # 6) Fallback: response_data itself might be a list (some tools respond with a raw list)
                else:
                    if isinstance(response_data, list):
                        if len(response_data) == 0:
                            summary_text = "No items returned."
                        else:
                            lines = []
                            for idx, item in enumerate(response_data, start=1):
                                if isinstance(item, dict):
                                    author_name = item.get("author") or "Unknown author"
                                    headline = item.get("headline") or item.get("title") or "No headline"
                                    url = item.get("url") or ""
                                    if url:
                                        lines.append(f"{idx}. [{headline}]({url}) — *by {author_name}*")
                                    else:
                                        lines.append(f"{idx}. {headline} — *by {author_name}*")
                                else:
                                    lines.append(f"{idx}. {repr(item)}")
                            summary_text = "\n".join(lines)
                    else:
                        summary_text = str(response_data).strip() or f"Tool '{tool_name}' returned no content."

                # Extract audio_path only if this was a TTS tool response
                audio_path = None
                if tool_name == "text_to_speech" and "File saved as:" in summary_text:
                    try:
                        path_part = summary_text.split("File saved as:", 1)[1].strip()
                        audio_path = path_part.split()[0].rstrip(".")
                        if os.path.exists(audio_path):
                            st.write(f"Audio path: {audio_path}")
                        else:
                            st.warning(f"Audio file not found: {audio_path}")
                    except IndexError:
                        pass

                st.session_state.messages.append({
                    "role": "assistant", "type": "tool_response",
                    "tool_name": tool_name, "response_summary": summary_text,
                    "response_data": response_data, "author": author, "audio_path": audio_path
                })

    return True

def display_audio_if_present(message_data):
    """
    If this message_data has an 'audio_path' key, try to play it
    either from a local file or a URL.
    """
    if "audio_path" in message_data and message_data["audio_path"]:
        path = message_data["audio_path"]
        if not (path.startswith("http://") or path.startswith("https://")):
            # Local file
            if os.path.exists(path):
                try:
                    with open(path, "rb") as f:
                        st.audio(f.read(), format="audio/mpeg")
                except Exception as e:
                    st.warning(f"Could not play audio file: {path}. Error: {e}")
            else:
                st.warning(f"Audio file not found: {path}")
        else:
            # Remote URL
            st.audio(path)

# ─── 5) MAIN PAGE LAYOUT ────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Session Management")

    if st.session_state.session_id:
        st.success(f"Active session: {st.session_state.session_id}")
        if st.button("➕ New Session"):
            if create_session():
                st.rerun()
    else:
        st.warning("No active session")
        if st.button("➕ Create Session"):
            if create_session():
                st.rerun()

    st.divider()
    st.caption(f"Interacting with App: **{APP_NAME}**")
    st.caption(f"ADK API Server: {API_BASE_URL}")
    st.caption("Ensure ADK server is running & APP_NAME is correct.")

    # ─── 6) SIDEBAR SECTION: RAW “EVENTS” (click‐to‐expand style) ───────────────────
    st.divider()
    st.header("Latest Agent Events")
    if st.session_state.latest_events:
        for idx, evt in enumerate(st.session_state.latest_events):
            evt_type_label = "unknown"
            content = evt.get("content", {})
            parts = content.get("parts", [])
            if parts and isinstance(parts, list):
                part = parts[0] or {}
                if part.get("functionCall"):
                    name = part["functionCall"].get("name", "")
                    evt_type_label = f"functionCall:{name}"
                elif part.get("functionResponse"):
                    name = part["functionResponse"].get("name", "")
                    evt_type_label = f"functionResponse:{name}"
                elif part.get("text"):
                    txt = part["text"].replace("\n", " ")
                    snippet = txt[:40].rstrip()
                    if len(txt) > 40:
                        snippet += "…"
                    evt_type_label = f"text:{snippet}"
                else:
                    evt_type_label = "unknown"
            else:
                evt_type_label = "empty"

            with st.expander(f"**{idx}** {evt_type_label}", expanded=False):
                st.json(evt)
    else:
        st.caption("No events to show yet.")

if not st.session_state.get("session_id"):
    st.info("👈 Create a session from the sidebar to start chatting.")
else:
    # ── Display all messages in session_state.messages ──────────────────────────
    if "messages" in st.session_state and st.session_state.messages:
        for i, msg in enumerate(st.session_state.messages):
            msg_type = msg.get("type", "text")
            author = msg.get("author", msg.get("role", "assistant"))
            role_for_streamlit = "user" if author.lower() == "user" else "assistant"

            with st.chat_message(role_for_streamlit):
                if author.lower() not in ["user", "assistant", "model", "system_error"]:
                    st.caption(author.replace("_", " ").title())

                if msg_type == "text":
                    text_content = msg.get("content", "")
                    if "---END-OF-EDIT---" in text_content:
                        text_content = text_content.split("---END-OF-EDIT---")[0].strip()
                    st.markdown(text_content)

                    # ── Button to Generate and Play Speech for Assistant's Text Messages ──
                    if role_for_streamlit == "assistant" and text_content.strip():
                        button_key = f"tts_play_{msg.get('id', i)}"
                        if st.button("🔊 Convert text to speech", key=button_key):
                            try:
                                tts_client = texttospeech.TextToSpeechClient()
                                synthesis_input = texttospeech.SynthesisInput(text=text_content)
                                voice = texttospeech.VoiceSelectionParams(
                                    language_code="en-US",
                                    ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
                                )
                                audio_config = texttospeech.AudioConfig(
                                    audio_encoding=texttospeech.AudioEncoding.MP3
                                )
                                with st.spinner("Generating audio, please wait... 🎶"):
                                    tts_response = tts_client.synthesize_speech(
                                        input=synthesis_input,
                                        voice=voice,
                                        audio_config=audio_config,
                                    )
                                    mp3_bytes = tts_response.audio_content
                                st.audio(mp3_bytes, format="audio/mp3")
                                b64 = base64.b64encode(mp3_bytes).decode("utf-8")
                                download_filename = f"assistant_speech_{button_key}.mp3"
                                st.markdown(
                                    f'<a href="data:audio/mp3;base64,{b64}" download="{download_filename}">Download Audio</a>',
                                    unsafe_allow_html=True
                                )
                            except ImportError:
                                st.error(
                                    "Google Cloud Text-to-Speech library not found. "
                                    "Please ensure it's installed (e.g., `pip install google-cloud-texttospeech`)."
                                )
                            except Exception as e:
                                st.error(f"An error occurred during speech generation: {e}")

                elif msg_type == "tool_call":
                    tool_name = msg.get("tool_name", "Unknown Tool")
                    st.markdown(
                        f"<span style='{TOOL_CALL_STYLE}'>⚡ {tool_name}</span>",
                        unsafe_allow_html=True
                    )
                    tool_args = msg.get("tool_args", {})
                    if tool_args:
                        with st.expander(f"Arguments for {tool_name}", expanded=False):
                            st.json(tool_args)

                elif msg_type == "tool_response":
                    tool_name = msg.get("tool_name", "Unknown Tool")
                    st.markdown(
                        f"<span style='{TOOL_RESPONSE_STYLE}'>✓ {tool_name}</span>",
                        unsafe_allow_html=True
                    )
                    summary = msg.get("response_summary", "")
                    is_generic = summary == f"Tool '{tool_name}' processed."
                    is_tts_tool_response = tool_name == "text_to_speech" and "File saved as:" in summary

                    if summary and not is_generic and not is_tts_tool_response:
                        st.caption(f"↳ {summary}")
                    display_audio_if_present(msg)

                elif msg_type == "error":
                    st.error(f"**Error from {author}:** {msg.get('content', 'No error details')}")
                else:
                    st.markdown(msg.get("content", f"Message of type '{msg_type}' received."))
                    display_audio_if_present(msg)
    else:
        st.info("No messages in the current session yet.")

import streamlit as st
import io
import time
import wave
import audioop

from google.cloud import speech

# ─── 7) INPUT SECTION ──────────────────────────────────────────────────────────

# 1) Typing input
user_input = st.chat_input("Type your message…")
if user_input:
    if send_message(user_input):
        # Only rerun if send_message returned True (i.e. the message was sent)
        st.rerun()


# 2) Separator
st.markdown("---")
st.subheader("Voice Input")

recorded_bytes = None

# 3) Try to show an audio recorder widget
try:
    # audio_recorder provides its own Start/Stop button and shows elapsed time.
    recorded_bytes = audio_recorder(
        text="",                   # Hide its default labels
        recording_color="#53f707eb",
        neutral_color="#4217ddfd",
        icon_name="microphone",
        icon_size="0.5x",
        key="audio_recorder",
    )
except ImportError:
    st.info(
        "To use voice input, please install the audio recorder component:\n\n"
        "```bash\n"
        "pip install streamlit-audiorecorder\n"
        "```"
    )
    recorded_bytes = None
except Exception as e:
    st.error(f"Error initialising the audio recorder: {e}")
    recorded_bytes = None


# 4) Once recording stops, `audio_recorder` returns bytes
if recorded_bytes:
    # Transcribe inside a spinner
    with st.spinner("Transcribing your spoken question…"):
        try:
            # ----- Convert stereo to mono (if needed) -----
            in_buffer = io.BytesIO(recorded_bytes)
            wf = wave.open(in_buffer, "rb")

            if wf.getnchannels() == 1:
                # Already mono → just rewind and grab the raw bytes
                wf.rewind()
                mono_bytes = in_buffer.getvalue()
            else:
                # Convert to mono
                frames = wf.readframes(wf.getnframes())
                mono_frames = audioop.tomono(
                    frames,
                    wf.getsampwidth(),  # sample width in bytes
                    1,                  # left channel weight
                    1                   # right channel weight
                )
                out_buffer = io.BytesIO()
                monowf = wave.open(out_buffer, "wb")
                monowf.setnchannels(1)
                monowf.setsampwidth(wf.getsampwidth())
                monowf.setframerate(wf.getframerate())
                monowf.writeframes(mono_frames)
                monowf.close()
                mono_bytes = out_buffer.getvalue()

            # ----- Call Google Cloud Speech-to-Text -----
            speech_client = speech.SpeechClient()
            audio = speech.RecognitionAudio(content=mono_bytes)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=48000,
                language_code="en-US",
            )

            response = speech_client.recognize(config=config, audio=audio)
            transcript = "\n".join(
                res.alternatives[0].transcript for res in response.results
            )

            if transcript:
                st.write(f"**Transcribed:** {transcript}")
                if send_message(transcript):
                    st.rerun()
            else:
                st.warning("No speech detected. Please try recording again.")
        except Exception as e:
            st.session_state.is_recording = False
            st.error(f"Error during transcription: {e}")
