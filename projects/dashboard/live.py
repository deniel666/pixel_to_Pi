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

import tools

API = os.environ.get("LIVE_API_URL", "https://api.openai.com/v1/live/sessions")
MODEL = os.environ.get("LIVE_MODEL", "gpt-live-1")
VOICE = os.environ.get("LIVE_VOICE", "marin")
# Backend model for delegated reasoning and tools (Responses delegation).
# Docs suggest gpt-5.6-terra, or gpt-5.6-luna for lower cost. "none" = voice only.
BACKEND = os.environ.get("LIVE_BACKEND_MODEL", "gpt-5.6-terra")

# Spoken capability list per tool, so GPT-Live knows what it can hand off.
CAPABILITIES = {
    "web_search": "Web search: news, facts, prices, anything current.",
    "get_weather": "Weather: current conditions and 3-day forecast (Kuala Lumpur unless another place is named).",
    "posthog_query": "ErzyCall analytics from PostHog: events, active users, funnels, trends.",
    "linear_search_issues": "Linear: look up ErzyCall issues and their status.",
    "linear_create_issue": "Linear: create feature, bug, test or improvement issues (after the user confirms).",
    "linear_update_issue": "Linear: move, retitle, reprioritise or comment on issues (after the user confirms).",
}


def live_instructions(tool_names):
    caps = "\n".join(f"- {CAPABILITIES[n]}" for n in ["web_search", *tool_names] if n in CAPABILITIES)
    # Structure follows OpenAI's "Prompting GPT-Live" template; keep the three policy headings.
    return os.environ.get("LIVE_INSTRUCTIONS", f"""\
You are Pixel, a sharp, friendly voice assistant and brainstorming partner for Deni and Artur,
the co-founders of ErzyCall (AI phone calls and WhatsApp agents). You run on a Pixel 7 Pro
on their desk. They are in Kuala Lumpur.
Speak warmly and naturally, short and conversational. Speak the language the user speaks (often Russian).
When brainstorming: build on ideas, ask one pointed question at a time, push back when something
sounds weak, and suggest capturing clear decisions as Linear issues.

Backchannel policy: Use moderate backchannels. Acknowledge naturally without competing with the main response.

Interruption policy: Stop speaking when the user interrupts. Listen to what they say.

Delegation policy:
Backend tools:
{caps}

Delegate to the backend when:
- The request needs current information, weather, analytics, Linear, or careful reasoning.
- The user confirms a Linear change you proposed.
- A correction changes the work already requested.

Do not delegate to the backend when:
- You can answer from the conversation or a still-current result.
- You need a brief clarification to understand the request.

Before any Linear create or update, say exactly what will be created or changed and ask for a yes.
Delegate before giving an answer that depends on backend work.
Do not guess the result while waiting.
""")


BACKEND_INSTRUCTIONS = """\
## Voice conversation context
You are helping an assistant in a live voice conversation between Deni and Artur, the founders of
ErzyCall. Transcripts can contain mistakes, unfinished phrases, and later corrections. Use the latest
context. If a needed detail is still unclear, ask for that detail instead of guessing.

## Task instructions
- Current events, news and facts: use web search.
- Weather: use get_weather; default to Kuala Lumpur.
- ErzyCall analytics: use posthog_query. First discover event names if unsure, then query. Report
  numbers with the time range they cover.
- Linear: search before creating to avoid duplicates. Only create or update an issue when the
  conversation shows the user explicitly said yes to that exact change; otherwise return the proposed
  change and ask for confirmation. Write clear titles, and for bugs include repro steps and expected
  versus actual behaviour; for features include acceptance criteria.
- Report an action as done only after the tool confirms success, and give the issue ID (e.g. ERZ-42).

## Return the result
Return the relevant facts briefly, in the user's language, easy to say aloud. No Markdown, no URLs.
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
    names = tools.enabled_tools()
    base = {"model": MODEL, "instructions": live_instructions(names)}
    voice = {"audio": {"output": {"voice": VOICE}}}
    configs = []
    if BACKEND.lower() != "none":
        delegation = {"delegation": {"type": "responses", "responses": {
            "model": BACKEND,
            "instructions": BACKEND_INSTRUCTIONS,
            "tools": [{"type": "web_search"}, *tools.definitions()],
            "tool_choice": "auto",
        }}}
        configs += [("responses+voice", {**base, **voice, **delegation}),
                    ("responses", {**base, **delegation})]
    # Without delegation there is no backend, so no search or tools: say so in the prompt.
    bare = {"model": MODEL, "instructions": live_instructions([]).split("Delegation policy:")[0]
            + "You have no tools in this session. If asked for current information, analytics or "
              "Linear, say that tools are unavailable right now."}
    configs += [("voice-only", {**bare, **voice}), ("minimal", bare)]
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
    """Returns (session_id, answer_sdp, config_name), falling back through session_configs() on 4xx."""
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
        print(f"GPT-Live session {sid} started ({name}; tools: {', '.join(tools.enabled_tools())})")
        return sid, sdp, name
    raise LiveError(last or "GPT-Live session create failed")


def hangup(session_id):
    key = api_key()
    if key and session_id:
        try:
            _post(f"{API}/{session_id}/hangup", {}, key)
        except Exception as e:  # hanging up is best effort; the session also ends when WebRTC closes
            print(f"hangup failed: {e}")
