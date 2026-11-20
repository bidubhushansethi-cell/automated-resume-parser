# TalentScan – Automated Resume Parser

A local web application for HR teams. Upload PDF or DOCX resumes and TalentScan reads each one, extracts the
candidate's details with spaCy and regex, sorts their skills into categories, and stores everything in PostgreSQL
where it can be searched, edited and exported.

## Features

- **Upload**: PDF and DOCX, single or many at once, drag and drop, upload progress, per-file error messages.
- **Parsing**: name, email, phone, skills, education (degree, college/university, years, grade), work experience,
  projects, certifications, total years of experience. Warnings are shown when something could not be found.
- **Skill categories**: Programming Languages, Web Development, Database Technologies, Frameworks, Machine Learning,
  Data Science, Cloud Computing, Tools and Platforms (about 175 skills with aliases, e.g. `JS`, `Postgres`, `k8s`).
- **Dashboard**: total resumes, candidates, distinct skills, average experience, recent uploads, skills by category,
  top skills, experience levels, uploads over 7 days.
- **Candidates**: list, full profile, edit, delete, view the raw text the parser read, download the original resume.
- **Search**: by name, email, skills (all must match), education, experience (years or employer/title), skill
  category, plus a free-text box. Sorting and pagination.
- **Export**: CSV and Excel (respects the current filters).
- **Security**: login with hashed passwords, CSRF protection, file type and content checks, random stored file names,
  all data behind login, parameterised queries, formula-injection-safe exports, login throttling.

## Technology

Python 3.12 · Flask · Flask-SQLAlchemy / SQLAlchemy 2 · PostgreSQL (psycopg2) · spaCy · pdfplumber · python-docx ·
openpyxl · Bootstrap 5 (loaded from a CDN, so the browser needs internet access) · vanilla JavaScript.

## Architecture

```
automated_resume_parser/
├── app/
│   ├── __init__.py          app factory, error handlers, CLI commands (init-db, create-user)
│   ├── auth.py              session auth, CSRF check, security headers
│   ├── extensions.py        SQLAlchemy instance
│   ├── models/              User, Candidate, Education, Skill, Experience, Project, Certification, ResumeFile
│   ├── parser/              text_extractor.py (PDF/DOCX) · resume_parser.py · skills_db.py · nlp.py (spaCy)
│   ├── services/            resume_service (validate/store/save) · search_service · export_service
│   ├── routes/              auth.py · pages.py · api.py (REST)
│   ├── templates/           Jinja pages (Bootstrap)
│   └── static/              css/ js/ images/
├── uploads/                 original resumes (random file names, never served directly)
├── tests/                   parser tests and API tests
├── config.py · run.py · requirements.txt · .env.example
```

Flow: browser → `/api/resumes/upload` → validate (extension, size, file signature) → save under a random name →
`text_extractor` → `resume_parser` (sections → regex + spaCy + skill dictionary) → rows in PostgreSQL → JSON back.

spaCy is used for name detection (PERSON) and for organisation names when the layout gives no other clue. If the model
is not installed the parser logs a warning and falls back to rules only.

## Installation (Windows 11, PowerShell)

### 1. PostgreSQL

Install PostgreSQL 15 or newer from https://www.postgresql.org/download/windows/ and remember the password you set
for the `postgres` user. Create the database (adjust the version folder if needed):

```powershell
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -c "CREATE DATABASE resume_parser;"
```

### 2. Python environment

