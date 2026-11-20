"""Rule-based + spaCy resume parser.

parse_resume(path) -> dict with: full_name, email, phone, skills, education, experience,
projects, certifications, total_experience_years, raw_text, warnings.
"""
import re
from datetime import date
from pathlib import Path

from . import nlp
from .skills_db import extract_skills
from .text_extractor import ExtractionError, extract_text


class ResumeParseError(Exception):
    """Raised when a resume cannot be parsed; the message is safe to show to users."""


# --------------------------------------------------------------------------- sections
SECTION_HEADINGS = {
    "skills": ["skills", "technical skills", "key skills", "core competencies", "technologies",
               "skill set", "tech stack", "technical expertise", "areas of expertise",
               "technical proficiency", "it skills", "programming skills"],
    "education": ["education", "academic qualifications", "educational qualifications", "academics",
                  "academic background", "qualifications", "education and training",
                  "educational background", "academic details"],
    "experience": ["experience", "work experience", "professional experience", "employment history",
                   "work history", "internships", "internship experience", "career history",
                   "employment", "relevant experience", "professional background",
                   "internship"],
    "projects": ["projects", "academic projects", "personal projects", "key projects",
                 "project experience", "technical projects", "project work", "major projects"],
    "certifications": ["certifications", "certificates", "licenses and certifications", "courses",
                       "certifications and courses", "training and certifications",
                       "professional certifications", "certification", "courses and certifications",
                       "online courses"],
    "summary": ["summary", "professional summary", "profile", "objective", "career objective",
                "about me", "profile summary", "career summary"],
    "other": ["hobbies", "interests", "languages", "references", "declaration", "achievements",
              "awards", "personal details", "personal information", "extracurricular activities",
              "volunteering", "publications", "activities", "strengths", "awards and achievements",
              "hobbies and interests", "contact", "links", "co-curricular activities"],
}
HEADING_LOOKUP = {h: sec for sec, hs in SECTION_HEADINGS.items() for h in hs}
INLINE_SKILLS = re.compile(r"^(?:technical skills|skills|key skills|technologies|tech stack|"
                           r"skill set)\s*[:\-]\s*(.+)$", re.I)
BULLET = re.compile(r"^\s*(?:•|-|–|—|\*|\d+[.)])\s+")


def _norm_heading(line: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z]+", " ", line.lower().replace("&", " and "))).strip()


def split_sections(text: str):
    """Returns (header_lines, {section: [lines]})."""
    header, sections, current = [], {}, None
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            if current:
                sections[current].append("")
            continue
        if len(stripped) <= 45 and not BULLET.match(stripped):
            key = HEADING_LOOKUP.get(_norm_heading(stripped))
            if key:
                current = key
                sections.setdefault(key, [])
                continue
        m = INLINE_SKILLS.match(stripped)
        if m:
            current = "skills"
            sections.setdefault("skills", []).append(m.group(1))
            continue
        (sections[current] if current else header).append(stripped)
    return header, sections


def _lines(section_lines):
    return [l for l in section_lines if l.strip()]


# --------------------------------------------------------------------------- contact
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
PHONE_CANDIDATE = re.compile(r"(?<![\w@])(\+?\(?\d[\d\s().\-]{8,18}\d)(?![\w@])")
YEAR_ONLY = re.compile(r"^(?:19|20)\d{2}$")


def extract_email(text: str):
    m = EMAIL_RE.search(text)
    return m.group(0).lower().rstrip(".") if m else None


def extract_phone(text: str):
    for m in PHONE_CANDIDATE.finditer(text):
        raw = m.group(1).strip()
        digits = re.sub(r"\D", "", raw)
        if not 10 <= len(digits) <= 13:
            continue
        groups = re.findall(r"\d+", raw)
        if all(YEAR_ONLY.match(g) for g in groups):  # e.g. "2019 2020 2021"
            continue
        if re.fullmatch(r"(?:19|20)\d{2}\s*[-–]\s*(?:19|20)\d{2}", raw):
            continue
        return re.sub(r"\s+", " ", raw)
    return None


