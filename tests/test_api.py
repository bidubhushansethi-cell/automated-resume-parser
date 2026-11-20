import csv
import io

from openpyxl import load_workbook

from tests.sample_resumes import RESUME_ONE, RESUME_TWO, build_docx, build_pdf


def _file(tmp_path, text=RESUME_ONE, kind="pdf", name="resume"):
    path = (build_pdf if kind == "pdf" else build_docx)(tmp_path / f"{name}.{kind}", text)
    return (io.BytesIO(path.read_bytes()), path.name)


def _upload(client, tmp_path, **kw):
    return client.post("/api/resumes/upload", data={"file": _file(tmp_path, **kw)}, content_type="multipart/form-data")


def test_api_requires_login(anon):
    r = anon.get("/api/candidates")
    assert r.status_code == 401 and "error" in r.get_json()
    assert anon.get("/").status_code == 302


def test_login_logout_flow(anon):
    anon.get("/login")
    with anon.session_transaction() as s:
        s["csrf_token"] = "abc"
    bad = anon.post("/login", data={"username": "hr", "password": "wrong", "csrf_token": "abc"})
    assert bad.status_code == 401
    ok = anon.post("/login", data={"username": "hr", "password": "password123", "csrf_token": "abc"})
    assert ok.status_code == 302
    assert anon.get("/").status_code == 200
    assert anon.get("/api/dashboard/stats").status_code == 200


def test_login_rejects_open_redirect(anon):
    with anon.session_transaction() as s:
        s["csrf_token"] = "abc"
    r = anon.post("/login?next=//evil.example", data={"username": "hr", "password": "password123", "csrf_token": "abc"})
    assert r.headers["Location"] == "/"


def test_csrf_is_enforced(client):
    client.environ_base["HTTP_X_CSRF_TOKEN"] = "wrong"
    assert client.delete("/api/candidates/1").status_code == 400


def test_upload_pdf_and_docx_and_persist(client, tmp_path, app):
    r = _upload(client, tmp_path)
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body["name"] == "Arjun Mehta" and body["skills_found"] > 10
    detail = client.get(f"/api/candidates/{body['candidate_id']}").get_json()
    assert detail["email"] == "arjun.mehta@example.com"
    assert len(detail["education"]) == 2 and len(detail["experience"]) == 2
    assert detail["resume"]["file_type"] == "pdf" and "arjun" in detail["raw_text"].casefold()
    r2 = _upload(client, tmp_path, text=RESUME_TWO, kind="docx", name="priya")
    assert r2.status_code == 201 and r2.get_json()["name"] == "Priya Nair"
    assert len(list(app.config["UPLOAD_FOLDER"].iterdir())) == 2


def test_upload_validation(client, tmp_path, app):
    assert client.post("/api/resumes/upload", data={}, content_type="multipart/form-data").status_code == 400
    txt = client.post("/api/resumes/upload", data={"file": (io.BytesIO(b"hello"), "a.txt")}, content_type="multipart/form-data")
    assert txt.status_code == 415
    fake = client.post("/api/resumes/upload", data={"file": (io.BytesIO(b"MZ not a pdf at all......"), "a.pdf")}, content_type="multipart/form-data")
    assert fake.status_code == 415
    empty = client.post("/api/resumes/upload", data={"file": (io.BytesIO(b""), "a.pdf")}, content_type="multipart/form-data")
    assert empty.status_code == 400
    big = client.post("/api/resumes/upload", data={"file": (io.BytesIO(b"%PDF-" + b"0" * 1_300_000), "big.pdf")}, content_type="multipart/form-data")
    assert big.status_code == 413
    traversal = client.post("/api/resumes/upload", data={"file": (io.BytesIO(b"x"), "../../evil.exe")}, content_type="multipart/form-data")
    assert traversal.status_code == 415
    assert not list(app.config["UPLOAD_FOLDER"].glob("*"))  # nothing stored for rejected files


def test_duplicate_email_rejected_and_file_cleaned(client, tmp_path, app):
    assert _upload(client, tmp_path).status_code == 201
    dup = _upload(client, tmp_path)
    assert dup.status_code == 409 and "already exists" in dup.get_json()["error"]
    assert len(list(app.config["UPLOAD_FOLDER"].iterdir())) == 1


def test_bulk_upload_reports_each_file(client, tmp_path):
    data = {"files": [_file(tmp_path, name="a"), _file(tmp_path, text=RESUME_TWO, name="b"),
                      (io.BytesIO(b"nope"), "c.txt")]}
    r = client.post("/api/resumes/bulk-upload", data=data, content_type="multipart/form-data")
    body = r.get_json()
    assert r.status_code == 200 and body["uploaded"] == 2 and body["failed"] == 1
    assert [x["success"] for x in body["results"]] == [True, True, False]


def _seed(client, tmp_path):
    _upload(client, tmp_path, name="a")
    _upload(client, tmp_path, text=RESUME_TWO, name="b")


