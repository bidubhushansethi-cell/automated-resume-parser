"use strict";
/* ---------- helpers ---------- */
const csrf = () => document.querySelector('meta[name="csrf-token"]').content;
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const slug = (s) => String(s).toLowerCase().replace(/[^a-z]+/g, "-").replace(/^-|-$/g, "");
const $ = (sel, root = document) => root.querySelector(sel);
const CATEGORY_COLORS = { "Programming Languages": "#2f63d6", "Web Development": "#d2561f", "Database Technologies": "#7a4bc7",
  "Frameworks": "#0e8f83", "Machine Learning": "#c72d6a", "Data Science": "#b27a05", "Cloud Computing": "#1d84c4",
  "Tools and Platforms": "#586274", "Other": "#6b7684" };

function toast(message, type = "success") {
  const el = document.createElement("div");
  el.className = `toast align-items-center text-bg-${type === "error" ? "danger" : "success"} border-0`;
  el.setAttribute("role", "alert");
  el.innerHTML = `<div class="d-flex"><div class="toast-body">${esc(message)}</div><button class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button></div>`;
  $("#toasts").appendChild(el);
  const t = new bootstrap.Toast(el, { delay: type === "error" ? 7000 : 3500 });
  el.addEventListener("hidden.bs.toast", () => el.remove());
  t.show();
}

async function api(url, options = {}) {
  const opts = { credentials: "same-origin", ...options, headers: { "X-CSRF-Token": csrf(), ...(options.headers || {}) } };
  if (opts.json !== undefined) { opts.body = JSON.stringify(opts.json); opts.headers["Content-Type"] = "application/json"; }
  let res;
  try { res = await fetch(url, opts); } catch (e) { throw new Error("Cannot reach the server. Check that the app is running."); }
  if (res.status === 401) { window.location = "/login"; throw new Error("Your session expired. Please sign in again."); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) { const err = new Error(data.error || `Request failed (${res.status}).`); err.fields = data.fields; err.status = res.status; throw err; }
  return data;
}

function confirmDialog(message, okLabel = "Delete") {
  return new Promise((resolve) => {
    const modalEl = $("#confirmModal"); const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    $("#confirmText").textContent = message; $("#confirmOk").textContent = okLabel;
    let done = false;
    const finish = (v) => { if (!done) { done = true; resolve(v); } };
    $("#confirmOk").onclick = () => { finish(true); modal.hide(); };
    modalEl.addEventListener("hidden.bs.modal", () => finish(false), { once: true });
    modal.show();
  });
}

const chip = (s) => `<span class="chip cat-${slug(s.category)}" title="${esc(s.category)}">${esc(s.name)}</span>`;
const fmtDate = (iso) => iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "";
const fmtSize = (n) => n > 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1024)) + " KB";
const bars = (items, label, value, color) => {
  const max = Math.max(1, ...items.map((i) => i[value]));
  return items.length ? items.map((i) => `<div class="bar-row"><span>${esc(i[label])}</span><div class="bar-track"><div class="bar-fill" style="width:${(i[value] / max) * 100}%;--c:${color ? color(i) : "var(--brand)"}"></div></div><span class="bar-num">${i[value]}</span></div>`).join("")
    : `<p class="text-muted mb-0">Nothing to show yet.</p>`;
};

/* ---------- dashboard ---------- */
async function initDashboard() {
  try {
    const d = await api("/api/dashboard/stats");
    document.querySelectorAll("[data-stat]").forEach((el) => { el.textContent = d[el.dataset.stat]; });
    $("#recentUploads").innerHTML = d.recent_uploads.length ? `<table class="table table-sm align-middle mb-0"><tbody>${d.recent_uploads.map((r) =>
      `<tr><td><a class="cand-name" href="/candidates/${r.candidate_id}">${esc(r.name)}</a><div class="sub">${esc(r.filename)}</div></td><td>${r.skill_count} skills</td><td class="text-end sub">${esc(fmtDate(r.uploaded_at))}</td></tr>`).join("")}</tbody></table>`
      : `<p class="text-muted mb-0">No resumes yet. <a href="/upload">Upload the first one.</a></p>`;
    $("#catBars").innerHTML = bars(d.skills_by_category, "category", "candidates", (i) => CATEGORY_COLORS[i.category] || "#6b7684");
    $("#topSkills").innerHTML = bars(d.top_skills, "name", "count");
    $("#expBars").innerHTML = bars(d.experience_distribution, "label", "count");
    $("#dayBars").innerHTML = bars(d.uploads_last_7_days, "label", "count");
  } catch (e) { toast(e.message, "error"); }
}