NAME_STOP = {"resume", "curriculum", "vitae", "cv", "engineer", "developer", "manager", "analyst",
             "student", "intern", "designer", "scientist", "consultant", "address", "email", "phone",
             "mobile", "contact", "profile", "summary", "objective", "education", "linkedin", "github",
             "portfolio", "fresher", "experienced", "software", "full", "stack", "senior", "junior",
             "lead", "architect", "specialist", "executive", "administrator", "page", "skills"}


def extract_name(header_lines, text, email):
    for line in header_lines[:10]:
        if "@" in line or re.search(r"\d{3,}", line) or re.search(r"https?://|www\.|linkedin|github", line, re.I):
            continue
        cleaned = re.sub(r"[|•,]+", " ", line).strip()
        words = cleaned.split()
        if not 2 <= len(words) <= 4 or len(cleaned) > 40:
            continue
        if any(w.lower().strip(".") in NAME_STOP for w in words):
            continue
        if all(re.fullmatch(r"[A-Za-z][A-Za-z.'\-]*", w) for w in words):
            return " ".join(w.capitalize() if w.isupper() or w.islower() else w for w in words)
    for ent in nlp.entities("\n".join(header_lines[:12]) or text[:500], "PERSON"):
        parts = ent.split()
        if 2 <= len(parts) <= 4 and all(re.fullmatch(r"[A-Za-z.'\-]+", p) for p in parts):
            return " ".join(p.capitalize() if p.isupper() else p for p in parts)
    if email:
        local = re.split(r"[0-9]", email.split("@")[0])[0]
        parts = [p for p in re.split(r"[._\-]+", local) if len(p) > 1]
        if parts:
            return " ".join(p.capitalize() for p in parts[:3])
    return None


# --------------------------------------------------------------------------- dates
MONTH = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|"
         r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)")
DATE = rf"(?:{MONTH}\.?,?\s*(?:19|20)\d{{2}}|\d{{1,2}}[/.\-](?:19|20)\d{{2}}|(?:19|20)\d{{2}})"
PRESENT = r"(?:Present|Current|Now|Till\s+date|To\s+date|Ongoing|Today)"
RANGE_RE = re.compile(rf"({DATE})\s*(?:-|–|—|to|until|till)\s*({DATE}|{PRESENT})", re.I)
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _to_ym(token: str):
    if re.fullmatch(PRESENT, token.strip(), re.I):
        t = date.today()
        return t.year, t.month
    year = int(re.search(r"(?:19|20)\d{2}", token).group(0))
    m = re.match(r"\s*([A-Za-z]{3})", token)
    if m and m.group(1).lower() in MONTHS:
        return year, MONTHS[m.group(1).lower()]
    m = re.match(r"\s*(\d{1,2})[/.\-]", token)
    if m and 1 <= int(m.group(1)) <= 12:
        return year, int(m.group(1))
    return year, 1


def _months(ym):
    return ym[0] * 12 + ym[1]


def total_years(ranges):
    spans = sorted((_months(_to_ym(a)), _months(_to_ym(b))) for a, b in ranges)
    spans = [(s, e) for s, e in spans if e >= s and e - s < 600]
    merged = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return round(sum(e - s for s, e in merged) / 12, 1)


# --------------------------------------------------------------------------- education
SHORT_DEGREE = re.compile(
    r"(?<![A-Za-z])(?:B\.?\s?Tech|M\.?\s?Tech|B\.?\s?Sc|M\.?\s?Sc|B\.?\s?Com|M\.?\s?Com|B\.?\s?Arch|"
    r"M\.?\s?Arch|Ph\.?\s?D|BBA|MBA|BCA|MCA|B\.?\s?E|M\.?\s?E|B\.?\s?A|M\.?\s?A|B\.?\s?S|M\.?\s?S|"
    r"BS|MS|BA|MA|BE|ME|HSC|SSC|CBSE|ICSE)(?![A-Za-z])")
LONG_DEGREE = re.compile(
    r"(?<![A-Za-z])(?:bachelor(?:'s|s)?(?:\s+of\s+[A-Za-z]+)?|master(?:'s|s)?(?:\s+of\s+[A-Za-z]+)?|"
    r"doctorate|diploma|associate degree|higher secondary|senior secondary|secondary school|"
    r"(?:10|12)th|class\s+(?:x|xii|10|12)|intermediate|high school)(?![A-Za-z])", re.I)
