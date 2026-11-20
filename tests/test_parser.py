import pytest

from app.parser import ResumeParseError, parse_resume, parse_text
from app.parser.resume_parser import extract_email, extract_phone
from app.parser.skills_db import CATEGORIES, categorize, extract_skills
from tests.sample_resumes import RESUME_ONE, RESUME_TWO, build_docx, build_pdf


def _check_resume_one(r):
    assert r["full_name"] == "Arjun Mehta"
    assert r["email"] == "arjun.mehta@example.com"
    assert r["phone"] == "+91 98765 43210"
    names = {s["name"] for s in r["skills"]}
    assert {"Python", "Flask", "PostgreSQL", "AWS", "Docker", "TensorFlow", "Pandas"} <= names
    assert r["education"][0]["degree"].startswith("Bachelor of Technology")
    assert r["education"][0]["institution"] == "Savitribai Phule Pune University"
    assert r["education"][0]["grade"] == "8.7/10"
    assert [e["title"] for e in r["experience"]] == ["Senior Software Engineer", "Software Engineer"]
    assert r["experience"][0]["company"] == "Infosys Technologies Pvt Ltd"
    assert r["experience"][1]["company"] == "Tata Consultancy Services"
    assert [p["name"] for p in r["projects"]] == ["Resume Screening System", "Sales Forecasting Dashboard"]
    assert len(r["certifications"]) == 2
    assert r["total_experience_years"] > 5


def test_pdf_extraction(tmp_path):
    _check_resume_one(parse_resume(build_pdf(tmp_path / "r.pdf")))


def test_docx_extraction(tmp_path):
    _check_resume_one(parse_resume(build_docx(tmp_path / "r.docx")))


def test_second_layout_without_bullets_or_headline_caps():
    r = parse_text(RESUME_TWO)
    assert r["full_name"] == "Priya Nair"
    assert r["email"] == "priya_nair92@gmail.com" and r["phone"] == "9876501234"
    assert r["education"][0]["institution"] == "Anna University"
    assert r["education"][0]["grade"] == "7.9"
    assert r["experience"][0]["company"] == "Wipro Limited"
    assert r["total_experience_years"] == 2.0


@pytest.mark.parametrize("text,expected", [
    ("Call +91 98765-43210 now", "+91 98765-43210"),
    ("Phone: (415) 555-2671", "(415) 555-2671"),
    ("+1 415 555 2671", "+1 415 555 2671"),
    ("Worked 2018 - 2022 and 2019 2020 2021", None),
    ("Roll no 12345", None),
])
def test_phone_extraction(text, expected):
    assert extract_phone(text) == expected


def test_email_extraction():
    assert extract_email("Reach me: John.Doe+jobs@Mail.Example.co.in.") == "john.doe+jobs@mail.example.co.in"
    assert extract_email("no email here") is None


def test_skill_categorization():
    by_name = {s["name"]: s["category"] for s in extract_skills(
        "Python, Django, MySQL, React, TensorFlow, Pandas, AWS, Git, HTML, Node.js")}
    assert by_name["Python"] == "Programming Languages"
    assert by_name["MySQL"] == "Database Technologies"
    assert by_name["Django"] == "Frameworks"
    assert by_name["TensorFlow"] == "Machine Learning"
    assert by_name["Pandas"] == "Data Science"
    assert by_name["AWS"] == "Cloud Computing"
    assert by_name["Git"] == "Tools and Platforms"
    assert by_name["HTML"] == "Web Development"
    assert set(by_name.values()) <= set(CATEGORIES)
    assert categorize("Underwater Basket Weaving") == "Other"


def test_ambiguous_skills_need_skills_section():
    assert "R" not in {s["name"] for s in extract_skills("R and D team, Go to market, C level")}
    assert {"R", "Go", "C"} <= {s["name"] for s in extract_skills("x", "Python, R, Go, C")}
    assert "Java" not in {s["name"] for s in extract_skills("I know JavaScript only")}


def test_scanned_pdf_gives_clear_error(tmp_path):
    from reportlab.pdfgen import canvas
    path = tmp_path / "blank.pdf"
    c = canvas.Canvas(str(path))
    c.showPage()
    c.save()
    with pytest.raises(ResumeParseError, match="No readable text"):
        parse_resume(path)


def test_corrupt_pdf_gives_clear_error(tmp_path):
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"%PDF-1.4 this is not really a pdf")
    with pytest.raises(ResumeParseError):
        parse_resume(path)
