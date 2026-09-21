"""Coffee Pie Integration Test Fixtures.

Spins up the full stack via docker compose, waits for readiness,
and tears down after tests. Each test module reuses the same stack
for speed — use 'docker compose restart <service>' if state isolation
is needed between tests.

Usage:
    cd tests/integration
    pip install -r requirements.txt
    pytest -v --timeout=120
"""

import os
import subprocess
import time
import pytest
import requests
import socket
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
COMPOSE_FILE = PROJECT_ROOT / "docker-compose.yml"
ENV_FILE = PROJECT_ROOT / ".env"

# Service endpoints (from docker-compose.yml)
ORCHESTRATOR_URL = "http://localhost:8000"
DC_AGENT_URL = "http://localhost:9090"
PROXMOX_MOCK_URL = "http://localhost:8001"
SUNSHINE_MOCK_HOST = "localhost"
SUNSHINE_MOCK_PORT = 47989
ACTOR_PORT = 43910
POSTGRES_PORT = 5432
REDIS_PORT = 6379


def _compose(*args, check=True):
    """Run docker compose command from project root."""
    cmd = [
        "docker", "compose",
        "-f", str(COMPOSE_FILE),
        "--env-file", str(ENV_FILE),
    ] + list(args)
    return subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, check=check)


def _wait_for_tcp(host, port, timeout=30):
    """Wait until a TCP port is accepting connections."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            time.sleep(1)
    return False


def _wait_for_http(url, expected_status=200, timeout=30):
    """Wait until an HTTP endpoint returns expected status."""
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=3)
            if r.status_code == expected_status:
                return True
        except requests.RequestException as e:
            last_error = e
        time.sleep(1)
    if last_error:
        print(f"  HTTP wait failed for {url}: {last_error}")
    return False


@pytest.fixture(scope="session")
def compose_up():
    """Start the full stack. Session-scoped — all tests share one stack."""
    print("\n[compose_up] Starting Coffee Pie stack...")

    # Ensure .env exists
    if not ENV_FILE.exists():
        subprocess.run(["cp", str(PROJECT_ROOT / ".env.example"), str(ENV_FILE)], check=True)

    # Build and start
    _compose("build", "--quiet", "postgres", "redis", "proxmox-mock", "sunshine-mock")
    _compose("up", "-d", "postgres", "redis", "proxmox-mock", "sunshine-mock")

    # Wait for core services
    services = [
        ("PostgreSQL", "localhost", POSTGRES_PORT, "tcp"),
        ("Redis", "localhost", REDIS_PORT, "tcp"),
        ("Proxmox Mock", PROXMOX_MOCK_URL + "/health", None, "http"),
        ("Sunshine Mock", "localhost", SUNSHINE_MOCK_PORT, "tcp"),
    ]

    for name, host_or_url, port, kind in services:
        print(f"  Waiting for {name}...")
        if kind == "tcp":
            ok = _wait_for_tcp(host_or_url, port)
        else:
            ok = _wait_for_http(host_or_url)
        if not ok:
            _compose("logs", "--tail=50")
            pytest.fail(f"{name} did not become ready in time")

    print("  All services ready.")
    yield

    # Teardown
    print("\n[compose_up] Stopping stack...")
    _compose("down", "-v", check=False)


@pytest.fixture(scope="session")
def orch_url(compose_up):
    """Orchestrator base URL."""
    return ORCHESTRATOR_URL


@pytest.fixture(scope="session")
def dc_agent_url(compose_up):
    """DC Agent base URL."""
    return DC_AGENT_URL


@pytest.fixture(scope="session")
def proxmox_mock_url(compose_up):
    """Proxmox mock base URL."""
    return PROXMOX_MOCK_URL


@pytest.fixture(scope="session")
def http_session():
    """Reusable requests session."""
    s = requests.Session()
    s.headers.update({"User-Agent": "CoffeePie-IntegrationTests/1.0"})
    yield s
    s.close()


@pytest.fixture(scope="session")
def api(http_session, orch_url):
    """Helper for orchestrator API calls."""

    class ApiHelper:
        def __init__(self, session, base_url):
            self.session = session
            self.base_url = base_url

        def get(self, path, **kwargs):
            return self.session.get(f"{self.base_url}{path}", timeout=10, **kwargs)

        def post(self, path, **kwargs):
            return self.session.post(f"{self.base_url}{path}", timeout=10, **kwargs)

        def put(self, path, **kwargs):
            return self.session.put(f"{self.base_url}{path}", timeout=10, **kwargs)

        def delete(self, path, **kwargs):
            return self.session.delete(f"{self.base_url}{path}", timeout=10, **kwargs)

    return ApiHelper(http_session, orch_url)