INSTITUTION_RE = re.compile(
    r"\b(?:University|College|Institute|Institution|School|Academy|Polytechnic|Vidyalaya|Vidyapeeth|"
    r"Mahavidyalaya|IIT|NIT|IIIT|BITS|IIM|Campus)\b", re.I)
GRADE_RE = re.compile(r"(?:CGPA|GPA|CPI|SGPA)\s*[:\-]?\s*(\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?)|"
                      r"(\d{2}(?:\.\d+)?\s*%)|(?<![\d.])(\d(?:\.\d+)?)\s*(?:CGPA|GPA)\b", re.I)
YEAR_RE = re.compile(r"(?:19|20)\d{2}")
DEGREE_CUT = re.compile(r",|\||\bfrom\b|\bat\b|\b(?:19|20)\d{2}\b|CGPA|GPA|CPI|\d+(?:\.\d+)?\s*%", re.I)


def _find_degree(line):
    m = SHORT_DEGREE.search(line) or LONG_DEGREE.search(line)
    if not m:
        return None
    seg = line[m.start():]
    cut = DEGREE_CUT.search(seg, 2)
    seg = seg[:cut.start()] if cut else seg
    inst = INSTITUTION_RE.search(seg)
    if inst and inst.start() > 0:
        seg = seg[:inst.start()]
    return re.sub(r"[\s\-–—(:]+$", "", seg).strip() or m.group(0)


def _institution(line):
    if not INSTITUTION_RE.search(line):
        return None
    for part in re.split(r",|\||–|—|\s-\s|\bat\b|\bfrom\b|\(|\)", line):
        if INSTITUTION_RE.search(part):
            part = re.sub(r"\s*(?:" + DATE + r")(?:\s*(?:-|–|—|to)\s*(?:" + DATE + "|" + PRESENT + r"))?", "", part, flags=re.I)
            part = part.strip(" -–—:•")
            if len(part) > 3:
                return part
    return None


def _years_text(window):
    blob = " ".join(window)
    m = RANGE_RE.search(blob)
    if m:
        return f"{m.group(1)} – {m.group(2)}"
    years = YEAR_RE.findall(blob)
    return None if not years else (years[0] if len(set(years)) == 1 else f"{years[0]} – {years[-1]}")


def parse_education(lines):
    lines = [BULLET.sub("", l) for l in _lines(lines)]
    deg_idx = [i for i, l in enumerate(lines) if _find_degree(l)]
    if not deg_idx:
        out = []
        for i, l in enumerate(lines):
            inst = _institution(l)
            if inst:
                out.append({"degree": None, "institution": inst,
                            "year": _years_text(lines[i:i + 2]), "grade": None})
        return out
    entries = {i: {"degree": _find_degree(lines[i]), "institution": _institution(lines[i]),
                   "year": None, "grade": None} for i in deg_idx}
    for j, l in enumerate(lines):
        if j in entries:
            continue
        inst = _institution(l)
        if inst:
            nearest = min(deg_idx, key=lambda d: (abs(d - j), -d))
            if abs(nearest - j) <= 2 and not entries[nearest]["institution"]:
                entries[nearest]["institution"] = inst
    for i in deg_idx:
        window = [lines[k] for k in range(i, min(len(lines), i + 4)) if k == i or k not in entries]
        if i > 0 and i - 1 not in entries and INSTITUTION_RE.search(lines[i - 1]):
            window.insert(0, lines[i - 1])  # institution printed above the degree
        entries[i]["year"] = _years_text(window)
        g = GRADE_RE.search(" ".join(window))
        entries[i]["grade"] = (g.group(1) or g.group(2) or g.group(3)).strip() if g else None
        if not entries[i]["institution"]:
            orgs = nlp.entities(" ".join(window), "ORG")
            entries[i]["institution"] = orgs[0] if orgs else None
    return [entries[i] for i in deg_idx]


