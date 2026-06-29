"""
MECOS Startup Script
Starts SearXNG Docker container, waits for it to be healthy, then launches MECOS.
Usage: python run_mecos.py
"""
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

DOCKER_COMPOSE = "docker-compose-searxng.yml"
DOCKER_PATH = r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"
SEARXNG_URL = "http://localhost:8888/search?q=test&format=json"


def start_searxng():
    print("[MECOS] Starting SearXNG Docker container...")
    result = subprocess.run(
        [DOCKER_PATH, "compose", "-f", DOCKER_COMPOSE, "up", "-d"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"[MECOS] Failed to start SearXNG: {result.stderr}")
        sys.exit(1)
    print("[MECOS] SearXNG container started.")


def wait_for_searxng(timeout=60):
    print(f"[MECOS] Waiting for SearXNG at {SEARXNG_URL} ...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(SEARXNG_URL, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    print("[MECOS] SearXNG is ready.")
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(3)
    print("[MECOS] SearXNG did not become ready in time.")
    return False


def run_mecos():
    print("[MECOS] Starting MECOS engine...")
    env = dict(os.environ)
    env["MECOS_ENABLE_ASSISTANT"] = "true"
    env["MECOS_ENABLE_OUTREACH"] = "false"
    result = subprocess.run(
        [sys.executable, "main.py"],
        env=env,
    )
    return result.returncode


def main():
    start_searxng()
    if not wait_for_searxng():
        sys.exit(1)
    sys.exit(run_mecos())


if __name__ == "__main__":
    main()
