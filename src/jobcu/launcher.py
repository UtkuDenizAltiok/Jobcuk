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


def running_jobcu_version(port: int, timeout: float = 1.0) -> str | None:
    """Return the version of Jobcu answering on this port, or None."""
    try:
        with _local_opener.open(f"http://{HOST}:{port}/api/health", timeout=timeout) as resp:
            data = json.load(resp)
    except (OSError, ValueError):
        return None
    if isinstance(data, dict) and data.get("app") == "jobcu":
        return str(data.get("version"))
    return None


def _say(text: str = "") -> None:
    print(text, flush=True)


def main() -> int:
    selftest = os.environ.get("JOBCU_SELFTEST") == "1"
    open_browser = not selftest and os.environ.get("JOBCU_NO_BROWSER") != "1"

    ensure_data_dir()

    if not selftest and running_jobcu_version(PREFERRED_PORT):
        _say("Jobcu is already running. Opening it in your browser.")
        if open_browser:
            webbrowser.open(url_for(PREFERRED_PORT))
        return 0

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
    outcome = {"ok": not selftest}

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
    return 0 if outcome["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