# --------------------------------------------------------------------------- experience
TITLE_WORDS = re.compile(r"\b(?:Engineer|Developer|Intern|Analyst|Manager|Consultant|Lead|Architect|"
                         r"Designer|Scientist|Associate|Executive|Administrator|Specialist|Trainee|"
                         r"Officer|Director|Head|Programmer|Tester|Researcher|Assistant|Coordinator|"
                         r"Technician|Support)\b", re.I)
COMPANY_WORDS = re.compile(r"\b(?:Pvt|Ltd|Inc|LLC|LLP|Technologies|Solutions|Systems|Corp|Corporation|"
                           r"Labs|Software|Infotech|Services|Company|Group|Consulting|Limited|"
                           r"Technology|Global|Bank|Enterprises)\b", re.I)


def _is_header_candidate(line):
    return bool(line) and not BULLET.match(line) and len(line.split()) <= 12 and not line.endswith(".")


def _split_header(headers):
    headers = [h.strip(" |,-–—•") for h in headers if h.strip(" |,-–—•")]
    if len(headers) == 1:
        parts = re.split(r"\s+(?:at|@)\s+|\s*\|\s*|\s+[-–—]\s+|,\s*", headers[0], maxsplit=1)
        headers = [p.strip() for p in parts if p.strip()]
    if not headers:
        return None, None
    if len(headers) == 1:
        return (None, headers[0]) if COMPANY_WORDS.search(headers[0]) and not TITLE_WORDS.search(headers[0]) \
            else (headers[0], None)
    a, b = headers[0], headers[1]
    a_company = bool(COMPANY_WORDS.search(a)) and not TITLE_WORDS.search(a)
    b_title = bool(TITLE_WORDS.search(b)) and not TITLE_WORDS.search(a)
    if a_company or b_title:
        a, b = b, a
    return a, b


def parse_experience(lines):
    lines = _lines(lines)
    idxs = [i for i, l in enumerate(lines) if RANGE_RE.search(l) and not BULLET.match(l)]
    ranges = [(m.group(1), m.group(2)) for l in (lines[i] for i in idxs) for m in [RANGE_RE.search(l)]]
    if not idxs:
        desc = "\n".join(BULLET.sub("", l) for l in lines).strip()
        return ([{"title": None, "company": None, "start_date": None, "end_date": None,
                  "description": desc}] if desc else []), 0.0
    header_idx = {}
    for n, i in enumerate(idxs):
        lo = idxs[n - 1] if n else -1
        heads = []
        for k in (i - 2, i - 1):
            if k > lo and _is_header_candidate(lines[k]):
                heads.append(k)
        remainder = RANGE_RE.sub("", lines[i]).strip(" |,-–—•()")
        if not remainder and not heads:
            heads = [k for k in (i + 1, i + 2) if k < len(lines) and k not in idxs
                     and _is_header_candidate(lines[k]) and len(lines[k]) < 90][:2]
        header_idx[i] = (heads, remainder)
    claimed = {k for heads, _ in header_idx.values() for k in heads} | set(idxs)
    entries = []
    for n, i in enumerate(idxs):
        nxt = idxs[n + 1] if n + 1 < len(idxs) else len(lines)
        heads, remainder = header_idx[i]
        texts = [lines[k] for k in heads] + ([remainder] if remainder else [])
        title, company = _split_header(texts[-2:] if len(texts) > 2 else texts)
        if company is None and title is None and texts:
            title = texts[0]
        if not company:
            for t in texts:
                orgs = nlp.entities(t, "ORG")
                if orgs and orgs[0] != title:
                    company = orgs[0]
                    break
        if company and "," in company and COMPANY_WORDS.search(company.split(",")[0]):
            company = company.split(",")[0].strip()  # drop trailing ", City"
        desc = [BULLET.sub("", lines[k]) for k in range(i + 1, nxt) if k not in claimed]
        m = RANGE_RE.search(lines[i])
        entries.append({"title": title, "company": company, "start_date": m.group(1),
                        "end_date": m.group(2), "description": "\n".join(desc).strip()})
    return entries, total_years(ranges)


# --------------------------------------------------------------------------- projects
TECH_LINE = re.compile(r"^(?:tech(?:nologies)?(?:\s+(?:stack|used))?|tools(?:\s+used)?|stack|environment)"
                       r"\s*[:\-]\s*(.+)$", re.I)


