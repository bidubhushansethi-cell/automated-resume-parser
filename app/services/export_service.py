"""CSV / Excel export of candidate data."""
import csv
import io
from datetime import datetime, timezone

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

COLUMNS = ["ID", "Full Name", "Email", "Phone", "Experience (years)", "Skills", "Education",
           "Experience", "Projects", "Certifications", "Resume File", "Added On"]


def _safe(value):
    """Neutralise spreadsheet formula injection (cells starting with = + - @)."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def _row(c):
    return [
        c.id, c.full_name, c.email or "", c.phone or "", c.total_experience_years,
        ", ".join(s.name for s in c.skills),
        "; ".join(" - ".join(x for x in (e.degree, e.institution, e.year) if x) for e in c.education),
        "; ".join(" - ".join(x for x in (e.title, e.company) if x) for e in c.experience),
        "; ".join(p.name for p in c.projects), "; ".join(x.name for x in c.certifications),
        c.resume.original_filename if c.resume else "",
        c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else "",
    ]


def stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def to_csv(candidates) -> bytes:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(COLUMNS)
    for c in candidates:
        writer.writerow([_safe(v) for v in _row(c)])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")  # BOM so Excel on Windows reads UTF-8


def to_xlsx(candidates) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Candidates"
    ws.append(COLUMNS)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F2A44")
    for c in candidates:
        ws.append([_safe(v) for v in _row(c)])
    for col, width in zip("ABCDEFGHIJKL", (6, 24, 30, 18, 12, 50, 50, 50, 36, 36, 28, 18)):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