/* ---------- upload ---------- */
function initUpload() {
  const input = $("#fileInput"), list = $("#fileList"), zone = $("#dropzone");
  const maxMb = +input.dataset.maxMb, maxFiles = +input.dataset.maxFiles;
  let files = [];
  const valid = (f) => /\.(pdf|docx)$/i.test(f.name) ? (f.size > maxMb * 1048576 ? `Larger than ${maxMb} MB` : f.size === 0 ? "File is empty" : null) : "Only PDF and DOCX files are allowed";
  function render() {
    list.innerHTML = files.map((f, i) => { const err = valid(f);
      return `<li><i class="bi ${err ? "bi-x-circle bad" : "bi-file-earmark-text"}"></i><div class="grow">${esc(f.name)} <span class="sub">${fmtSize(f.size)}</span>${err ? `<div class="bad small">${esc(err)}</div>` : ""}</div><button class="btn btn-sm btn-link text-muted" data-rm="${i}" aria-label="Remove ${esc(f.name)}"><i class="bi bi-x-lg"></i></button></li>`; }).join("");
    const ok = files.filter((f) => !valid(f)).length;
    $("#uploadBtn").disabled = !ok; $("#clearBtn").disabled = !files.length;
  }
  function add(newFiles) {
    files = files.concat([...newFiles]).slice(0, maxFiles);
    if (files.length === maxFiles) toast(`Only ${maxFiles} files can be uploaded at a time.`, "error");
    render();
  }
  input.addEventListener("change", () => { add(input.files); input.value = ""; });
  list.addEventListener("click", (e) => { const b = e.target.closest("[data-rm]"); if (b) { files.splice(+b.dataset.rm, 1); render(); } });
  ["dragenter", "dragover"].forEach((ev) => zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) => zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.remove("drag"); }));
  zone.addEventListener("drop", (e) => add(e.dataTransfer.files));
  $("#clearBtn").addEventListener("click", () => { files = []; render(); });

  $("#uploadBtn").addEventListener("click", () => {
    const send = files.filter((f) => !valid(f));
    const fd = new FormData();
    send.forEach((f) => fd.append(send.length === 1 ? "file" : "files", f));
    const xhr = new XMLHttpRequest();
    xhr.open("POST", send.length === 1 ? "/api/resumes/upload" : "/api/resumes/bulk-upload");
    xhr.setRequestHeader("X-CSRF-Token", csrf());
    const bar = $("#progressBar");
    $("#progressWrap").classList.remove("d-none"); bar.style.width = "0"; bar.textContent = "";
    $("#uploadBtn").disabled = true; $("#uploadSpin").classList.remove("d-none");
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) { const p = Math.round((e.loaded / e.total) * 100); bar.style.width = p + "%"; bar.textContent = p < 100 ? p + "%" : "Parsing…"; } };
    xhr.onerror = () => { finish(); toast("Upload failed. Check that the app is running.", "error"); };
    xhr.onload = () => {
      finish();
      let body = {}; try { body = JSON.parse(xhr.responseText); } catch (e) { /* non-JSON error page */ }
      if (xhr.status === 401) { window.location = "/login"; return; }
      const results = body.results || [{ filename: send[0].name, ...body }];
      $("#resultsPanel").classList.remove("d-none");
      $("#results").innerHTML = results.map((r) => r.success
        ? `<li><i class="bi bi-check-circle-fill ok"></i><div class="grow"><a href="/candidates/${r.candidate_id}">${esc(r.name)}</a> <span class="sub">${esc(r.filename)} · ${r.skills_found} skills found</span>${(r.warnings || []).map((w) => `<div class="small text-warning-emphasis">${esc(w)}</div>`).join("")}</div></li>`
        : `<li><i class="bi bi-x-circle-fill bad"></i><div class="grow">${esc(r.filename)}<div class="bad small">${esc(r.error || "Upload failed.")}</div></div></li>`).join("");
      const okCount = results.filter((r) => r.success).length;
      if (okCount) toast(`${okCount} resume${okCount > 1 ? "s" : ""} parsed and saved.`);
      if (okCount < results.length) toast(`${results.length - okCount} file${results.length - okCount > 1 ? "s" : ""} could not be processed.`, "error");
      files = files.filter((f) => !results.some((r) => r.success && r.filename === f.name)); render();
    };
    function finish() { $("#uploadSpin").classList.add("d-none"); setTimeout(() => $("#progressWrap").classList.add("d-none"), 800); render(); }
    xhr.send(fd);
  });
  render();
}

