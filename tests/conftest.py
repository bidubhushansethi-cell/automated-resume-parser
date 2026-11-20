import pytest

from app import create_app
from app.extensions import db
from app.models import User
from config import TestConfig


@pytest.fixture()
def app(tmp_path):
    class Cfg(TestConfig):
        UPLOAD_FOLDER = tmp_path / "uploads"

    app = create_app(Cfg)
    with app.app_context():
        db.create_all()
        user = User(username="hr")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def anon(app):
    return app.test_client()


@pytest.fixture()
def client(app):
    """A client that is already signed in and sends a valid CSRF header."""
    c = app.test_client()
    with c.session_transaction() as s:
        s["user_id"] = 1
        s["csrf_token"] = "test-token"
    c.environ_base["HTTP_X_CSRF_TOKEN"] = "test-token"
    return c
