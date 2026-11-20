"""Builds realistic sample resumes (PDF + DOCX) for tests. Content is synthetic test input only."""
from pathlib import Path

RESUME_ONE = """ARJUN MEHTA
Pune, Maharashtra | +91 98765 43210 | arjun.mehta@example.com
linkedin.com/in/arjunmehta | github.com/arjunmehta

PROFESSIONAL SUMMARY
Backend engineer with 4 years of experience building data platforms.

TECHNICAL SKILLS
Languages: Python, Java, C++, SQL, JavaScript
Frameworks: Django, Flask, FastAPI, React
Databases: PostgreSQL, MongoDB, Redis
Cloud & Tools: AWS, Docker, Kubernetes, Git, Jenkins, Jira
ML & Data: scikit-learn, TensorFlow, Pandas, NumPy, Tableau

WORK EXPERIENCE
Senior Software Engineer
Infosys Technologies Pvt Ltd, Pune
Jan 2021 - Present
• Designed REST APIs serving 2M requests per day using Flask and PostgreSQL.
• Migrated monolith services to Docker and Kubernetes on AWS.
Software Engineer | Tata Consultancy Services   Jul 2019 - Dec 2020
• Built ETL pipelines with Python and Pandas.
• Wrote unit tests with pytest.

EDUCATION
Bachelor of Technology in Computer Science
Savitribai Phule Pune University, Pune
2015 - 2019
CGPA: 8.7/10
Higher Secondary (12th), Delhi Public School, 2015, 92%

PROJECTS
Resume Screening System | Python, spaCy, Flask
• Built an NLP pipeline that ranks resumes against job descriptions.
• Deployed with Docker.
Sales Forecasting Dashboard
• Time-series model in Python with Tableau reporting.
Technologies: Python, Pandas, Tableau

CERTIFICATIONS
AWS Certified Solutions Architect - Associate, Amazon Web Services, 2022
Google Data Analytics Professional Certificate (2021)

HOBBIES
Chess, trekking
"""


def build_pdf(path: Path, text: str = RESUME_ONE):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for line in text.split("\n"):
        line = line.replace("•", "-")
        if y < 50:
            c.showPage()
            y = 800
        c.setFont("Helvetica-Bold" if line.isupper() and len(line) < 40 else "Helvetica", 10)
        c.drawString(40, y, line)
        y -= 14
    c.save()
    return path


def build_docx(path: Path, text: str = RESUME_ONE):
    from docx import Document
    doc = Document()
    for line in text.split("\n"):
        doc.add_paragraph(line)
    doc.save(str(path))
    return path


RESUME_TWO = """Priya Nair
priya_nair92@gmail.com  9876501234
Objective: seeking a role in data.
Education
Anna University
B.E. Electronics and Communication Engineering 2010-2014   First Class 7.9 CGPA
Experience
2014 - 2016  Test Engineer at Wipro Limited
- Manual and Selenium testing
Skills: Python, R, SQL, Excel, Power BI
"""
