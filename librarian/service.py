"""Run the librarian by itself: a macOS login agent that starts `serve` at login and restarts it if it stops.

    python3 -m librarian install      # start now and at every login
    python3 -m librarian uninstall    # stop and remove it

It runs as you, from this folder, and does what `serve` does: reads release feeds, files safe changes, holds
risky ones, commits locally, never pushes or deploys. Its log is librarian/var/librarian.log.
"""
import json, os, pathlib, plistlib, subprocess, sys, urllib.request

LABEL = "com.modular.librarian"
PLIST = pathlib.Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def agent(root, python=None, path=None, port=8431):
    """The login agent as data (kept separate from launchctl so it can be checked)."""
    root = pathlib.Path(root)
    log = str(root / "librarian" / "var" / "librarian.log")
    return {
        "Label": LABEL,
        "ProgramArguments": [python or sys.executable, "-m", "librarian", "serve", "--port", str(port)],
        "WorkingDirectory": str(root),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 30,
        "StandardOutPath": log,
        "StandardErrorPath": log,
        # launchd starts with a bare PATH; the librarian needs node and git
        "EnvironmentVariables": {"PATH": path or os.environ.get("PATH", "/usr/bin:/bin")},
    }


def launchctl(*args):
    return subprocess.run(["launchctl", *args], capture_output=True, text=True)


def install(root, port=8431):
    if sys.platform != "darwin":
        return False, "install is for macOS. Elsewhere, run `python3 -m librarian serve` under your service manager (systemd, cron @reboot)."
    (pathlib.Path(root) / "librarian" / "var").mkdir(parents=True, exist_ok=True)
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    PLIST.write_bytes(plistlib.dumps(agent(root, port=port)))
    uid = str(os.getuid())
    launchctl("bootout", f"gui/{uid}/{LABEL}")  # replace one that is already loaded
    r = launchctl("bootstrap", f"gui/{uid}", str(PLIST))
    if r.returncode:
        return False, "launchctl said: " + (r.stderr or r.stdout).strip()
    return True, f"installed: {PLIST}. It starts at login and restarts if it stops. Log: librarian/var/librarian.log"


def uninstall():
    if sys.platform != "darwin":
        return False, "nothing to remove on this system"
    launchctl("bootout", f"gui/{os.getuid()}/{LABEL}")
    existed = PLIST.exists()
    PLIST.unlink(missing_ok=True)
    return True, "stopped and removed" if existed else "it was not installed"


def running(port=8431):
    """Is a librarian answering? Returns its /status, or None."""
    try:
        return json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=2))
    except Exception:
        return None
