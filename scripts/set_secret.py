#!/usr/bin/env python3
"""Set one value in ~/.pixel_config.json from stdin, so secrets never touch a command line.

From the Mac (the value comes from the clipboard):
    pbpaste | ssh -p 8022 localhost 'python ~/pixel_to_Pi/scripts/set_secret.py linear.api_key'
Non-secret values can be echoed:
    echo ERZ | ssh -p 8022 localhost 'python ~/pixel_to_Pi/scripts/set_secret.py linear.team_key'
Show what is set (values masked):
    ssh -p 8022 localhost 'python ~/pixel_to_Pi/scripts/set_secret.py --show'
"""
import json
import os
import sys
from pathlib import Path

PATH = Path(os.environ.get("PIXEL_CONFIG", Path.home() / ".pixel_config.json"))


def load():
    try:
        return json.loads(PATH.read_text())
    except (OSError, ValueError):
        return {}


def mask(value):
    value = str(value)
    return value if len(value) <= 8 else value[:4] + "…" + value[-2:]


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    cfg = load()
    if sys.argv[1] == "--show":
        for section, values in cfg.items():
            for key, value in values.items():
                shown = mask(value) if "key" in key else value
                print(f"{section}.{key} = {shown}")
        return
    section, _, key = sys.argv[1].partition(".")
    if not key:
        sys.exit("Use section.key, e.g. linear.api_key")
    value = sys.stdin.read().strip()
    if not value:
        sys.exit("Nothing on stdin; copy the value first")
    cfg.setdefault(section, {})[key] = value
    old_umask = os.umask(0o077)
    try:
        PATH.write_text(json.dumps(cfg, indent=2))
    finally:
        os.umask(old_umask)
    PATH.chmod(0o600)
    print(f"Set {section}.{key} ({len(value)} chars) in {PATH}")


if __name__ == "__main__":
    main()
