import os
import socket
import subprocess
import sys

from jobcu import launcher


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
