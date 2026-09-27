"""Function tools the GPT-Live backend can call. They run on the phone, which holds the keys.

Config lives in ~/.pixel_config.json (chmod 600); set values with scripts/set_secret.py:
    {"posthog": {"host": "https://us.posthog.com", "project_id": "12345", "api_key": "phx_..."},
     "linear":  {"api_key": "lin_api_...", "team_key": "ERZ"}}
A tool whose config is missing is simply not offered to the model.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CONFIG_PATH = Path(os.environ.get("PIXEL_CONFIG", Path.home() / ".pixel_config.json"))
# Overridable so the tools can be tested against local fakes.
OPEN_METEO = os.environ.get("OPEN_METEO_URL", "https://api.open-meteo.com")
GEOCODE = os.environ.get("GEOCODE_URL", "https://geocoding-api.open-meteo.com")
LINEAR_API = os.environ.get("LINEAR_API_URL", "https://api.linear.app/graphql")

MAX_OUTPUT = 6000  # characters handed back to the backend model


class ToolError(Exception):
    pass


def load_config():
    try:
        return json.loads(CONFIG_PATH.read_text())
    except (OSError, ValueError):
        return {}


def _http(url, body=None, headers=None, timeout=20):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **(headers or {})},
                                 method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise ToolError(f"HTTP {e.code} from {urllib.parse.urlsplit(url).netloc}: "
                        f"{e.read().decode(errors='replace')[:400]}")
    except urllib.error.URLError as e:
        raise ToolError(f"Can't reach {urllib.parse.urlsplit(url).netloc}: {e.reason}")


# ---------- weather (Open-Meteo, no key) ----------

WEATHER_CODES = {
    0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 61: "light rain", 63: "rain",
    65: "heavy rain", 80: "rain showers", 81: "heavy showers", 82: "violent showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with hail",
}


def get_weather(location="Kuala Lumpur"):
    location = (location or "Kuala Lumpur").strip()
    geo = _http(f"{GEOCODE}/v1/search?" + urllib.parse.urlencode({"name": location, "count": 1}))
    hits = geo.get("results") or []
    if not hits:
        raise ToolError(f"Unknown place: {location}")
    place = hits[0]
    params = {
        "latitude": place["latitude"], "longitude": place["longitude"], "timezone": "auto", "forecast_days": 3,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
    }
    fc = _http(f"{OPEN_METEO}/v1/forecast?" + urllib.parse.urlencode(params))
    cur, daily = fc.get("current", {}), fc.get("daily", {})
    days = [
        {"date": d, "summary": WEATHER_CODES.get(code, f"code {code}"), "max_c": hi, "min_c": lo, "rain_chance_pct": p}
        for d, code, hi, lo, p in zip(daily.get("time", []), daily.get("weather_code", []),
                                      daily.get("temperature_2m_max", []), daily.get("temperature_2m_min", []),
                                      daily.get("precipitation_probability_max", []))
    ]
    return {
        "place": f"{place.get('name')}, {place.get('country', '')}".strip(", "),
        "now": {"summary": WEATHER_CODES.get(cur.get("weather_code"), "unknown"),
                "temp_c": cur.get("temperature_2m"), "feels_like_c": cur.get("apparent_temperature"),
                "humidity_pct": cur.get("relative_humidity_2m"), "wind_kmh": cur.get("wind_speed_10m")},
        "next_days": days,
    }


# ---------- PostHog (read-only HogQL) ----------

def posthog_query(hogql):
    cfg = load_config().get("posthog", {})
    host = cfg.get("host", "https://us.posthog.com").rstrip("/")
    url = f"{host}/api/projects/{cfg['project_id']}/query/"
    data = _http(url, {"query": {"kind": "HogQLQuery", "query": hogql}},
                 headers={"Authorization": f"Bearer {cfg['api_key']}"}, timeout=40)
    rows = data.get("results") or []
    return {"columns": data.get("columns"), "rows": rows[:50], "row_count": len(rows),
            "truncated": len(rows) > 50}


# ---------- Linear ----------

def _linear(query, variables=None):
    cfg = load_config().get("linear", {})
    data = _http(LINEAR_API, {"query": query, "variables": variables or {}},
                 headers={"Authorization": cfg["api_key"]})
    if data.get("errors"):
        raise ToolError("Linear: " + "; ".join(e.get("message", "?") for e in data["errors"]))
    return data["data"]


def _team_id():
    key = load_config().get("linear", {}).get("team_key", "")
    nodes = _linear("query($k:String!){teams(filter:{key:{eq:$k}}){nodes{id}}}", {"k": key})["teams"]["nodes"]
    if not nodes:
        raise ToolError(f"No Linear team with key {key!r}")
    return nodes[0]["id"]


ISSUE_FIELDS = "identifier title url priority state{name} assignee{name} labels{nodes{name}} updatedAt"


def _issue_summary(i):
    return {"id": i["identifier"], "title": i["title"], "state": (i.get("state") or {}).get("name"),
            "assignee": (i.get("assignee") or {}).get("name"), "priority": i.get("priority"),
            "labels": [l["name"] for l in (i.get("labels") or {}).get("nodes", [])], "url": i.get("url")}


def linear_search_issues(query="", limit=10):
    limit = max(1, min(int(limit or 10), 25))
    team = load_config().get("linear", {}).get("team_key", "")
    flt = {"team": {"key": {"eq": team}}}
    if query:
        flt["title"] = {"containsIgnoreCase": query}
    data = _linear(f"query($f:IssueFilter,$n:Int){{issues(filter:$f,first:$n,orderBy:updatedAt){{nodes{{{ISSUE_FIELDS}}}}}}}",
                   {"f": flt, "n": limit})
    return {"issues": [_issue_summary(i) for i in data["issues"]["nodes"]]}


KIND_LABELS = {"feature": "Feature", "bug": "Bug", "test": "Test", "improvement": "Improvement"}


def _label_id(team_id, name):
    nodes = _linear("query($t:ID!,$n:String!){issueLabels(filter:{name:{eqIgnoreCase:$n},"
                    "or:[{team:{id:{eq:$t}}},{team:{null:true}}]}){nodes{id}}}", {"t": team_id, "n": name})
    return (nodes["issueLabels"]["nodes"] or [{}])[0].get("id")


def linear_create_issue(title, kind="feature", description="", priority=0):
    team_id = _team_id()
    label = KIND_LABELS.get((kind or "").lower(), "")
    body = {"teamId": team_id, "title": title.strip(),
            "description": (description or "").strip() + "\n\n_Created by Pixel voice assistant._",
            "priority": max(0, min(int(priority or 0), 4))}
    label_id = _label_id(team_id, label) if label else None
    if label_id:
        body["labelIds"] = [label_id]
    elif label:
        body["title"] = f"[{label}] {body['title']}"
    data = _linear(f"mutation($i:IssueCreateInput!){{issueCreate(input:$i){{success issue{{{ISSUE_FIELDS}}}}}}}",
                   {"i": body})
    return {"created": _issue_summary(data["issueCreate"]["issue"])}


def linear_update_issue(issue_id, state="", comment="", title="", priority=None):
    issue = _linear("query($id:String!){issue(id:$id){id team{id}}}", {"id": issue_id})["issue"]
    changes = {}
    if title:
        changes["title"] = title
    if priority is not None:
        changes["priority"] = max(0, min(int(priority), 4))
    if state:
        nodes = _linear("query($t:ID!,$n:String!){workflowStates(filter:{team:{id:{eq:$t}},name:{eqIgnoreCase:$n}})"
                        "{nodes{id name}}}", {"t": issue["team"]["id"], "n": state})["workflowStates"]["nodes"]
        if not nodes:
            raise ToolError(f"No workflow state named {state!r}")
        changes["stateId"] = nodes[0]["id"]
    result = {}
    if changes:
        data = _linear(f"mutation($id:String!,$i:IssueUpdateInput!){{issueUpdate(id:$id,input:$i)"
                       f"{{success issue{{{ISSUE_FIELDS}}}}}}}", {"id": issue["id"], "i": changes})
        result["updated"] = _issue_summary(data["issueUpdate"]["issue"])
    if comment:
        _linear("mutation($i:CommentCreateInput!){commentCreate(input:$i){success}}",
                {"i": {"issueId": issue["id"], "body": comment}})
        result["commented"] = True
    if not result:
        raise ToolError("Nothing to change: give a state, comment, title or priority")
    return result


# ---------- registry ----------

def _fn(name, description, properties, required=()):
    return {"type": "function", "name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "required": list(required),
                           "additionalProperties": False}}


CONFIRM = " Only call this after the user has clearly said yes to the exact change."

TOOLS = {
    "get_weather": (
        _fn("get_weather", "Current weather and 3-day forecast. Defaults to Kuala Lumpur.",
            {"location": {"type": "string", "description": "City name; omit for Kuala Lumpur"}}),
        lambda a: get_weather(a.get("location") or "Kuala Lumpur"),
        None,
    ),
    "posthog_query": (
        _fn("posthog_query",
            "Read-only ErzyCall product analytics from PostHog. Takes a HogQL (ClickHouse SQL) query over "
            "the `events` table (columns: event, timestamp, distinct_id, person_id, properties.*). Examples: "
            "`SELECT event, count() c FROM events WHERE timestamp > now() - INTERVAL 30 DAY GROUP BY event "
            "ORDER BY c DESC LIMIT 20` to discover event names; `SELECT toDate(timestamp) d, "
            "count(DISTINCT person_id) FROM events WHERE timestamp > now() - INTERVAL 14 DAY GROUP BY d ORDER BY d` "
            "for daily active users. Discover event names before assuming them.",
            {"hogql": {"type": "string"}}, ["hogql"]),
        lambda a: posthog_query(a["hogql"]),
        "posthog",
    ),
    "linear_search_issues": (
        _fn("linear_search_issues", "Find ErzyCall Linear issues by title text, newest activity first. "
            "Empty query lists recently updated issues.",
            {"query": {"type": "string"}, "limit": {"type": "integer"}}),
        lambda a: linear_search_issues(a.get("query", ""), a.get("limit", 10)),
        "linear",
    ),
    "linear_create_issue": (
        _fn("linear_create_issue", "Create a Linear issue: a feature, bug, test or improvement." + CONFIRM,
            {"title": {"type": "string"},
             "kind": {"type": "string", "enum": ["feature", "bug", "test", "improvement"]},
             "description": {"type": "string", "description": "Markdown: context, acceptance criteria, repro steps"},
             "priority": {"type": "integer", "description": "0 none, 1 urgent, 2 high, 3 medium, 4 low"}},
            ["title", "kind"]),
        lambda a: linear_create_issue(a["title"], a.get("kind", "feature"), a.get("description", ""),
                                      a.get("priority", 0)),
        "linear",
    ),
    "linear_update_issue": (
        _fn("linear_update_issue", "Change a Linear issue's state/title/priority and/or add a comment, by its "
            "identifier such as ERZ-42." + CONFIRM,
            {"issue_id": {"type": "string"}, "state": {"type": "string", "description": "e.g. Todo, In Progress, Done"},
             "comment": {"type": "string"}, "title": {"type": "string"}, "priority": {"type": "integer"}},
            ["issue_id"]),
        lambda a: linear_update_issue(a["issue_id"], a.get("state", ""), a.get("comment", ""),
                                      a.get("title", ""), a.get("priority")),
        "linear",
    ),
}

REQUIRED_KEYS = {"posthog": ("project_id", "api_key"), "linear": ("api_key", "team_key")}


def enabled_tools():
    """Tool names whose config is present."""
    cfg = load_config()
    out = []
    for name, (_, _, section) in TOOLS.items():
        if section is None or all(cfg.get(section, {}).get(k) for k in REQUIRED_KEYS[section]):
            out.append(name)
    return out


def definitions():
    return [TOOLS[n][0] for n in enabled_tools()]


def run(name, arguments):
    """Run a tool call from the model. Always returns a JSON string, errors included."""
    if name not in enabled_tools():
        return json.dumps({"error": f"Tool {name!r} is not available"})
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else (arguments or {})
        result = TOOLS[name][1](args)
    except ToolError as e:
        result = {"error": str(e)}
    except (KeyError, TypeError, ValueError) as e:
        result = {"error": f"Bad arguments for {name}: {e}"}
    out = json.dumps(result, ensure_ascii=False, default=str)
    return out if len(out) <= MAX_OUTPUT else out[:MAX_OUTPUT] + " …[truncated]"