/* ---------- candidates list ---------- */
function initCandidates() {
  const form = $("#filterForm"); let page = 1, timer;
  const params = (extra = {}) => { const p = new URLSearchParams(); new FormData(form).forEach((v, k) => { if (String(v).trim()) p.set(k, String(v).trim()); }); Object.entries(extra).forEach(([k, v]) => p.set(k, v)); return p; };
  async function load() {
    const p = params({ page, per_page: 10 });
    history.replaceState(null, "", "?" + p.toString());
    const ex = params(); $("#exportCsv").href = "/api/candidates/export?format=csv&" + ex; $("#exportXlsx").href = "/api/candidates/export?format=xlsx&" + ex;
    $("#candRows").innerHTML = `<tr><td colspan="5" class="text-center text-muted py-4"><span class="spinner-border spinner-border-sm"></span> Loading…</td></tr>`;
    try {
      const d = await api("/api/candidates?" + p);
      $("#totalLine").textContent = `${d.total} candidate${d.total === 1 ? "" : "s"} found`;
      $("#candRows").innerHTML = d.candidates.length ? d.candidates.map((c) => `<tr>
        <td><a class="cand-name" href="/candidates/${c.id}">${esc(c.full_name)}</a><div class="sub">${esc(c.email || "No email")}${c.phone ? " · " + esc(c.phone) : ""}</div></td>
        <td style="min-width:220px">${c.skills.map(chip).join("")}${c.skill_count > c.skills.length ? `<span class="sub">+${c.skill_count - c.skills.length}</span>` : ""}</td>
        <td class="d-none d-md-table-cell sub">${esc(c.top_education || "—")}</td>
        <td>${c.total_experience_years} yrs</td>
        <td class="text-end text-nowrap">
          <a class="btn btn-sm btn-light" href="/candidates/${c.id}" title="View profile"><i class="bi bi-eye"></i></a>
          ${c.resume_id ? `<a class="btn btn-sm btn-light" href="/api/resumes/${c.resume_id}/download" title="Download resume"><i class="bi bi-download"></i></a>` : ""}
          <button class="btn btn-sm btn-light text-danger" data-del="${c.id}" data-name="${esc(c.full_name)}" title="Delete"><i class="bi bi-trash"></i></button></td></tr>`).join("")
        : `<tr><td colspan="5" class="text-center text-muted py-5">No candidates match. Adjust the filters or <a href="/upload">upload resumes</a>.</td></tr>`;
      $("#pageInfo").textContent = d.total ? `Page ${d.page} of ${d.pages}` : "";
      const pages = []; for (let i = 1; i <= d.pages; i++) if (i === 1 || i === d.pages || Math.abs(i - d.page) <= 2) pages.push(i);
      let last = 0; $("#pager").innerHTML = pages.map((i) => { const gap = i - last > 1 ? `<li class="page-item disabled"><span class="page-link">…</span></li>` : ""; last = i;
        return gap + `<li class="page-item ${i === d.page ? "active" : ""}"><a class="page-link" href="#" data-page="${i}">${i}</a></li>`; }).join("");
    } catch (e) { $("#candRows").innerHTML = ""; toast(e.message, "error"); }
  }
  const saved = new URLSearchParams(location.search);
  saved.forEach((v, k) => { if (k === "page") page = +v || 1; else if (form.elements[k]) form.elements[k].value = v; });
  form.addEventListener("submit", (e) => { e.preventDefault(); page = 1; load(); });
  $("#fq").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => { page = 1; load(); }, 350); });
  ["fsort", "forder"].forEach((id) => $("#" + id).addEventListener("change", () => { page = 1; load(); }));
  $("#resetBtn").addEventListener("click", () => { form.reset(); page = 1; load(); });
  $("#pager").addEventListener("click", (e) => { const a = e.target.closest("[data-page]"); if (a) { e.preventDefault(); page = +a.dataset.page; load(); } });
  $("#candRows").addEventListener("click", async (e) => {
    const b = e.target.closest("[data-del]"); if (!b) return;
    if (!(await confirmDialog(`Delete ${b.dataset.name} and their resume file? This cannot be undone.`))) return;
    try { await api(`/api/candidates/${b.dataset.del}`, { method: "DELETE" }); toast("Candidate deleted."); load(); } catch (err) { toast(err.message, "error"); }
  });
  load();
}

