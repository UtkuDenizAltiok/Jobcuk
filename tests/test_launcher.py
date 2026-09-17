import os
import socket
import subprocess
import sys
import threading
import time

import uvicorn
from fastapi.testclient import TestClient

from jobcu import launcher
from jobcu.app import create_app
from jobcu.build import build_id


def test_find_free_port_gives_a_usable_port():
    port = launcher.find_free_port()
    assert launcher.is_port_free(port)


def test_busy_port_is_detected():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((launcher.HOST, 0))
        sock.listen()
        assert not launcher.is_port_free(sock.getsockname()[1])


def test_no_jobcu_answers_on_an_unused_port():
    assert launcher.running_jobcu_version(launcher.find_free_port()) is None


def test_jobcu_starts_answers_and_stops():
    env = {**os.environ, "JOBCU_SELFTEST": "1"}
    result = subprocess.run(
        [sys.executable, "-m", "jobcu"],
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Self-test passed." in result.stdout


def test_health_tells_the_build_so_old_versions_can_be_recognised():
    client = TestClient(create_app(), base_url="http://127.0.0.1:8765")
    assert client.get("/api/health").json()["build"] == build_id()
    # Without a launcher there is nothing to stop.
    assert client.post("/api/shutdown", headers={"X-Jobcu": "1"}).status_code == 409


def test_a_running_jobcu_can_be_asked_to_stop():
    port = launcher.find_free_port()
    app = create_app()
    server = uvicorn.Server(uvicorn.Config(app, host=launcher.HOST, port=port, log_level="error"))
    app.state.request_shutdown = lambda: setattr(server, "should_exit", True)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 20
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert launcher.running_jobcu(port)
    assert launcher.stop_running_jobcu(port)
    thread.join(timeout=10)
    assert not thread.is_alive()