def parse_projects(lines):
    projects, current, prev_bullet = [], None, False
    for raw in lines:
        if not raw.strip():
            prev_bullet = False if current is None else prev_bullet
            continue
        is_bullet = bool(BULLET.match(raw))
        line = BULLET.sub("", raw).strip()
        tech = TECH_LINE.match(line)
        if tech and current is not None:
            current["technologies"] = tech.group(1).strip()
        elif is_bullet and current is not None:
            current["description"].append(line)
        elif current is not None and (prev_bullet and line[:1].islower() or
                                      (not current["description"] and (len(line) > 70 or line.endswith(".")))):
            current["description"].append(line)
        else:
            line = RANGE_RE.sub("", line).strip(" |,-–—")
            parts = re.split(r"\s*[|–—]\s*|\s+-\s+|\s*:\s+", line, maxsplit=1)
            name = parts[0].strip()
            if not name:
                continue
            extra = parts[1].strip() if len(parts) > 1 else ""
            current = {"name": name[:200], "description": [], "technologies": extra[:250] if len(extra) < 120 else ""}
            if len(extra) >= 120:
                current["description"].append(extra)
            projects.append(current)
        prev_bullet = is_bullet
    out = []
    for p in projects:
        desc = "\n".join(p["description"]).strip()
        tech = p["technologies"] or ", ".join(s["name"] for s in extract_skills(p["name"] + "\n" + desc))
        out.append({"name": p["name"], "description": desc, "technologies": tech})
    return out


# --------------------------------------------------------------------------- certifications
def parse_certifications(lines):
    out = []
    for raw in _lines(lines):
        line = BULLET.sub("", raw).strip()
        if not 4 <= len(line) <= 160:
            continue
        year = YEAR_RE.findall(line)
        line_no_year = re.sub(r"[\(\[]?\b(?:19|20)\d{2}\b[\)\]]?", "", line).strip(" -–—|,()")
        parts = re.split(r"\s+(?:by|from)\s+|\s*\|\s*", line_no_year, maxsplit=1)
        if len(parts) == 1 and "," in line_no_year:
            parts = line_no_year.rsplit(",", 1)
        elif len(parts) == 1:
            parts = re.split(r"\s+[-–—]\s+", line_no_year, maxsplit=1)
        out.append({"name": parts[0].strip()[:250], "issuer": parts[1].strip()[:200] if len(parts) > 1 else None,
                    "year": year[-1] if year else None})
    return out


# --------------------------------------------------------------------------- entry points
def parse_text(text: str, fallback_name: str = None) -> dict:
    header, sections = split_sections(text)
    warnings = []
    email = extract_email(text)
    phone = extract_phone("\n".join(header) or text[:600]) or extract_phone(text)
    name = extract_name(header, text, email)
    if not name:
        name = fallback_name
        warnings.append("Candidate name could not be detected; please review and edit it.")
    # drop "Languages:" style row labels so they are not mistaken for skills
    skills_text = "\n".join(l.split(":", 1)[1] if ":" in l else l for l in sections.get("skills", []))
    skills = extract_skills(text, skills_text)
    experience, years = parse_experience(sections.get("experience", []))
    if not years:
        m = re.search(r"(\d{1,2}(?:\.\d)?)\+?\s*(?:years|yrs)\s+(?:of\s+)?(?:professional\s+)?experience", text, re.I)
        years = float(m.group(1)) if m else 0.0
    if not email:
        warnings.append("No email address found.")
    if not phone:
        warnings.append("No phone number found.")
    if not skills:
        warnings.append("No known skills were detected.")
    return {
        "full_name": name, "email": email, "phone": phone, "skills": skills,
        "education": parse_education(sections.get("education", [])),
        "experience": experience,
        "projects": parse_projects(sections.get("projects", [])),
        "certifications": parse_certifications(sections.get("certifications", [])),
        "total_experience_years": years, "raw_text": text, "warnings": warnings,
    }


def parse_resume(path) -> dict:
    path = Path(path)
    try:
        text = extract_text(path)
    except ExtractionError as exc:
        raise ResumeParseError(str(exc)) from exc
    return parse_text(text, fallback_name=None)
