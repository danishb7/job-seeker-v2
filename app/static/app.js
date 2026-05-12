(() => {
  const SECTION_ORDER = [
    "job_titles",
    "location",
    "search_domains",
    "work_mode",
    "salary",
    "company_type",
    "visa_requirements",
    "must_have",
    "nice_to_have",
    "exclude",
  ];
  const MD_SECTION_HEADING = {
    job_titles: "Job Titles",
    location: "Location",
    search_domains: "Search domains",
    work_mode: "Work Mode",
    salary: "Salary",
    company_type: "Company Type",
    visa_requirements: "Visa requirements",
    must_have: "Must-Have",
    nice_to_have: "Nice-to-Have",
    exclude: "Exclude",
  };
  const els = {
    btnSearch: document.getElementById("btn-search"), btnPrefs: document.getElementById("btn-prefs"), btnReload: document.getElementById("btn-reload"),
    btnDownload: document.getElementById("btn-download"), btnHistory: document.getElementById("btn-history"), statusBar: document.getElementById("status-bar"),
    loading: document.getElementById("loading"), empty: document.getElementById("empty"), controls: document.getElementById("controls"), results: document.getElementById("results"),
    chips: document.querySelectorAll(".chip"), sortBy: document.getElementById("sort-by"), modalPrefs: document.getElementById("modal-prefs"), modalHistory: document.getElementById("modal-history"),
    historyList: document.getElementById("history-list"), prefsMeta: document.getElementById("prefs-meta"), prefsExtraWrap: document.getElementById("prefs-extra-wrap"),
    btnSave: document.getElementById("btn-save"), btnSaveSearch: document.getElementById("btn-save-search"), btnCancel: document.getElementById("btn-cancel"), toast: document.getElementById("toast"),
  };
  const prefIds = { intro: "pref-intro", extra: "pref-extra", ...Object.fromEntries(SECTION_ORDER.map((k) => [k, `pref-${k}`])) };
  const state = { jobs: [], filter: "all", sort: "best", latestCsv: null, prefsOriginal: "" };
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const headingToKey = (name) => {
    const n = name.trim().toLowerCase().replace(/\s+/g, " ");
    const map = {
      "job titles": "job_titles",
      location: "location",
      "search domains": "search_domains",
      "work mode": "work_mode",
      salary: "salary",
      "company type": "company_type",
      "visa requirements": "visa_requirements",
      "visa requirement": "visa_requirements",
      "must-have": "must_have",
      "must have": "must_have",
      "nice-to-have": "nice_to_have",
      "nice to have": "nice_to_have",
      exclude: "exclude",
    };
    return map[n] || null;
  };
  function parsePrefsMarkdown(md) {
    const data = { intro: "", extra: "" }; SECTION_ORDER.forEach((k) => (data[k] = ""));
    let rest = (md || "").replace(/^\uFEFF/, "").replace(/^#\s+Job Search Preferences\s*\r?\n/i, "");
    const bq = rest.match(/^((?:>\s?[^\r\n]*(?:\r?\n|$))+)\s*/); if (bq) { data.intro = bq[1].split(/\r?\n/).map((l) => l.replace(/^>\s?/, "")).join("\n").trim(); rest = rest.slice(bq[0].length); }
    const headers = []; const re = /^##\s+(.+?)\s*$/gm; let m; while ((m = re.exec(rest))) headers.push({ title: m[1].trim(), headerEnd: m.index + m[0].length, index: m.index });
    const unknown = [];
    for (let i = 0; i < headers.length; i++) { const h = headers[i]; const body = rest.slice(h.headerEnd, i + 1 < headers.length ? headers[i + 1].index : rest.length).trim(); const key = headingToKey(h.title); if (key) data[key] = body; else unknown.push(`## ${h.title}\n\n${body}`); }
    data.extra = unknown.join("\n\n").trim(); return data;
  }
  function buildPrefsMarkdown(data) {
    let out = "# Job Search Preferences\n\n"; const intro = (data.intro || "").trim();
    if (intro) out += intro.split(/\r?\n/).map((l) => `> ${l}`).join("\n") + "\n\n";
    SECTION_ORDER.forEach((k) => { out += `## ${MD_SECTION_HEADING[k]}\n\n${(data[k] || "").trim()}\n\n`; });
    if ((data.extra || "").trim()) out += `${data.extra.trim()}\n`; return out.endsWith("\n") ? out : out + "\n";
  }
  const collectFormData = () => ({ intro: document.getElementById(prefIds.intro).value, extra: document.getElementById(prefIds.extra).value, ...Object.fromEntries(SECTION_ORDER.map((k) => [k, document.getElementById(prefIds[k]).value])) });
  function applyFormData(data) { document.getElementById(prefIds.intro).value = data.intro || ""; document.getElementById(prefIds.extra).value = data.extra || ""; SECTION_ORDER.forEach((k) => (document.getElementById(prefIds[k]).value = data[k] || "")); els.prefsExtraWrap.classList.toggle("hidden", !(data.extra || "").trim()); }
  let toastTimer = null;
  function toast(message, ms = 2200) { els.toast.textContent = message; els.toast.classList.remove("hidden"); requestAnimationFrame(() => els.toast.classList.add("show")); clearTimeout(toastTimer); toastTimer = setTimeout(() => { els.toast.classList.remove("show"); setTimeout(() => els.toast.classList.add("hidden"), 250); }, ms); }
  const showStatus = (html) => { if (!html) { els.statusBar.classList.add("hidden"); els.statusBar.innerHTML = ""; return; } els.statusBar.classList.remove("hidden"); els.statusBar.innerHTML = html; };
  const isPrefsDirty = () => buildPrefsMarkdown(collectFormData()) !== state.prefsOriginal;
  const updatePrefsMeta = () => { const md = buildPrefsMarkdown(collectFormData()); const dirty = md !== state.prefsOriginal ? " · unsaved changes" : ""; els.prefsMeta.textContent = `${md.split("\n").length} lines in file · ${md.length} chars${dirty}`; };
  const parseSalaryNumber = (raw) => { if (!raw) return -1; const matches = String(raw).match(/\$?\s*([\d,]+(?:\.\d+)?)\s*(k|K)?/g); if (!matches) return -1; return Math.max(...matches.map((m) => { const num = parseFloat(m.replace(/[^\d.]/g, "")); return /k/i.test(m) && num < 1000 ? num * 1000 : num; }).filter((n) => !Number.isNaN(n))); };
  const parseDate = (raw) => { if (!raw) return 0; const t = Date.parse(raw); if (!Number.isNaN(t)) return t; const m = String(raw).toLowerCase().match(/(\d+)\s*(day|hour|week|month)/); if (!m) return 0; const unitMs = { hour: 36e5, day: 864e5, week: 6048e5, month: 2628e6 }[m[2]] || 0; return Date.now() - parseInt(m[1], 10) * unitMs; };
  const matchesFilter = (job, filter) => filter === "all" || (filter === "remote" && (job.work_mode || "").toLowerCase().includes("remote")) || (filter === "hybrid" && (job.work_mode || "").toLowerCase().includes("hybrid")) || (filter === "nonprofit" && job.is_nonprofit_or_h1b_cap_exempt === true) || (filter === "hassalary" && !!(job.salary || "").trim());
  function renderCard(job) {
    const badges = []; if (job.location) badges.push(`<span class="badge location">${esc(job.location)}</span>`); if (job.work_mode) badges.push(`<span class="badge work-mode">${esc(job.work_mode)}</span>`); if (job.salary) badges.push(`<span class="badge salary">${esc(job.salary)}</span>`); if (job.is_nonprofit_or_h1b_cap_exempt === true) badges.push(`<span class="badge nonprofit">Non-profit / H1B-exempt</span>`);
    return `<article class="card"><div class="card-head"><div><h3>${esc(job.title || "Untitled role")}</h3><div class="company">${esc(job.company || "Unknown employer")}${job.source ? ` · ${esc(job.source)}` : ""}</div></div><div class="posted">${job.posted ? `Posted ${esc(job.posted)}` : ""}</div></div><div class="badges">${badges.join("")}</div>${job.why_match ? `<p class="why">${esc(job.why_match)}</p>` : ""}<div class="card-actions">${job.url ? `<a class="btn btn-secondary" target="_blank" rel="noopener" href="${esc(job.url)}">Open posting</a><button class="btn btn-ghost" data-copy="${esc(job.url)}">Copy link</button>` : `<span class="muted">No link provided</span>`}</div></article>`;
  }
  function render() {
    if (!state.jobs.length) { els.results.innerHTML = ""; els.controls.classList.add("hidden"); return; }
    const filtered = state.jobs.filter((j) => matchesFilter(j, state.filter));
    filtered.sort((a, b) => state.sort === "newest" ? parseDate(b.posted) - parseDate(a.posted) : state.sort === "salary" ? parseSalaryNumber(b.salary) - parseSalaryNumber(a.salary) : 0);
    els.controls.classList.remove("hidden");
    els.results.innerHTML = filtered.length ? filtered.map(renderCard).join("") : `<div class="empty">No jobs match this filter.</div>`;
    els.results.querySelectorAll("[data-copy]").forEach((btn) => btn.addEventListener("click", async () => { try { await navigator.clipboard.writeText(btn.dataset.copy); toast("Link copied"); } catch { toast("Couldn't copy"); } }));
  }

  const apiGetPrefs = async () => (await (await fetch("/api/preferences")).json()).content || "";
  const apiReloadPrefs = async () => (await (await fetch("/api/preferences/reload", { method: "POST" })).json()).content || "";
  const apiListResults = async () => (await (await fetch("/api/results")).json()).results || [];
  async function apiSavePrefs(content) { const res = await fetch("/api/preferences", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content }) }); if (!res.ok) throw new Error("Save failed"); }
  async function refreshHistoryList() { const items = await apiListResults(); els.btnHistory.classList.toggle("hidden", items.length === 0); els.historyList.innerHTML = items.length ? items.map((it) => `<li class="history-item"><div><div>${esc(it.filename)}</div><div class="muted">${esc(it.created_at)} · ${it.rows} rows · ${(it.size_bytes / 1024).toFixed(1)} KB</div></div><a class="btn btn-secondary" href="/api/results/${encodeURIComponent(it.filename)}">Download</a></li>`).join("") : "<li>No past runs yet.</li>"; }
  async function apiSearch() {
    els.empty.classList.add("hidden"); els.results.innerHTML = ""; els.controls.classList.add("hidden"); els.loading.classList.remove("hidden"); showStatus(""); els.btnSearch.disabled = true;
    try { const res = await fetch("/api/search", { method: "POST" }); if (!res.ok) throw new Error("Search failed"); const data = await res.json(); state.jobs = data.jobs || []; state.latestCsv = data.csv_filename || null; if (state.latestCsv) els.btnDownload.classList.remove("hidden"); showStatus(`${state.jobs.length} jobs found in ${data.elapsed_seconds}s using ${esc(data.model)}${state.latestCsv ? ` · Saved to results/${esc(state.latestCsv)}` : ""}`); if (!state.jobs.length) els.empty.classList.remove("hidden"); render(); await refreshHistoryList(); } catch (e) { showStatus(`Search failed: ${esc(e.message)}`); } finally { els.loading.classList.add("hidden"); els.btnSearch.disabled = false; }
  }

  async function openPrefsModal() { const content = await apiGetPrefs(); state.prefsOriginal = content; applyFormData(parsePrefsMarkdown(content)); updatePrefsMeta(); els.modalPrefs.classList.remove("hidden"); }
  const closePrefsModal = (force = false) => { if (!force && isPrefsDirty() && !confirm("Discard unsaved changes?")) return; els.modalPrefs.classList.add("hidden"); };
  const savePrefs = async () => { const md = buildPrefsMarkdown(collectFormData()); if (!md.trim()) return false; await apiSavePrefs(md); state.prefsOriginal = md; updatePrefsMeta(); toast("Saved"); return true; };
  const closeHistoryModal = () => els.modalHistory.classList.add("hidden");

  els.btnSearch.addEventListener("click", apiSearch); els.btnPrefs.addEventListener("click", openPrefsModal);
  els.btnReload.addEventListener("click", async () => { try { const content = await apiReloadPrefs(); state.prefsOriginal = content; if (!els.modalPrefs.classList.contains("hidden")) { applyFormData(parsePrefsMarkdown(content)); updatePrefsMeta(); } toast("Preferences reloaded from disk"); } catch { toast("Reload failed"); } });
  els.btnDownload.addEventListener("click", () => state.latestCsv && (window.location.href = `/api/results/${encodeURIComponent(state.latestCsv)}`));
  els.btnHistory.addEventListener("click", async () => { await refreshHistoryList(); els.modalHistory.classList.remove("hidden"); });
  els.chips.forEach((chip) => chip.addEventListener("click", () => { els.chips.forEach((c) => c.classList.remove("is-active")); chip.classList.add("is-active"); state.filter = chip.dataset.filter; render(); }));
  els.sortBy.addEventListener("change", (e) => { state.sort = e.target.value; render(); });
  els.btnSave.addEventListener("click", async () => { if (await savePrefs()) closePrefsModal(true); });
  els.btnSaveSearch.addEventListener("click", async () => { if (await savePrefs()) { closePrefsModal(true); apiSearch(); } });
  els.btnCancel.addEventListener("click", () => closePrefsModal(false));
  document.querySelectorAll("[data-close]").forEach((n) => n.addEventListener("click", () => (n.getAttribute("data-modal") === "history" ? closeHistoryModal() : closePrefsModal(false))));
  [prefIds.intro, prefIds.extra, ...SECTION_ORDER.map((k) => prefIds[k])].forEach((id) => { const e = document.getElementById(id); if (e) e.addEventListener("input", updatePrefsMeta); });
  document.addEventListener("keydown", (e) => {
    if (!els.modalHistory.classList.contains("hidden") && e.key === "Escape") { e.preventDefault(); closeHistoryModal(); return; }
    if (!els.modalPrefs.classList.contains("hidden")) { if (e.key === "Escape") { e.preventDefault(); closePrefsModal(false); } if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); savePrefs().then((ok) => ok && closePrefsModal(true)); } }
  });
  refreshHistoryList();
})();
