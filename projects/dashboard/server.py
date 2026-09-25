#!/usr/bin/env python3
"""Live phone dashboard: battery, sensors, memory, and an optional Pico W LED.

Runs with the standard library only. On the phone it reads real data through
Termux:API; anywhere else it falls back to demo mode with fake data.

    python server.py                         # http://localhost:8000
    PORT=9000 python server.py
    PICO_URL=http://192.168.1.50 python server.py   # enable LED controls
"""
import json
import math
import os
import random
import shutil
import subprocess
import threading
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import live

PORT = int(os.environ.get("PORT", "8000"))
PICO_URL = os.environ.get("PICO_URL", "").rstrip("/")
DARK_LUX = float(os.environ.get("DARK_LUX", "15"))
STATIC = Path(__file__).parent / "static"

state = {
    "demo": False,
    "battery": {},
    "accel": [0.0, 0.0, 9.8],
    "lux": None,
    "memory": {},
    "uptime": 0,
    "pico": {"enabled": bool(PICO_URL), "on": False, "auto": False, "error": None},
    # GPT-Live voice assistant, driven from voice.html in the phone's browser.
    "voice": {"status": "idle", "session": "", "error": None, "lines": []},
}
lock = threading.Lock()
started = time.time()


def run_json(*cmd, timeout=15):
    """Run a termux-* command and parse its JSON; {} if it fails or prints non-JSON."""
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return {}
    try:
        return json.loads(out) if out.strip() else {}
    except ValueError:
        print(f"{cmd[0]} printed non-JSON output: {out.strip()[:200]!r}")
        return {}


def termux_api_works():
    """The termux-api package can be installed while the Termux:API app is missing."""
    if shutil.which("termux-battery-status") is None:
        return False
    return "percentage" in run_json("termux-battery-status", timeout=10)


