"""GPT-Live session broker: the phone's server holds the API key, the browser never sees it.

The browser sends its WebRTC SDP offer here. We create the Live session on
OpenAI with the offer and hand back the SDP answer. After that, audio flows
directly between the browser and OpenAI.

Key lookup: $OPENAI_API_KEY, else the file ~/.openai_key.
"""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

API = os.environ.get("LIVE_API_URL", "https://api.openai.com/v1/live/sessions")
MODEL = os.environ.get("LIVE_MODEL", "gpt-live-1")
VOICE = os.environ.get("LIVE_VOICE", "marin")
# Model that handles delegated reasoning/tools (Responses delegation). Set to
# "none" to run voice-only, with no delegation block in the session.
BACKEND = os.environ.get("LIVE_BACKEND_MODEL", "gpt-5.5")

INSTRUCTIONS = os.environ.get("LIVE_INSTRUCTIONS", (
    "You are Pixel, a friendly voice assistant running on the user's Pixel 7 Pro, "
    "which is hooked up to a big monitor as a home tinker computer. Keep replies short "
    "and conversational. Reply in the language the user speaks (often Russian). "
    "Delegate anything that needs current information or web search."
))


def api_key():
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        path = Path.home() / ".openai_key"
        if path.exists():
            key = path.read_text().strip()
    return key


def session_config(delegate=True):
    cfg = {
        "model": MODEL,
        "instructions": INSTRUCTIONS,
        "audio": {"output": {"voice": VOICE}},
    }
    if delegate and BACKEND.lower() != "none":
        cfg["delegation"] = {
            "type": "responses",
            "responses": {"model": BACKEND, "tools": [{"type": "web_search"}]},
        }
    return cfg


def _post(url, body, key):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw.strip() else {}


class LiveError(Exception):
    """Carries OpenAI's own error text so it can be shown on screen verbatim."""


def create_session(offer_sdp):
    """Returns (session_id, answer_sdp). If delegation is rejected, retries voice-only."""
    key = api_key()
    if not key:
        raise LiveError("No OpenAI API key: put it in ~/.openai_key on the phone (chmod 600).")
    last = None
    for delegate in (True, False):
        body = {"session": session_config(delegate), "transport": {"type": "webrtc", "sdp": offer_sdp}}
        try:
            data = _post(API, body, key)
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode(errors='replace')[:800]}"
            print(f"GPT-Live session create failed (delegation={delegate}): {last}")
            continue
        except urllib.error.URLError as e:
            raise LiveError(f"Can't reach OpenAI: {e.reason}")
        sdp = (data.get("transport") or {}).get("sdp")
        if not sdp:
            raise LiveError(f"Unexpected response, no SDP answer: {json.dumps(data)[:800]}")
        sid = (data.get("session") or {}).get("id", "")
        print(f"GPT-Live session {sid} started (delegation={delegate})")
        return sid, sdp
    raise LiveError(last or "GPT-Live session create failed")


def hangup(session_id):
    key = api_key()
    if key and session_id:
        try:
            _post(f"{API}/{session_id}/hangup", {}, key)
        except Exception as e:  # hanging up is best effort; the session also ends when WebRTC closes
            print(f"hangup failed: {e}")
