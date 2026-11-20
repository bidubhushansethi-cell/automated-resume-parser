"""Session-based authentication, CSRF protection and security headers."""
import hmac
import secrets
from functools import wraps

from flask import abort, g, jsonify, redirect, request, session, url_for

from .extensions import db
from .models import User


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def init_security(app):
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def load_user_and_check_csrf():
        if request.endpoint == "static":
            return
        g.user = db.session.get(User, session["user_id"]) if session.get("user_id") else None
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
            if not sent or not hmac.compare_digest(sent, session.get("csrf_token", "")):
                if request.path.startswith("/api/"):
                    return jsonify(error="Invalid or missing CSRF token. Reload the page and try again."), 400
                abort(400)

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        if not request.path.startswith("/static/"):
            resp.headers["Cache-Control"] = "no-store"  # pages and API contain personal data
        return resp


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            if request.path.startswith("/api/"):
                return jsonify(error="Authentication required."), 401
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)
    return wrapped
