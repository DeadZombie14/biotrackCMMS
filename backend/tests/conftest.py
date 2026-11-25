import pytest
from sqlalchemy import text
from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.seed import run_seed


@pytest.fixture(scope="function")
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.session.execute(text("DROP TRIGGER IF EXISTS trg_audit_events_no_update"))
        db.session.execute(text("DROP TRIGGER IF EXISTS trg_audit_events_no_delete"))
        db.session.commit()
        db.drop_all()
        db.create_all()
        run_seed(reset=False)
        yield app
        db.session.remove()


@pytest.fixture()
def client(app):
    return app.test_client()


def auth_headers(client, email: str, password: str = "BioTrack2026!") -> dict:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.get_json()
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
