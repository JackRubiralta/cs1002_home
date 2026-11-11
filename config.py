"""Paths and small shared helpers. Standard library only."""

import json
import os
import stat
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Where your CS1002 work lives. Change with the CS1002_HOME environment variable.
HOME = os.path.abspath(os.path.expanduser(os.environ.get("CS1002_HOME", os.path.join("~", "CS1002"))))
MIRROR_ROOT = os.path.join(HOME, "studres")              # like /cs/studres on a lab PC
MIRROR = os.path.join(MIRROR_ROOT, "CS1002")             # read-only copy of StudRes CS1002
EXERCISES = os.path.join(HOME, "Exercises")              # your exercise answers
COURSEWORK = os.path.join(HOME, "Coursework")            # your assignment work
MOCK = os.path.join(HOME, "MockTest")                    # one folder per mock-test attempt

STATE_DIR = os.path.abspath(os.path.expanduser(os.environ.get("CS1002_STATE", os.path.join("~", ".cs1002_home"))))
PROFILE_DIR = os.path.join(STATE_DIR, "browser")         # our own browser profile (keeps the sign-in)
STATE_FILE = os.path.join(STATE_DIR, "state.json")
MANIFEST = os.path.join(STATE_DIR, "manifest.json")      # StudRes time of every file we have

ENV_FILE = os.path.join(HERE, ".env")
ENV_TEMPLATE = """# Optional: your St Andrews sign-in, only ever typed into the Microsoft login page.
# Leave PASSWORD empty to type it yourself in the browser window.
# This file is never committed (.gitignore) and is kept readable by you alone.
EMAIL=
PASSWORD=
"""


def say(msg=""):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:          # old Windows consoles
        print(msg.encode("ascii", "replace").decode(), flush=True)


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, sort_keys=True)
    os.replace(tmp, path)


def load_state():
    return _read_json(STATE_FILE, {})


def save_state(data):
    _write_json(STATE_FILE, data)


def load_manifest():
    return _read_json(MANIFEST, {})


def save_manifest(data):
    _write_json(MANIFEST, data)


def load_env():
    """(email, password) from .env; creates the template the first time."""
    if not os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, "w", encoding="utf-8") as f:
                f.write(ENV_TEMPLATE)
        except OSError:
            return None, None
    if os.name != "nt":
        try:
            if stat.S_IMODE(os.stat(ENV_FILE).st_mode) & 0o077:
                os.chmod(ENV_FILE, 0o600)
        except OSError:
            pass
    vals = {}
    try:
        with open(ENV_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    vals[k.strip().upper()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return vals.get("EMAIL") or None, vals.get("PASSWORD") or None


IS_WINDOWS = os.name == "nt"
PY = sys.executable
