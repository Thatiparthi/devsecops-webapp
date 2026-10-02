import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.app import app


def test_home_route():
    client = app.test_client()
    response = client.get("/")

    assert response.status_code == 200
    assert b"Hello from DevSecOps Kubernetes Application!" in response.data


def test_health_route():
    client = app.test_client()
    response = client.get("/health")

    assert response.status_code == 200
    assert response.data == b"UP"
