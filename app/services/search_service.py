"""Candidate search / filter / sort / pagination, shared by the list, search and export endpoints."""
from sqlalchemy import func, or_

from ..extensions import db
from ..models import Candidate, Education, Experience, Skill
from ..parser.skills_db import CATEGORIES

SORT_FIELDS = {
    "name": Candidate.full_name, "email": Candidate.email,
    "experience": Candidate.total_experience_years, "created": Candidate.created_at,
}


def _like(value):
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _num(value):
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def build_query(args):
    stmt = db.select(Candidate)
    g = lambda k: (args.get(k) or "").strip()
    if g("name"):
        stmt = stmt.where(Candidate.full_name.ilike(_like(g("name")), escape="\\"))
    if g("email"):
        stmt = stmt.where(Candidate.email.ilike(_like(g("email")), escape="\\"))
    for skill in [s.strip() for s in g("skill").split(",") if s.strip()][:10]:  # every listed skill must match
        stmt = stmt.where(Candidate.skills.any(Skill.name.ilike(_like(skill), escape="\\")))
    if g("category") in CATEGORIES:
        stmt = stmt.where(Candidate.skills.any(Skill.category == g("category")))
    if g("education"):
        p = _like(g("education"))
        stmt = stmt.where(Candidate.education.any(or_(Education.degree.ilike(p, escape="\\"),
                                                      Education.institution.ilike(p, escape="\\"))))
    lo, hi = _num(args.get("min_experience")), _num(args.get("max_experience"))
    if lo is not None:
        stmt = stmt.where(Candidate.total_experience_years >= lo)
    if hi is not None:
        stmt = stmt.where(Candidate.total_experience_years <= hi)
    if g("experience"):  # free-text match on job titles / companies
        p = _like(g("experience"))
        stmt = stmt.where(Candidate.experience.any(or_(Experience.title.ilike(p, escape="\\"),
                                                       Experience.company.ilike(p, escape="\\"))))
    if g("q"):
        p = _like(g("q"))
        stmt = stmt.where(or_(
            Candidate.full_name.ilike(p, escape="\\"), Candidate.email.ilike(p, escape="\\"),
            Candidate.phone.ilike(p, escape="\\"),
            Candidate.skills.any(Skill.name.ilike(p, escape="\\")),
            Candidate.education.any(or_(Education.degree.ilike(p, escape="\\"),
                                        Education.institution.ilike(p, escape="\\"))),
            Candidate.experience.any(or_(Experience.title.ilike(p, escape="\\"),
                                         Experience.company.ilike(p, escape="\\")))))
    column = SORT_FIELDS.get(g("sort"), Candidate.created_at)
    desc = g("order").lower() != "asc"
    stmt = stmt.order_by(column.desc() if desc else column.asc(), Candidate.id.desc())
    return stmt


def search(args, paginate=True):
    stmt = build_query(args)
    if not paginate:
        return db.session.execute(stmt).scalars().all()
    page = max(int(args.get("page", 1) or 1), 1) if str(args.get("page", 1)).isdigit() else 1
    per_page = int(args.get("per_page", 10)) if str(args.get("per_page", 10)).isdigit() else 10
    return db.paginate(stmt, page=page, per_page=min(max(per_page, 1), 100), error_out=False)
