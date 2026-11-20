import logging
import os

from flask import Flask, jsonify, render_template, request


def create_app(config_object=None):
    # Heavy imports live here so that `app.parser` can be used without the web stack installed.
    from dotenv import load_dotenv

    from .auth import init_security
    from .extensions import db

    load_dotenv()
    if config_object is None:
        from config import Config as config_object  # imported late so .env is loaded first
    app = Flask(__name__)
    app.config.from_object(config_object)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY is not set. Copy .env.example to .env and set SECRET_KEY "
                           "(generate one with: python -c \"import secrets; print(secrets.token_hex(32))\").")
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        raise RuntimeError("No database configured. Set DB_PASSWORD (and optionally DB_USER, DB_HOST, DB_PORT, "
                           "DB_NAME) or DATABASE_URL in your .env file. "
                           "Or leave DB_PASSWORD empty to use a local SQLite file.")
    logging.basicConfig(level=logging.INFO)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    init_security(app)

    from .routes import api, auth, pages
    for module in (auth, pages, api):
        app.register_blueprint(module.bp)

    def wants_json():
        return request.path.startswith("/api/")

    @app.errorhandler(404)
    def not_found(_):
        return (jsonify(error="Not found."), 404) if wants_json() else (render_template("error.html", code=404,
                message="That page does not exist."), 404)

    @app.errorhandler(413)
    def too_large(_):
        msg = f"The upload is too large. Each file may be up to {app.config['MAX_FILE_MB']} MB."
        return (jsonify(error=msg), 413) if wants_json() else (render_template("error.html", code=413, message=msg), 413)

    @app.errorhandler(400)
    def bad_request(exc):
        return (jsonify(error="Bad request."), 400) if wants_json() else (render_template("error.html", code=400,
                message="The request could not be processed. Reload the page and try again."), 400)

    @app.errorhandler(405)
    def not_allowed(_):
        return jsonify(error="Method not allowed."), 405

    @app.errorhandler(500)
    def server_error(_):
        db.session.rollback()
        return (jsonify(error="Internal server error."), 500) if wants_json() else (render_template(
            "error.html", code=500, message="Something went wrong on our side."), 500)

    register_cli(app)
    return app


def register_cli(app):
    import click
    from .extensions import db

    @app.cli.command("init-db")
    def init_db():
        """Create all tables (and the admin user from ADMIN_USERNAME / ADMIN_PASSWORD if set)."""
        db.create_all()
        click.echo("Database tables created.")
        username, password = os.environ.get("ADMIN_USERNAME"), os.environ.get("ADMIN_PASSWORD")
        if username and password:
            _create_user(username, password)

    @app.cli.command("create-user")
    @click.argument("username")
    @click.password_option()
    def create_user(username, password):
        """Create (or reset the password of) an HR user."""
        _create_user(username, password)


def _create_user(username, password):
    import click

    from .extensions import db
    from .models import User
    if len(password) < 8:
        raise click.ClickException("Password must be at least 8 characters.")
    user = db.session.scalar(db.select(User).where(User.username == username))
    created = user is None
    user = user or User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo(f"User '{username}' {'created' if created else 'password updated'}.")
