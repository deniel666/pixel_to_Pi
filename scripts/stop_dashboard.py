#!/usr/bin/env python3
"""Stop every running dashboard server.py and wait until its port is free.

Doesn't rely on pkill/pgrep, which aren't always installed in Termux or don't
match how Android reports the process. It reads /proc directly instead.
Exit code 0 = port free, 1 = something still holds it.
"""
import os
import signal
import socket
import sys
import time

PORT = int(os.environ.get("PORT", "8000"))
ME = os.getpid()


def dashboard_pids():
    pids = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit() or int(entry) == ME:
            continue
        try:
            with open(f"/proc/{entry}/cmdline", "rb") as f:
                args = f.read().split(b"\0")
        except OSError:
            continue
        # A python process whose script argument is server.py (any path).
        if args and b"python" in os.path.basename(args[0]) and any(
                os.path.basename(a) == b"server.py" for a in args[1:]):
            pids.append(int(entry))
    return pids


def port_free():
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("0.0.0.0", PORT))
        return True
    except OSError:
        return False
    finally:
        s.close()


def main():
    pids = dashboard_pids()
    if "--list" in sys.argv:  # report only, stop nothing (used by diagnose.sh)
        print(f"server.py pids: {pids or 'none'}; port {PORT} {'free' if port_free() else 'IN USE'}")
        return 0
    print(f"dashboard processes: {pids or 'none'}")
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pid in pids:
            try:
                os.kill(pid, sig)
            except OSError:
                pass
        for _ in range(20):
            if port_free():
                print(f"port {PORT} is free")
                return 0
            time.sleep(0.25)
        pids = dashboard_pids()
    print(f"port {PORT} is STILL in use by something that isn't server.py", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
