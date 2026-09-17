"""Starts Jobcu: runs the local server and opens Jobcu in the browser.

This is what the "Start Jobcu" files run. Environment variables:

- JOBCU_NO_BROWSER=1  start without opening the browser
- JOBCU_SELFTEST=1    start, check that Jobcu answers, then stop (used by tests)
"""

import json
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

import uvicorn

from jobcu import __version__
from jobcu.app import create_app
from jobcu.build import build_id
from jobcu.logs import setup_logging
from jobcu.paths import ensure_data_dir

HOST = "127.0.0.1"
PREFERRED_PORT = 8765
STARTUP_TIMEOUT_SECONDS = 60

# Talk to 127.0.0.1 directly, never through a proxy configured on the computer.
_local_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def url_for(port: int) -> str:
    return f"http://{HOST}:{port}/"


def is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if os.name == "posix":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((HOST, port))
        except OSError:
            return False
    return True


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def running_jobcu(port: int, timeout: float = 1.0) -> dict | None:
    """Return what the Jobcu answering on this port says about itself, or None."""
    try:
        with _local_opener.open(f"http://{HOST}:{port}/api/health", timeout=timeout) as resp:
            data = json.load(resp)
    except (OSError, ValueError):
        return None
    if isinstance(data, dict) and data.get("app") == "jobcu":
        return data
    return None


def running_jobcu_version(port: int, timeout: float = 1.0) -> str | None:
    """Return the version of Jobcu answering on this port, or None."""
    data = running_jobcu(port, timeout)
    return str(data.get("version")) if data else None


def stop_running_jobcu(port: int, wait_seconds: float = 20.0) -> bool:
    """Ask an older Jobcu on this port to stop, and wait until the port is free."""
    request = urllib.request.Request(
        f"http://{HOST}:{port}/api/shutdown", method="POST", headers={"X-Jobcu": "1"}
    )
    try:
        with _local_opener.open(request, timeout=5):
            pass
    except OSError:
        return False
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if running_jobcu(port, timeout=0.5) is None and is_port_free(port):
            return True
        time.sleep(0.2)
    return False


def _say(text: str = "") -> None:
    print(text, flush=True)


def main() -> int:
    selftest = os.environ.get("JOBCU_SELFTEST") == "1"
    open_browser = not selftest and os.environ.get("JOBCU_NO_BROWSER") != "1"

    ensure_data_dir()
    setup_logging()

    running = None if selftest else running_jobcu(PREFERRED_PORT)
    if running and running.get("build") == build_id():
        _say("Jobcu is already running. Opening it in your browser.")
        if open_browser:
            webbrowser.open(url_for(PREFERRED_PORT))
        return 0
    if running:
        _say("An older version of Jobcu is still running. Replacing it with the new version...")
        if not stop_running_jobcu(PREFERRED_PORT):
            _say()
            _say("Jobcu couldn't close the older version by itself.")
            _say("Please close the other Jobcu window, then double-click Start Jobcu again.")
            return 1

    if not selftest and is_port_free(PREFERRED_PORT):
        port = PREFERRED_PORT
    else:
        port = find_free_port()

    server = uvicorn.Server(
        uvicorn.Config(
            create_app(),
            host=HOST,
            port=port,
            log_level="warning",
            access_log=False,
        )
    )
    outcome = {"ok": not selftest, "replaced": False}

    def replaced_by_newer_version() -> None:
        outcome["replaced"] = True
        server.should_exit = True

    server.config.app.state.request_shutdown = replaced_by_newer_version

    def after_start() -> None:
        deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
        while not server.started:
            if server.should_exit or time.monotonic() > deadline:
                server.should_exit = True
                return
            time.sleep(0.05)
        url = url_for(port)
        if selftest:
            outcome["ok"] = running_jobcu_version(port, timeout=10) == __version__
            _say("Self-test passed." if outcome["ok"] else "Self-test FAILED.")
            server.should_exit = True
            return
        _say()
        _say("  Jobcu is running.")
        _say()
        _say("  Your browser should open by itself. If it doesn't, open this address:")
        _say(f"      {url}")
        _say()
        _say("  Keep this window open while you use Jobcu.")
        _say("  To stop Jobcu, close this window.")
        _say()
        if open_browser:
            webbrowser.open(url)

    threading.Thread(target=after_start, daemon=True).start()
    _say(f"Starting Jobcu {__version__}...")
    try:
        server.run()
    except KeyboardInterrupt:
        pass
    if not server.started:
        _say("Jobcu couldn't start. Please close this window and try again.")
        return 1
    if outcome["replaced"]:
        _say()
        _say("  A newer version of Jobcu has taken over. You can close this window.")
    return 0 if outcome["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