def read_memory():
    info = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                key, val = line.split(":", 1)
                info[key] = int(val.split()[0])  # kB
    except OSError:
        return {}
    total = info.get("MemTotal", 0)
    avail = info.get("MemAvailable", 0)
    return {"total_mb": total // 1024, "used_mb": (total - avail) // 1024}


def pick_sensors():
    """Find accelerometer + light sensor names; they differ between phones."""
    names = run_json("termux-sensor", "-l").get("sensors", [])
    accel = next((n for n in names if "accelerometer" in n.lower() and "uncal" not in n.lower()), None)
    light = next((n for n in names if "light" in n.lower()), None)
    return accel, light


def stream_sensors():
    """Keep a termux-sensor process running and parse its stream of JSON objects."""
    accel_name, light_name = pick_sensors()
    wanted = ",".join(n for n in (accel_name, light_name) if n)
    if not wanted:
        print("No sensors from Termux:API. Instead, open "
              f"http://localhost:{PORT}/sensors.html in Chrome on the phone.")
        return
    print(f"Streaming sensors: {wanted}")
    decoder = json.JSONDecoder()
    while True:
        proc = subprocess.Popen(
            ["termux-sensor", "-s", wanted, "-d", "100"],
            stdout=subprocess.PIPE, text=True,
        )
        buf = ""
        for chunk in iter(lambda: proc.stdout.readline(), ""):
            buf += chunk
            while True:
                buf = buf.lstrip()
                try:
                    obj, end = decoder.raw_decode(buf)
                except json.JSONDecodeError:
                    break
                buf = buf[end:]
                with lock:
                    for name, data in obj.items():
                        vals = data.get("values", [])
                        if name == accel_name and len(vals) >= 3:
                            state["accel"] = vals[:3]
                        elif name == light_name and vals:
                            state["lux"] = vals[0]
        proc.wait()
        subprocess.run(["termux-sensor", "-c"], capture_output=True)
        time.sleep(2)


def poll_slow():
    """Battery and memory change slowly, so poll them every few seconds."""
    while True:
        try:
            batt = run_json("termux-battery-status")
        except Exception as e:  # keep the dashboard alive if Termux:API hiccups
            batt = {"error": str(e)}
        with lock:
            state["battery"] = batt
        time.sleep(5)


def demo_loop():
    t = 0.0
    while True:
        t += 0.1
        with lock:
            state["accel"] = [3 * math.sin(t / 3), 3 * math.cos(t / 4), 9.3]
            state["lux"] = max(0.0, 120 + 110 * math.sin(t / 8) + random.uniform(-5, 5))
            state["battery"] = {
                "percentage": 80 + int(10 * math.sin(t / 50)),
                "status": "CHARGING",
                "temperature": round(31 + math.sin(t / 20), 1),
                "health": "GOOD",
            }
        time.sleep(0.1)


def set_led(on):
    pico = state["pico"]
    try:
        urllib.request.urlopen(f"{PICO_URL}/led?on={int(on)}", timeout=3).read()
        pico["on"], pico["error"] = on, None
    except Exception as e:
        pico["error"] = str(e)


def auto_led_loop():
    """When auto mode is on, the LED follows the room: dark room turns the light on."""
    while True:
        with lock:
            auto, lux, on = state["pico"]["auto"], state["lux"], state["pico"]["on"]
        if auto and lux is not None:
            want = lux < DARK_LUX
            if want != on:
                with lock:
                    set_led(want)
        time.sleep(1)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def log_message(self, *args):
        pass  # the page polls a lot; keep the terminal quiet

    def send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def start_live(self, offer):
        """Broker the WebRTC offer to OpenAI; the API key never leaves the phone."""
        if not offer:
            return self.send_json({"error": "missing sdp"}, 400)
        try:
            sid, answer = live.create_session(offer)
        except live.LiveError as e:
            with lock:
                state["voice"].update(status="error", error=str(e))
            return self.send_json({"error": str(e)}, 502)
        with lock:
            state["voice"].update(status="connected", session=sid, error=None)
        return self.send_json({"sdp": answer, "session": sid})

    def do_GET(self):
        if self.path == "/api/stats":
            with lock:
                state["memory"] = read_memory()
                state["uptime"] = int(time.time() - started)
                return self.send_json(state)
        return super().do_GET()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(length) or "{}")
        except ValueError:
            return self.send_json({"error": "bad json"}, 400)
        if self.path == "/api/live":
            return self.start_live(req.get("sdp", ""))
        if self.path == "/api/live/hangup":
            with lock:
                sid = state["voice"]["session"]
                state["voice"].update(status="idle", session="")
            live.hangup(sid)
            return self.send_json({"ok": True})
        if self.path == "/api/voice":
            # Transcript lines and status from voice.html, shown on the big-screen dashboard.
            with lock:
                v = state["voice"]
                if req.get("status"):
                    v["status"] = str(req["status"])[:40]
                if req.get("line"):
                    v["lines"] = (v["lines"] + [str(req["line"])[:500]])[-8:]
            return self.send_json({"ok": True})
        if self.path == "/api/motion":
            # Sent by sensors.html in the phone's browser: a fallback for when
            # Termux:API can't read sensors (e.g. the Google Play build of Termux).
            with lock:
                accel = req.get("accel")
                if isinstance(accel, list) and len(accel) >= 3:
                    state["accel"] = [float(v) for v in accel[:3]]
                if isinstance(req.get("lux"), (int, float)):
                    state["lux"] = float(req["lux"])
            return self.send_json({"ok": True})
        if self.path != "/api/led":
            return self.send_json({"error": "not found"}, 404)
        if not PICO_URL:
            return self.send_json({"error": "start the server with PICO_URL set"}, 400)
        with lock:
            if "auto" in req:
                state["pico"]["auto"] = bool(req["auto"])
            if "on" in req:
                state["pico"]["auto"] = False
                set_led(bool(req["on"]))
            return self.send_json(state["pico"])


def main():
    demo = not termux_api_works()
    state["demo"] = demo
    workers = [demo_loop] if demo else [stream_sensors, poll_slow]
    if PICO_URL:
        workers.append(auto_led_loop)
    for fn in workers:
        threading.Thread(target=fn, daemon=True).start()

    mode = "live Termux:API"
    if demo:
        mode = "DEMO mode: Termux:API not responding"
        if shutil.which("termux-battery-status"):
            print("Install the Termux:API app (same source as Termux), open it once, then restart.")
    print(f"Dashboard on http://0.0.0.0:{PORT}  [{mode}]")
    if PICO_URL:
        print(f"Pico W LED at {PICO_URL}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
