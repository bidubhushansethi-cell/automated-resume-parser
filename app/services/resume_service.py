"""Upload validation, storage and persistence of parsed resumes."""
import re
import uuid
from pathlib import Path

from flask import current_app
from sqlalchemy import func
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import (Candidate, Certification, Education, Experience, Project, ResumeFile,
                      Skill)
from ..parser import ResumeParseError, parse_resume
from ..parser.skills_db import CATEGORIES, categorize

EMAIL_VALID = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


class UploadError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status


def _signature_ok(ext, data):
    if ext == ".pdf":
        return data[:5] == b"%PDF-"
    return data[:4] == b"PK\x03\x04"  # DOCX is a zip container


def _trim(value, length):
    return value.strip()[:length] if isinstance(value, str) and value.strip() else None


def _apply_parsed(candidate, data):
    """Replace all child rows of a candidate with the given (already validated) data."""
    candidate.education = [Education(degree=_trim(e.get("degree"), 250), institution=_trim(e.get("institution"), 250),
                                     year=_trim(e.get("year"), 40), grade=_trim(e.get("grade"), 40))
                           for e in data.get("education", [])]
    seen, skills = set(), []
    for s in data.get("skills", []):
        name = _trim(s.get("name"), 100)
        if name and name.lower() not in seen:
            seen.add(name.lower())
            cat = s.get("category")
            if cat not in CATEGORIES and cat != "Other":
                cat = categorize(name)
            skills.append(Skill(name=name, category=cat))
    candidate.skills = skills
    candidate.experience = [Experience(title=_trim(e.get("title"), 250), company=_trim(e.get("company"), 250),
                                       start_date=_trim(e.get("start_date"), 40), end_date=_trim(e.get("end_date"), 40),
                                       description=_trim(e.get("description"), 10000))
                            for e in data.get("experience", [])]
    candidate.projects = [Project(name=_trim(p.get("name"), 250) or "Untitled project",
                                  description=_trim(p.get("description"), 10000),
                                  technologies=_trim(p.get("technologies"), 300))
                          for p in data.get("projects", [])]
    candidate.certifications = [Certification(name=_trim(c.get("name"), 250) or "Untitled", issuer=_trim(c.get("issuer"), 250),
                                              year=_trim(c.get("year"), 10))
                                for c in data.get("certifications", [])]


def validate_candidate_payload(payload):
    """Returns (cleaned_dict, errors). Used by PUT /api/candidates/<id>."""
    errors = {}
    if not isinstance(payload, dict):
        return None, {"body": "A JSON object is required."}
    name = (payload.get("full_name") or "").strip()
    if not name:
        errors["full_name"] = "Full name is required."
    elif len(name) > 200:
        errors["full_name"] = "Full name must be 200 characters or fewer."
    email = (payload.get("email") or "").strip().lower() or None
    if email and (len(email) > 254 or not EMAIL_VALID.match(email)):
        errors["email"] = "Enter a valid email address."
    phone = (payload.get("phone") or "").strip() or None
    if phone and (len(phone) > 40 or not re.fullmatch(r"[+\d\s().\-]{7,40}", phone)):
        errors["phone"] = "Enter a valid phone number."
    years = payload.get("total_experience_years", 0)
    try:
        years = float(years or 0)
        if not 0 <= years <= 60:
            raise ValueError
    except (TypeError, ValueError):
        errors["total_experience_years"] = "Experience must be a number between 0 and 60."
        years = 0
    cleaned = {"full_name": name, "email": email, "phone": phone, "total_experience_years": round(years, 1)}
    for key in ("education", "skills", "experience", "projects", "certifications"):
        items = payload.get(key, [])
        if not isinstance(items, list) or any(not isinstance(i, dict) for i in items) or len(items) > 200:
            errors[key] = "Must be a list of objects."
        else:
            cleaned[key] = items
    return cleaned, errors


def update_candidate(candidate, cleaned):
    candidate.full_name, candidate.email = cleaned["full_name"], cleaned["email"]
    candidate.phone, candidate.total_experience_years = cleaned["phone"], cleaned["total_experience_years"]
    _apply_parsed(candidate, cleaned)


def process_upload(file_storage, user_id):
    """Validates, parses and stores one uploaded resume. Returns the new Candidate."""
    cfg = current_app.config
    original = secure_filename(file_storage.filename or "")
    if not original:
        raise UploadError("The file has no usable name.", 400)
    ext = Path(original).suffix.lower()
    if ext not in cfg["ALLOWED_EXTENSIONS"]:
        raise UploadError("Unsupported file type. Upload a PDF or DOCX file.", 415)
    data = file_storage.read(cfg["MAX_FILE_MB"] * 1024 * 1024 + 1)
    if not data:
        raise UploadError("The file is empty.", 400)
    if len(data) > cfg["MAX_FILE_MB"] * 1024 * 1024:
        raise UploadError(f"The file is larger than the {cfg['MAX_FILE_MB']} MB limit.", 413)
    if not _signature_ok(ext, data):
        raise UploadError(f"The file content does not match a valid {ext[1:].upper()} document.", 415)

    folder = Path(cfg["UPLOAD_FOLDER"])
    folder.mkdir(parents=True, exist_ok=True)
    stored = uuid.uuid4().hex + ext
    path = folder / stored
    path.write_bytes(data)
    try:
        try:
            parsed = parse_resume(path)
        except ResumeParseError as exc:
            raise UploadError(str(exc), 422) from exc
        email = parsed["email"]
        if email and db.session.scalar(db.select(func.count(Candidate.id)).where(func.lower(Candidate.email) == email)):
            raise UploadError(f"A candidate with the email {email} already exists.", 409)
        candidate = Candidate(full_name=parsed["full_name"] or Path(original).stem.replace("_", " ").title(),
                              email=email, phone=parsed["phone"],
                              total_experience_years=parsed["total_experience_years"], uploaded_by=user_id)
        _apply_parsed(candidate, parsed)
        candidate.resume = ResumeFile(original_filename=original, stored_filename=stored, file_type=ext[1:],
                                      file_size=len(data), raw_text=parsed["raw_text"])
        db.session.add(candidate)
        db.session.commit()
    except Exception:
        db.session.rollback()
        path.unlink(missing_ok=True)
        raise
    candidate.parse_warnings = parsed["warnings"]
    return candidate


def delete_candidate(candidate):
    stored = candidate.resume.stored_filename if candidate.resume else None
    db.session.delete(candidate)
    db.session.commit()
    if stored:
        (Path(current_app.config["UPLOAD_FOLDER"]) / stored).unlink(missing_ok=True)
