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
# Backend model for delegated reasoning and web search (Responses delegation).
# Docs suggest gpt-5.6-terra, or gpt-5.6-luna for lower cost. "none" = voice only.
BACKEND = os.environ.get("LIVE_BACKEND_MODEL", "gpt-5.6-terra")

# Structure follows OpenAI's "Prompting GPT-Live" template; keep the three policy headings.
INSTRUCTIONS = os.environ.get("LIVE_INSTRUCTIONS", """\
You are Pixel, a calm, friendly voice assistant running on the user's Pixel 7 Pro,
which is hooked up to a big monitor as a home tinker computer.
Speak warmly and naturally. Keep replies short and conversational.
Speak the language the user speaks; they often speak Russian.

Backchannel policy: Use moderate backchannels. Acknowledge naturally without competing with the main response.

Interruption policy: Stop speaking when the user interrupts. Listen to what they say.

Delegation policy:
Backend tools:
- Web search: look up current information such as news, weather, prices, and facts.

Delegate to the backend when:
- The request needs current information, a web search, or careful reasoning.
- A correction changes the work already requested.

Do not delegate to the backend when:
- You can answer from the conversation or a still-current result.
- You need a brief clarification to understand the request.

Delegate before giving an answer that depends on backend work.
Do not guess the result while waiting.
""")

BACKEND_INSTRUCTIONS = """\
## Voice conversation context
You are helping an assistant in a live voice conversation. Transcripts can contain
mistakes, unfinished phrases, and later corrections. Use the latest context. If a
needed detail is still unclear, ask for that detail instead of guessing.

## Task instructions
Answer the user's question, using web search for anything current.

## Return the result
Return the relevant facts briefly, in the user's language. No Markdown.
"""


def api_key():
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        path = Path.home() / ".openai_key"
        if path.exists():
            key = path.read_text().strip()
    return key


def session_configs():
    """Configs to try in order: full, then without delegation, then minimal.

    Only model, instructions and delegation are confirmed by the docs; the voice
    field is a best guess, so each fallback drops the less certain parts.
    """
    base = {"model": MODEL, "instructions": INSTRUCTIONS}
    voice = {"audio": {"output": {"voice": VOICE}}}
    configs = []
    if BACKEND.lower() != "none":
        delegation = {"delegation": {"type": "responses", "responses": {
            "model": BACKEND,
            "instructions": BACKEND_INSTRUCTIONS,
            "tools": [{"type": "web_search"}],
        }}}
        configs += [("responses+voice", {**base, **voice, **delegation}),
                    ("responses", {**base, **delegation})]
    configs += [("voice-only", {**base, **voice}), ("minimal", base)]
    return configs


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
    """Returns (session_id, answer_sdp), falling back through session_configs() on 4xx."""
    key = api_key()
    if not key:
        raise LiveError("No OpenAI API key: put it in ~/.openai_key on the phone (chmod 600).")
    last = None
    for name, cfg in session_configs():
        body = {"session": cfg, "transport": {"type": "webrtc", "sdp": offer_sdp}}
        try:
            data = _post(API, body, key)
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode(errors='replace')[:800]}"
            print(f"GPT-Live session create failed ({name}): {last}")
            if e.code in (401, 429) or e.code >= 500:
                break  # bad key, quota, or outage: a smaller config won't help
            continue
        except urllib.error.URLError as e:
            raise LiveError(f"Can't reach OpenAI: {e.reason}")
        sdp = (data.get("transport") or {}).get("sdp")
        if not sdp:
            raise LiveError(f"Unexpected response, no SDP answer: {json.dumps(data)[:800]}")
        sid = (data.get("session") or {}).get("id", "")
        print(f"GPT-Live session {sid} started ({name})")
        return sid, sdp
    raise LiveError(last or "GPT-Live session create failed")


def hangup(session_id):
    key = api_key()
    if key and session_id:
        try:
            _post(f"{API}/{session_id}/hangup", {}, key)
        except Exception as e:  # hanging up is best effort; the session also ends when WebRTC closes
            print(f"hangup failed: {e}")