def test_search_filter_sort_paginate(client, tmp_path):
    _seed(client, tmp_path)
    q = lambda **kw: client.get("/api/candidates/search", query_string=kw).get_json()
    assert q()["total"] == 2
    assert [c["full_name"] for c in q(name="priya")["candidates"]] == ["Priya Nair"]
    assert q(email="example.com")["total"] == 1
    assert q(skill="flask, aws")["total"] == 1 and q(skill="flask, power bi")["total"] == 0
    assert q(education="anna")["total"] == 1
    assert q(min_experience=5)["total"] == 1 and q(max_experience=3)["total"] == 1
    assert q(experience="wipro")["total"] == 1
    assert q(q="tcs")["total"] == 0 and q(q="selenium")["total"] == 1
    assert q(category="Cloud Computing")["total"] == 1
    assert [c["full_name"] for c in q(sort="name", order="asc")["candidates"]] == ["Arjun Mehta", "Priya Nair"]
    page = q(per_page=1, page=2)
    assert page["pages"] == 2 and len(page["candidates"]) == 1
    assert q(q="100%")["total"] == 0  # wildcard characters are escaped
    assert q(q="' OR 1=1 --")["total"] == 0  # SQL injection attempt is just text


def test_update_validate_and_delete(client, tmp_path, app):
    cid = _upload(client, tmp_path).get_json()["candidate_id"]
    detail = client.get(f"/api/candidates/{cid}").get_json()
    bad = client.put(f"/api/candidates/{cid}", json={**detail, "full_name": " ", "email": "nope"})
    assert bad.status_code == 422 and set(bad.get_json()["fields"]) >= {"full_name", "email"}
    detail.update(full_name="Arjun K. Mehta", phone="+91 99999 11111", skills=[{"name": "Rust"}, {"name": "Hand Lettering"}],
                  education=[{"degree": "MBA", "institution": "IIM Ahmedabad"}])
    ok = client.put(f"/api/candidates/{cid}", json=detail)
    assert ok.status_code == 200
    out = ok.get_json()
    assert out["full_name"] == "Arjun K. Mehta" and len(out["education"]) == 1
    assert {s["name"]: s["category"] for s in out["skills"]} == {"Rust": "Programming Languages", "Hand Lettering": "Other"}
    assert client.put("/api/candidates/999", json=detail).status_code == 404
    assert client.delete(f"/api/candidates/{cid}").status_code == 200
    assert client.get(f"/api/candidates/{cid}").status_code == 404
    assert not list(app.config["UPLOAD_FOLDER"].iterdir())


def test_update_rejects_duplicate_email(client, tmp_path):
    _seed(client, tmp_path)
    a = client.get("/api/candidates/search?name=priya").get_json()["candidates"][0]
    d = client.get(f"/api/candidates/{a['id']}").get_json()
    d["email"] = "arjun.mehta@example.com"
    assert client.put(f"/api/candidates/{a['id']}", json=d).status_code == 409


def test_download_original_resume(client, tmp_path):
    cid = _upload(client, tmp_path).get_json()["candidate_id"]
    rid = client.get(f"/api/candidates/{cid}").get_json()["resume"]["id"]
    r = client.get(f"/api/resumes/{rid}/download")
    assert r.status_code == 200 and r.data[:5] == b"%PDF-"
    assert "resume.pdf" in r.headers["Content-Disposition"]
    assert client.get("/api/resumes/999/download").status_code == 404


def test_export_csv_and_xlsx(client, tmp_path):
    _seed(client, tmp_path)
    r = client.get("/api/candidates/export?format=csv&skill=flask")
    assert r.status_code == 200 and r.mimetype == "text/csv"
    rows = list(csv.reader(io.StringIO(r.data.decode("utf-8-sig"))))
    assert rows[0][1] == "Full Name" and len(rows) == 2 and rows[1][1] == "Arjun Mehta"
    x = client.get("/api/candidates/export?format=xlsx")
    ws = load_workbook(io.BytesIO(x.data)).active
    assert ws.max_row == 3 and ws["B1"].value == "Full Name"
    assert client.get("/api/candidates/export?format=pdf").status_code == 400


def test_export_neutralises_formula_injection(client, tmp_path):
    cid = _upload(client, tmp_path).get_json()["candidate_id"]
    d = client.get(f"/api/candidates/{cid}").get_json()
    d["full_name"] = "=HYPERLINK(\"http://evil\")"
    assert client.put(f"/api/candidates/{cid}", json=d).status_code == 200
    rows = list(csv.reader(io.StringIO(client.get("/api/candidates/export").data.decode("utf-8-sig"))))
    assert rows[1][1].startswith("'=")


def test_dashboard_stats(client, tmp_path):
    empty = client.get("/api/dashboard/stats").get_json()
    assert empty["total_candidates"] == 0 and empty["recent_uploads"] == []
    _seed(client, tmp_path)
    s = client.get("/api/dashboard/stats").get_json()
    assert s["total_resumes"] == 2 and s["total_candidates"] == 2 and s["total_skills"] > 10
    assert len(s["uploads_last_7_days"]) == 7 and sum(d["count"] for d in s["uploads_last_7_days"]) == 2
    assert s["recent_uploads"][0]["name"] in ("Arjun Mehta", "Priya Nair")


def test_pages_render(client, tmp_path):
    cid = _upload(client, tmp_path).get_json()["candidate_id"]
    for url in ("/", "/upload", "/candidates", f"/candidates/{cid}"):
        assert client.get(url).status_code == 200, url
    assert client.get("/candidates/999").status_code == 404


def test_login_is_throttled_after_repeated_failures(anon):
    with anon.session_transaction() as s:
        s["csrf_token"] = "abc"
    for _ in range(5):
        assert anon.post("/login", data={"username": "ghost", "password": "x", "csrf_token": "abc"}).status_code == 401
    assert anon.post("/login", data={"username": "ghost", "password": "x", "csrf_token": "abc"}).status_code == 429