```powershell
cd automated_resume_parser
python -m venv venv
.\venv\Scripts\Activate.ps1       # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 3. Configuration

```powershell
Copy-Item .env.example .env
notepad .env
```

Set `SECRET_KEY` (generate with `python -c "import secrets; print(secrets.token_hex(32))"`), `DB_PASSWORD`
(your PostgreSQL password), and `ADMIN_USERNAME` / `ADMIN_PASSWORD` (the first HR login, at least 8 characters).
The app refuses to start, with a message saying what is missing, if `SECRET_KEY` or the database settings are absent.
`.env` is in `.gitignore`; never commit it.

### 4. Create tables and the first user

```powershell
flask --app run init-db
```

Add more users later with `flask --app run create-user some.name` (prompts for the password).

### 5. Run

```powershell
python run.py
```

Open http://127.0.0.1:5000 and sign in. Stop with `Ctrl+C`.

### 6. Tests

```powershell
pip install -r requirements-dev.txt
python -m pytest -v
```

The tests build real PDF and DOCX resumes, and run the API against an in-memory SQLite database, so PostgreSQL is
not needed for them.

## API

All endpoints need a signed-in session and, for non-GET requests, the header `X-CSRF-Token` (the web UI does this
automatically). Errors are JSON: `{"error": "message", "fields": {...}}`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/resumes/upload` | One resume, multipart field `file`. 201 with the parsed candidate. |
| POST | `/api/resumes/bulk-upload` | Many resumes, field `files`. 200 with a result per file (422 if all failed). |
| GET | `/api/candidates` | List. Query: `page`, `per_page` (max 100), `sort` (`name`, `email`, `experience`, `created`), `order`, plus the filters below. |
| GET | `/api/candidates/search` | Same as above. |
| GET | `/api/candidates/<id>` | Full profile including raw text. |
| PUT | `/api/candidates/<id>` | Replace editable fields (`full_name`, `email`, `phone`, `total_experience_years`, `skills`, `education`, `experience`, `projects`, `certifications`). 422 on validation errors, 409 on duplicate email. |
| DELETE | `/api/candidates/<id>` | Delete the candidate and the stored file. |
| GET | `/api/dashboard/stats` | Dashboard numbers. |
| GET | `/api/resumes/<resume_id>/download` | Original file. `resume_id` is `candidate.resume.id`. |
| GET | `/api/candidates/export?format=csv\|xlsx` | Export, accepts the same filters as search. |

Filters: `q` (free text), `name`, `email`, `skill` (comma separated, all must match), `category`, `education`,
`experience` (title or company), `min_experience`, `max_experience`.

## Screenshots

Add your own screenshots to `app/static/images/` and link them here after your first run:
`dashboard.png`, `upload.png`, `candidates.png`, `profile.png`.

## Limits to know about

- Scanned (image-only) PDFs have no text layer and are rejected with a clear message. OCR is not included.
- Parsing is rule-based, so unusual layouts (multi-column designs, text in images) can be misread. The profile page
  shows the extracted text and lets HR correct any field.
- A resume whose email already exists is rejected as a duplicate.
- Bootstrap and icons load from a CDN. For an offline machine, download them into `app/static/` and edit `base.html`.
- `python run.py` uses Flask's development server, which is fine for one laptop. For shared use, run it behind a
  production server and HTTPS, and set `SESSION_COOKIE_SECURE=1`.

## Future enhancements

OCR for scanned resumes · job-description matching and candidate ranking · role-based access (admin / recruiter) ·
duplicate detection by phone · PostgreSQL full-text search · email notifications · audit log · Docker setup.

## Troubleshooting

- `SECRET_KEY is not set`: create `.env` from `.env.example`.
- `password authentication failed`: `DB_PASSWORD` does not match your PostgreSQL password.
- `database "resume_parser" does not exist`: run the `CREATE DATABASE` command in step 1.
- `spaCy model 'en_core_web_sm' unavailable` warning: run `python -m spacy download en_core_web_sm`.
- `flask` not found: activate the virtual environment first (`.\venv\Scripts\Activate.ps1`).

### Windows DLL issues

**`DLL load failed while importing numpy_ops: The specified module could not be found`**

This means `MSVCP140.dll` (Visual C++ runtime) is not on the DLL search path. Install the
[Microsoft Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe). If that is not possible,
copy `MSVCP140.dll` from another location on your system (e.g. from `C:\Program Files\Java\jdk-*\bin\`) into
`venv\Lib\site-packages\thinc\backends\`:

```powershell
Copy-Item "C:\Program Files\Java\jdk-27\bin\msvcp140.dll" ".\venv\Lib\site-packages\thinc\backends\"
```

**`DLL load failed ... An Application Control policy has blocked this file`**

Windows Defender Application Control (WDAC) may block unsigned `.pyd` extensions. Force-reinstall the affected
packages so Windows marks the new files as allowed:

```powershell
pip install --force-reinstall --no-deps spacy preshed
```

Verify after any DLL fix:

```powershell
python -c "import spacy; nlp=spacy.load('en_core_web_sm'); print('OK')"
```
