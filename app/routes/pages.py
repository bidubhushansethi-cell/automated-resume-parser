from flask import Blueprint, abort, current_app, render_template

from ..auth import login_required
from ..extensions import db
from ..models import Candidate
from ..parser.skills_db import CATEGORIES

bp = Blueprint("pages", __name__)


@bp.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html", page="dashboard")


@bp.route("/upload")
@login_required
def upload():
    return render_template("upload.html", page="upload", max_mb=current_app.config["MAX_FILE_MB"],
                           max_files=current_app.config["MAX_FILES_PER_UPLOAD"])


@bp.route("/candidates")
@login_required
def candidates():
    return render_template("candidates.html", page="candidates", categories=CATEGORIES)


@bp.route("/candidates/<int:candidate_id>")
@login_required
def candidate(candidate_id):
    if db.session.get(Candidate, candidate_id) is None:
        abort(404)
    return render_template("candidate.html", page="candidate", candidate_id=candidate_id,
                           categories=CATEGORIES + ["Other"])
