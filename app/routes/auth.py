import time
from urllib.parse import urlparse

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from ..auth import csrf_token
from ..extensions import db
from ..models import User

bp = Blueprint("auth", __name__)
_FAILS = {}  # (ip, username) -> timestamps of recent failed logins
MAX_FAILS, WINDOW = 5, 300


def _recent_fails(key):
    now = time.time()
    _FAILS[key] = [t for t in _FAILS.get(key, []) if now - t < WINDOW]
    return len(_FAILS[key])


def _safe_next(target):
    """Only allow redirects to local paths."""
    if target and target.startswith("/") and not target.startswith("//") and not urlparse(target).netloc:
        return target
    return url_for("pages.dashboard")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        key = (request.remote_addr, username.lower())
        if _recent_fails(key) >= MAX_FAILS:
            flash("Too many failed attempts. Wait a few minutes and try again.", "warning")
            return render_template("login.html"), 429
        user = db.session.scalar(db.select(User).where(User.username == username))
        if user and user.check_password(request.form.get("password") or ""):
            _FAILS.pop(key, None)
            session.clear()
            session["user_id"] = user.id
            session.permanent = True
            csrf_token()
            return redirect(_safe_next(request.args.get("next")))
        _FAILS.setdefault(key, []).append(time.time())
        flash("Incorrect username or password.", "danger")
    elif g.user:
        return redirect(url_for("pages.dashboard"))
    return render_template("login.html"), (401 if request.method == "POST" else 200)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
