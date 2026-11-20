from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


_CHILD = dict(cascade="all, delete-orphan", lazy="selectin", passive_deletes=True)


class Candidate(db.Model):
    __tablename__ = "candidates"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False, index=True)
    email = db.Column(db.String(254), index=True)
    phone = db.Column(db.String(40))
    total_experience_years = db.Column(db.Float, default=0.0, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))

    education = db.relationship("Education", order_by="Education.id", **_CHILD)
    skills = db.relationship("Skill", order_by="Skill.id", **_CHILD)
    experience = db.relationship("Experience", order_by="Experience.id", **_CHILD)
    projects = db.relationship("Project", order_by="Project.id", **_CHILD)
    certifications = db.relationship("Certification", order_by="Certification.id", **_CHILD)
    resume = db.relationship("ResumeFile", uselist=False, **_CHILD)

    def to_dict(self, detail=False):
        edu = self.education[0] if self.education else None
        data = {
            "id": self.id, "full_name": self.full_name, "email": self.email, "phone": self.phone,
            "total_experience_years": self.total_experience_years,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resume_id": self.resume.id if self.resume else None,
            "resume_filename": self.resume.original_filename if self.resume else None,
            "skills": [s.to_dict() for s in self.skills] if detail else [s.to_dict() for s in self.skills[:8]],
            "skill_count": len(self.skills),
            "top_education": (f"{edu.degree or ''} {('· ' + edu.institution) if edu.institution else ''}".strip()
                              if edu else None),
        }
        if detail:
            data.update({
                "updated_at": self.updated_at.isoformat() if self.updated_at else None,
                "education": [e.to_dict() for e in self.education],
                "experience": [e.to_dict() for e in self.experience],
                "projects": [p.to_dict() for p in self.projects],
                "certifications": [c.to_dict() for c in self.certifications],
                "raw_text": self.resume.raw_text if self.resume else None,
                "resume": self.resume.to_dict() if self.resume else None,
            })
        return data


def _child_columns():
    return db.Column(db.Integer, primary_key=True), db.Column(
        db.Integer, db.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)


class Education(db.Model):
    __tablename__ = "education"
    id, candidate_id = _child_columns()
    degree = db.Column(db.String(250))
    institution = db.Column(db.String(250), index=True)
    year = db.Column(db.String(40))
    grade = db.Column(db.String(40))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    def to_dict(self):
        return {"degree": self.degree, "institution": self.institution, "year": self.year, "grade": self.grade}


class Skill(db.Model):
    __tablename__ = "skills"
    id, candidate_id = _child_columns()
    name = db.Column(db.String(100), nullable=False, index=True)
    category = db.Column(db.String(60), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    def to_dict(self):
        return {"name": self.name, "category": self.category}


class Experience(db.Model):
    __tablename__ = "experience"
    id, candidate_id = _child_columns()
    title = db.Column(db.String(250), index=True)
    company = db.Column(db.String(250), index=True)
    start_date = db.Column(db.String(40))
    end_date = db.Column(db.String(40))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    def to_dict(self):
        return {"title": self.title, "company": self.company, "start_date": self.start_date,
                "end_date": self.end_date, "description": self.description}


class Project(db.Model):
    __tablename__ = "projects"
    id, candidate_id = _child_columns()
    name = db.Column(db.String(250), nullable=False)
    description = db.Column(db.Text)
    technologies = db.Column(db.String(300))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    def to_dict(self):
        return {"name": self.name, "description": self.description, "technologies": self.technologies}


class Certification(db.Model):
    __tablename__ = "certifications"
    id, candidate_id = _child_columns()
    name = db.Column(db.String(250), nullable=False)
    issuer = db.Column(db.String(250))
    year = db.Column(db.String(10))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    def to_dict(self):
        return {"name": self.name, "issuer": self.issuer, "year": self.year}


class ResumeFile(db.Model):
    __tablename__ = "resume_files"
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey("candidates.id", ondelete="CASCADE"),
                             nullable=False, unique=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(64), nullable=False, unique=True)
    file_type = db.Column(db.String(10), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    raw_text = db.Column(db.Text)
    uploaded_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    def to_dict(self):
        return {"id": self.id, "original_filename": self.original_filename, "file_type": self.file_type,
                "file_size": self.file_size, "uploaded_at": self.uploaded_at.isoformat()}
