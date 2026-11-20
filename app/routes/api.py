"""JSON REST API. Every endpoint requires an authenticated session."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Blueprint, Response, current_app, g, jsonify, request, send_from_directory
from sqlalchemy import func

from ..auth import login_required
from ..extensions import db
from ..models import Candidate, ResumeFile, Skill
from ..services import export_service, resume_service, search_service
from ..services.resume_service import UploadError

bp = Blueprint("api", __name__, url_prefix="/api")
bp.before_request(login_required(lambda: None))  # 401 JSON for anonymous API calls


def _result(candidate):
    return {"success": True, "candidate_id": candidate.id, "name": candidate.full_name,
            "email": candidate.email, "skills_found": len(candidate.skills),
            "warnings": getattr(candidate, "parse_warnings", [])}


# ---------------------------------------------------------------- uploads
@bp.post("/resumes/upload")
def upload_one():
    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify(error="No file was uploaded. Send a PDF or DOCX in the 'file' field."), 400
    try:
        candidate = resume_service.process_upload(file, g.user.id)
    except UploadError as exc:
        return jsonify(error=exc.message), exc.status
    return jsonify({**_result(candidate), "candidate": candidate.to_dict(detail=True)}), 201


@bp.post("/resumes/bulk-upload")
def upload_many():
    files = [f for f in request.files.getlist("files") if f and f.filename]
    limit = current_app.config["MAX_FILES_PER_UPLOAD"]
    if not files:
        return jsonify(error="No files were uploaded. Send PDF or DOCX files in the 'files' field."), 400
    if len(files) > limit:
        return jsonify(error=f"You can upload at most {limit} files at a time."), 413
    results = []
    for f in files:
        try:
            results.append({"filename": f.filename, **_result(resume_service.process_upload(f, g.user.id))})
        except UploadError as exc:
            results.append({"filename": f.filename, "success": False, "error": exc.message})
        except Exception:
            current_app.logger.exception("Unexpected error while processing %s", f.filename)
            results.append({"filename": f.filename, "success": False,
                            "error": "Unexpected error while processing this file."})
    ok = sum(r["success"] for r in results)
    return jsonify(results=results, uploaded=ok, failed=len(results) - ok), (200 if ok else 422)


# ---------------------------------------------------------------- candidates
@bp.get("/candidates")
@bp.get("/candidates/search")
def list_candidates():
    page = search_service.search(request.args)
    return jsonify(candidates=[c.to_dict() for c in page.items], total=page.total, page=page.page,
                   pages=page.pages, per_page=page.per_page)


@bp.get("/candidates/export")
def export_candidates():
    fmt = (request.args.get("format") or "csv").lower()
    if fmt not in ("csv", "xlsx"):
        return jsonify(error="format must be 'csv' or 'xlsx'."), 400
    rows = search_service.search(request.args, paginate=False)
    if fmt == "csv":
        body, mime = export_service.to_csv(rows), "text/csv"
    else:
        body = export_service.to_xlsx(rows)
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return Response(body, mimetype=mime, headers={
        "Content-Disposition": f'attachment; filename="candidates_{export_service.stamp()}.{fmt}"'})


def _get_or_404(candidate_id):
    return db.session.get(Candidate, candidate_id)


@bp.get("/candidates/<int:candidate_id>")
def get_candidate(candidate_id):
    c = _get_or_404(candidate_id)
    return (jsonify(c.to_dict(detail=True)), 200) if c else (jsonify(error="Candidate not found."), 404)


@bp.put("/candidates/<int:candidate_id>")
def update_candidate(candidate_id):
    c = _get_or_404(candidate_id)
    if c is None:
        return jsonify(error="Candidate not found."), 404
    cleaned, errors = resume_service.validate_candidate_payload(request.get_json(silent=True))
    if errors:
        return jsonify(error="Please correct the highlighted fields.", fields=errors), 422
    if cleaned["email"]:
        dup = db.session.scalar(db.select(Candidate.id).where(func.lower(Candidate.email) == cleaned["email"],
                                                               Candidate.id != c.id))
        if dup:
            return jsonify(error="Another candidate already uses this email.", fields={"email": "Already in use."}), 409
    resume_service.update_candidate(c, cleaned)
    db.session.commit()
    return jsonify(c.to_dict(detail=True))


@bp.delete("/candidates/<int:candidate_id>")
def delete_candidate(candidate_id):
    c = _get_or_404(candidate_id)
    if c is None:
        return jsonify(error="Candidate not found."), 404
    resume_service.delete_candidate(c)
    return jsonify(message="Candidate deleted."), 200


# ---------------------------------------------------------------- files
@bp.get("/resumes/<int:resume_id>/download")
def download_resume(resume_id):
    r = db.session.get(ResumeFile, resume_id)
    if r is None:
        return jsonify(error="Resume not found."), 404
    path = Path(current_app.config["UPLOAD_FOLDER"]) / r.stored_filename  # server-generated name only
    if not path.is_file():
        return jsonify(error="The resume file is missing from storage."), 404
    return send_from_directory(path.parent, path.name, as_attachment=True, download_name=r.original_filename)


# ---------------------------------------------------------------- dashboard
@bp.get("/dashboard/stats")
def dashboard_stats():
    s = db.session
    total_candidates = s.scalar(db.select(func.count(Candidate.id)))
    by_category = s.execute(db.select(Skill.category, func.count(func.distinct(Skill.candidate_id)))
                            .group_by(Skill.category).order_by(func.count(func.distinct(Skill.candidate_id)).desc())).all()
    top_skills = s.execute(db.select(Skill.name, func.count(Skill.id).label("n")).group_by(Skill.name)
                           .order_by(func.count(Skill.id).desc(), Skill.name).limit(10)).all()
    years = [y or 0 for y in s.scalars(db.select(Candidate.total_experience_years)).all()]
    buckets = Counter()
    for y in years:
        buckets["0-1 yrs" if y < 1 else "1-3 yrs" if y < 3 else "3-5 yrs" if y < 5 else "5-10 yrs" if y < 10 else "10+ yrs"] += 1
    since = datetime.now(timezone.utc) - timedelta(days=6)
    utc = lambda d: d.astimezone(timezone.utc) if d.tzinfo else d
    days = Counter(utc(d).strftime("%a %d %b") for d in s.scalars(
        db.select(ResumeFile.uploaded_at).where(ResumeFile.uploaded_at >= since.replace(hour=0, minute=0, second=0))).all())
    today = datetime.now(timezone.utc)
    last7 = [(today - timedelta(days=i)).strftime("%a %d %b") for i in range(6, -1, -1)]
    recent = s.execute(db.select(ResumeFile, Candidate).join(Candidate, Candidate.id == ResumeFile.candidate_id)
                       .order_by(ResumeFile.uploaded_at.desc()).limit(6)).all()
    return jsonify(
        total_resumes=s.scalar(db.select(func.count(ResumeFile.id))),
        total_candidates=total_candidates,
        total_skills=s.scalar(db.select(func.count(func.distinct(func.lower(Skill.name))))),
        average_experience=round(sum(years) / len(years), 1) if years else 0,
        skills_by_category=[{"category": c, "candidates": n} for c, n in by_category],
        top_skills=[{"name": n, "count": c} for n, c in top_skills],
        experience_distribution=[{"label": k, "count": buckets.get(k, 0)}
                                 for k in ("0-1 yrs", "1-3 yrs", "3-5 yrs", "5-10 yrs", "10+ yrs")],
        uploads_last_7_days=[{"label": d, "count": days.get(d, 0)} for d in last7],
        recent_uploads=[{"candidate_id": c.id, "name": c.full_name, "filename": r.original_filename,
                         "file_type": r.file_type, "uploaded_at": r.uploaded_at.isoformat(),
                         "skill_count": len(c.skills)} for r, c in recent])
