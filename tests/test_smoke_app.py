import subprocess
import sys
import time

import httpx


def test_app_starts_and_health_endpoint_responds():
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "--app-dir",
            "src",
            "betano_analyzer.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                response = httpx.get("http://127.0.0.1:8765/health", timeout=1.0)
                if response.status_code == 200:
                    assert response.json() == {
                        "status": "ok",
                        "service": "analysis-betstotal",
                    }
                    return
            except httpx.HTTPError:
                time.sleep(0.2)
        raise AssertionError("ANALISYS BETSTOTAL no inició a tiempo")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