/* ---------- candidate profile ---------- */
const REPEATERS = {
  education: { label: "Education", fields: [["degree", "Degree"], ["institution", "College / university"], ["year", "Years"], ["grade", "Grade"]] },
  experience: { label: "Work experience", fields: [["title", "Job title"], ["company", "Company"], ["start_date", "Start"], ["end_date", "End"], ["description", "Description", "textarea"]] },
  projects: { label: "Projects", fields: [["name", "Project name"], ["technologies", "Technologies"], ["description", "Description", "textarea"]] },
  certifications: { label: "Certifications", fields: [["name", "Certification"], ["issuer", "Issuer"], ["year", "Year"]] },
};

function initCandidate() {
  const root = $("#profile"), id = root.dataset.id; let cand;
  const section = (title, items, render) => `<h2 class="section-title">${title}</h2>` + (items.length ? items.map((i) => `<div class="entry">${render(i)}</div>`).join("") : `<p class="text-muted">None found in the resume.</p>`);
  function show() {
    const byCat = {}; cand.skills.forEach((s) => (byCat[s.category] = byCat[s.category] || []).push(s));
    root.innerHTML = `
      <div class="profile-head"><div><h1>${esc(cand.full_name)}</h1>
        <div class="meta-line"><span><i class="bi bi-envelope"></i> ${esc(cand.email || "No email")}</span><span><i class="bi bi-telephone"></i> ${esc(cand.phone || "No phone")}</span>
        <span><i class="bi bi-briefcase"></i> ${cand.total_experience_years} years experience</span><span><i class="bi bi-calendar3"></i> Added ${esc(fmtDate(cand.created_at))}</span></div></div>
        <div class="d-flex gap-2 flex-wrap">${cand.resume ? `<a class="btn btn-outline-secondary" href="/api/resumes/${cand.resume.id}/download"><i class="bi bi-download"></i> Resume (${esc(cand.resume.file_type.toUpperCase())})</a>` : ""}
        <button class="btn btn-brand" id="editBtn"><i class="bi bi-pencil"></i> Edit</button><button class="btn btn-outline-danger" id="delBtn"><i class="bi bi-trash"></i> Delete</button></div></div>
      <div class="panel">
        <h2 class="section-title mt-0">Skills (${cand.skills.length})</h2>
        ${cand.skills.length ? Object.entries(byCat).map(([cat, list]) => `<div class="mb-2"><div class="sub mb-1">${esc(cat)}</div>${list.map(chip).join("")}</div>`).join("") : `<p class="text-muted">No skills detected.</p>`}
        ${section("Education", cand.education, (e) => `<div class="entry-title">${esc(e.degree || "Education")}</div><div class="sub">${[e.institution, e.year, e.grade && "Grade " + e.grade].filter(Boolean).map(esc).join(" · ")}</div>`)}
        ${section("Work experience", cand.experience, (e) => `<div class="entry-title">${esc(e.title || "Role not detected")}${e.company ? " · " + esc(e.company) : ""}</div><div class="sub">${esc([e.start_date, e.end_date].filter(Boolean).join(" – "))}</div>${e.description ? `<p class="pre">${esc(e.description)}</p>` : ""}`)}
        ${section("Projects", cand.projects, (p) => `<div class="entry-title">${esc(p.name)}</div>${p.technologies ? `<div class="sub">${esc(p.technologies)}</div>` : ""}${p.description ? `<p class="pre">${esc(p.description)}</p>` : ""}`)}
        ${section("Certifications", cand.certifications, (c) => `<div class="entry-title">${esc(c.name)}</div><div class="sub">${[c.issuer, c.year].filter(Boolean).map(esc).join(" · ")}</div>`)}
      </div>
      <div class="panel mt-3"><h2 class="mb-2">Extracted resume text</h2><p class="sub">The plain text the parser read from ${esc(cand.resume ? cand.resume.original_filename : "the file")}. Use it to check what was missed.</p>
        <details><summary class="btn btn-sm btn-light">Show text</summary><pre class="raw-text mt-2 mb-0">${esc(cand.raw_text || "")}</pre></details></div>`;
    $("#editBtn").onclick = openEdit;
    $("#delBtn").onclick = async () => {
      if (!(await confirmDialog(`Delete ${cand.full_name} and their resume file? This cannot be undone.`))) return;
      try { await api(`/api/candidates/${id}`, { method: "DELETE" }); window.location = "/candidates"; } catch (e) { toast(e.message, "error"); }
    };
  }
  const field = (name, label, value, type = "text", extra = "") => type === "textarea"
    ? `<div class="col-12"><label class="form-label">${label}</label><textarea class="form-control form-control-sm" rows="3" data-f="${name}">${esc(value)}</textarea></div>`
    : `<div class="col-md-6"><label class="form-label">${label}</label><input class="form-control form-control-sm" type="${type}" data-f="${name}" value="${esc(value)}" ${extra}></div>`;
  const rowHtml = (key, item = {}) => `<div class="repeat-row" data-row="${key}"><div class="row g-2">${REPEATERS[key].fields.map(([n, l, t]) => field(n, l, item[n] || "", t)).join("")}</div><button type="button" class="btn btn-sm btn-link text-danger px-0 mt-1" data-remove>Remove</button></div>`;
  function openEdit() {
    $("#editBody").innerHTML = `<div class="row g-2 mb-3">
      <div class="col-md-6"><label class="form-label" for="ef-name">Full name</label><input class="form-control" id="ef-name" value="${esc(cand.full_name)}" required><div class="invalid-feedback"></div></div>
      <div class="col-md-6"><label class="form-label" for="ef-email">Email</label><input class="form-control" id="ef-email" type="email" value="${esc(cand.email || "")}"><div class="invalid-feedback"></div></div>
      <div class="col-md-6"><label class="form-label" for="ef-phone">Phone</label><input class="form-control" id="ef-phone" value="${esc(cand.phone || "")}"><div class="invalid-feedback"></div></div>
      <div class="col-md-6"><label class="form-label" for="ef-exp">Total experience (years)</label><input class="form-control" id="ef-exp" type="number" min="0" max="60" step="0.1" value="${cand.total_experience_years}"><div class="invalid-feedback"></div></div>
      <div class="col-12"><label class="form-label" for="ef-skills">Skills (comma separated; categories are assigned automatically)</label><textarea class="form-control" id="ef-skills" rows="2">${esc(cand.skills.map((s) => s.name).join(", "))}</textarea></div></div>
      ${Object.entries(REPEATERS).map(([k, r]) => `<h3 class="h6 mt-3">${r.label}</h3><div data-list="${k}">${cand[k].map((i) => rowHtml(k, i)).join("")}</div><button type="button" class="btn btn-sm btn-outline-secondary" data-add="${k}"><i class="bi bi-plus"></i> Add</button>`).join("")}`;
    bootstrap.Modal.getOrCreateInstance($("#editModal")).show();
  }
  $("#editModal").addEventListener("click", (e) => {
    const add = e.target.closest("[data-add]"); if (add) { $(`[data-list="${add.dataset.add}"]`).insertAdjacentHTML("beforeend", rowHtml(add.dataset.add)); }
    if (e.target.closest("[data-remove]")) e.target.closest(".repeat-row").remove();
  });
  $("#editForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    document.querySelectorAll("#editBody .is-invalid").forEach((el) => el.classList.remove("is-invalid"));
    const known = Object.fromEntries(cand.skills.map((s) => [s.name.toLowerCase(), s.category]));
    const payload = { full_name: $("#ef-name").value, email: $("#ef-email").value, phone: $("#ef-phone").value, total_experience_years: $("#ef-exp").value || 0,
      skills: $("#ef-skills").value.split(",").map((s) => s.trim()).filter(Boolean).map((name) => ({ name, category: known[name.toLowerCase()] })) };
    Object.keys(REPEATERS).forEach((k) => { payload[k] = [...document.querySelectorAll(`[data-row="${k}"]`)].map((row) => Object.fromEntries([...row.querySelectorAll("[data-f]")].map((i) => [i.dataset.f, i.value]))).filter((o) => Object.values(o).some((v) => v.trim())); });
    try {
      cand = await api(`/api/candidates/${id}`, { method: "PUT", json: payload });
      bootstrap.Modal.getInstance($("#editModal")).hide(); show(); toast("Candidate updated.");
    } catch (err) {
      const map = { full_name: "ef-name", email: "ef-email", phone: "ef-phone", total_experience_years: "ef-exp" };
      Object.entries(err.fields || {}).forEach(([k, msg]) => { const el = map[k] && $("#" + map[k]); if (el) { el.classList.add("is-invalid"); el.nextElementSibling.textContent = msg; } });
      toast(err.message, "error");
    }
  });
  api(`/api/candidates/${id}`).then((d) => { cand = d; show(); }).catch((e) => { root.innerHTML = `<p class="bad py-4">${esc(e.message)}</p>`; });
}

document.addEventListener("DOMContentLoaded", () => {
  const init = { dashboard: initDashboard, upload: initUpload, candidates: initCandidates, candidate: initCandidate }[document.body.dataset.page];
  if (init) init();
});
