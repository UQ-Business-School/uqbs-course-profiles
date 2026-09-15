/* UQBS Course Profile Viewer — app.js
 *
 * Shared helpers + page-specific controllers. Vanilla JS, no build.
 * Data sources are relative to the site root:
 *   ./assets/manifest.json       -- lean index of all profiles
 *   ./profiles/{semester}/*.json -- full profile JSONs (loaded on demand)
 *   ./taxonomy/uqbs-programs.json -- program/major mappings
 */

// ---- shared ---------------------------------------------------------------
const STORE = {
  manifest: null,
  manifestAll: null,
  manifestLegacy: null,
  taxonomy: null,
  taxonomyAll: null,
  aol: null,
  loOverrides: null,
  teachingPeriods: null,
  selected: new Set(),   // course.file paths ticked for download
  filtered: [],          // current filtered+sorted list (set by render)
  renderFn: null,        // active browser's render function
};

// ---- edition config -------------------------------------------------------
// One codebase, two published editions. `window.SITE` is set by assets/site-config.js
// (the only file the dual-build swaps per edition). Falls back to the UQBS,
// self-contained defaults so local dev and tests behave as before.
//   edition : "uqbs" -> UQBS view, AoL/GA layers ON
//             "all"  -> All-UQ public view, AoL/GA layers OFF
//   dataBase: ""     -> bulk data (profile JSONs + big manifests) served same-origin
//             "https://host/base/" -> fetched cross-origin from that base, so a
//               light edition (e.g. UQBS on teach.business) needn't carry the data.
const SITE = (typeof window !== "undefined" && window.SITE) || { edition: "uqbs", dataBase: "", repoUrl: "", uqbsUrl: "", allUrl: "", reportEmail: "" };
const EDITION = SITE.edition === "all" ? "all" : "uqbs";
const DATA_BASE = (SITE.dataBase || "").replace(/\/+$/, "");

// URL for bulk/shared data. Same-origin when DATA_BASE is empty.
function dataUrl(rel) {
  const clean = String(rel).replace(/^\.?\//, "");
  return DATA_BASE ? `${DATA_BASE}/${clean}` : `./${clean}`;
}

// Everything the weekly scrape refreshes (the manifests, the program taxonomies, the
// LO overrides, the teaching periods) is read from the data host when one is set,
// so this hosted edition follows the scrape without a rebuild (2026-09-07; until
// then it shipped a frozen copy of the manifest and showed the 6 June scrape for
// three months). Only aol-status.json, which this edition alone carries, stays local.
const DATA_PATHS = {
  manifest: dataUrl("assets/manifest.json"),
  manifestAll: dataUrl("assets/manifest-all.json"),
  manifestLegacy: dataUrl("assets/manifest-legacy.json"),
  taxonomy: dataUrl("taxonomy/uqbs-programs.json"),
  taxonomyAll: dataUrl("taxonomy/all-programs.json"),
  aol: "./taxonomy/aol-status.json",
  loOverrides: dataUrl("taxonomy/lo-overrides.json"),
  teachingPeriods: dataUrl("taxonomy/teaching-periods.json"),
};

async function loadManifest() {
  if (STORE.manifest) return STORE.manifest;
  const res = await fetch(DATA_PATHS.manifest, { cache: "no-cache" });
  if (!res.ok) throw new Error(`Could not load manifest: ${res.status}`);
  STORE.manifest = await res.json();
  return STORE.manifest;
}

async function loadManifestAll() {
  if (STORE.manifestAll) return STORE.manifestAll;
  const res = await fetch(DATA_PATHS.manifestAll, { cache: "no-cache" });
  if (!res.ok) throw new Error(`Could not load full manifest: ${res.status}`);
  STORE.manifestAll = await res.json();
  return STORE.manifestAll;
}

// Legacy profile manifest (2009–S1 2024), kept separate from the live UQBS
// manifest. Loaded opt-in for the per-course timeline. Graceful fallback when
// absent (the timeline simply shows current-system offerings only).
async function loadManifestLegacy() {
  if (STORE.manifestLegacy) return STORE.manifestLegacy;
  try {
    const res = await fetch(DATA_PATHS.manifestLegacy, { cache: "no-cache" });
    if (!res.ok) { STORE.manifestLegacy = { periods: {} }; return STORE.manifestLegacy; }
    STORE.manifestLegacy = await res.json();
  } catch (_e) {
    STORE.manifestLegacy = { periods: {} };
  }
  return STORE.manifestLegacy;
}

// Flatten a legacy manifest's period buckets into a single offering list.
function getLegacyCourses(manifestLegacy) {
  const out = [];
  const periods = (manifestLegacy && manifestLegacy.periods) || {};
  for (const key of Object.keys(periods)) {
    for (const entry of periods[key]) out.push(entry);
  }
  return out;
}

async function loadTaxonomy() {
  if (STORE.taxonomy) return STORE.taxonomy;
  const res = await fetch(DATA_PATHS.taxonomy, { cache: "no-cache" });
  if (!res.ok) throw new Error(`Could not load taxonomy: ${res.status}`);
  STORE.taxonomy = await res.json();
  return STORE.taxonomy;
}

// All-of-UQ program taxonomy (all-programs.json) for the All-UQ dashboard.
async function loadTaxonomyAll() {
  if (STORE.taxonomyAll) return STORE.taxonomyAll;
  const res = await fetch(DATA_PATHS.taxonomyAll, { cache: "no-cache" });
  if (!res.ok) throw new Error(`Could not load all-UQ taxonomy: ${res.status}`);
  STORE.taxonomyAll = await res.json();
  return STORE.taxonomyAll;
}

async function loadAol() {
  if (STORE.aol) return STORE.aol;
  const res = await fetch(DATA_PATHS.aol, { cache: "no-cache" });
  if (!res.ok) { STORE.aol = { semesters: {} }; return STORE.aol; }
  STORE.aol = await res.json();
  return STORE.aol;
}

// Manual LO-to-assessment override overlay (patches the Drupal ECP bug that
// drops LO mappings, fully or partially). Graceful fallback when absent.
async function loadLoOverrides() {
  if (STORE.loOverrides) return STORE.loOverrides;
  const res = await fetch(DATA_PATHS.loOverrides, { cache: "no-cache" });
  if (!res.ok) { STORE.loOverrides = { overrides: [] }; return STORE.loOverrides; }
  STORE.loOverrides = await res.json();
  return STORE.loOverrides;
}

// Teaching-period registry (taxonomy/teaching-periods.json) — semester-code
// metadata incl. summer/medical special periods. Graceful fallback when absent.
async function loadTeachingPeriods() {
  if (STORE.teachingPeriods) return STORE.teachingPeriods;
  const res = await fetch(DATA_PATHS.teachingPeriods, { cache: "no-cache" });
  if (!res.ok) { STORE.teachingPeriods = { periods: {} }; return STORE.teachingPeriods; }
  STORE.teachingPeriods = await res.json();
  return STORE.teachingPeriods;
}

// Get AoL entries for a specific course code (across all semesters, or for a specific semester)
function getAolForCourse(aol, courseCode, semesterCode) {
  if (!aol || !aol.semesters) return [];
  const entries = [];
  for (const [sem, data] of Object.entries(aol.semesters)) {
    if (semesterCode && sem !== semesterCode) continue;
    for (const e of (data.entries || [])) {
      if (e.course_code === courseCode) entries.push({ ...e, semester_code: sem, semester_label: data.label });
    }
  }
  return entries;
}

// Status display config
// Mirrors the register's Lists tab and scraper/import_aol.py STATUSES. Order is
// the ladder: change the register first, then import_aol.py, then this.
const AOL_STATUS = {
  na:                         { label: "N/A",                         icon: "🚫", cls: "aol-na" },
  tbd:                        { label: "TBD",                         icon: "📋", cls: "aol-tbd" },
  identified:                 { label: "Identified",                  icon: "🔍", cls: "aol-identified" },
  rubric_in_dev:              { label: "Rubric in development",       icon: "🔨", cls: "aol-rubric-dev" },
  partial_mapping:            { label: "Partial mapping",             icon: "◐",  cls: "aol-partial" },
  built_awaiting_coordinator: { label: "Built, awaiting coordinator", icon: "📨", cls: "aol-built" },
  approved_not_installed:     { label: "Approved, not installed",     icon: "👍", cls: "aol-approved" },
  awaiting_ld_check:          { label: "Awaiting LD check",           icon: "👀", cls: "aol-awaiting-ld" },
  active:                     { label: "Active",                      icon: "✅", cls: "aol-active" },
};

function aolStatusChip(status) {
  const s = AOL_STATUS[status] || { label: status, icon: "?", cls: "aol-unknown" };
  return `<span class="aol-chip ${s.cls}" title="${escapeHtml(s.label)}">${s.icon} ${escapeHtml(s.label)}</span>`;
}

function aolGaChip(ga) {
  return `<span class="aol-ga-chip" title="${escapeHtml(ga)}">${escapeHtml(ga)}</span>`;
}

async function loadCourseJson(relPath) {
  const res = await fetch(dataUrl(relPath), { cache: "no-cache" });
  if (!res.ok) throw new Error(`Could not load ${relPath}: ${res.status}`);
  return res.json();
}

function getAllCourses(manifest) {
  // Flatten all semesters into one list of {..., semester_code}
  const out = [];
  for (const [sem, entries] of Object.entries(manifest.semesters || {})) {
    for (const e of entries) {
      out.push({ ...e, semester_code: e.semester_code || sem });
    }
  }
  return out;
}

function uniqueSorted(values) {
  return Array.from(new Set(values.filter(Boolean))).sort((a, b) => String(a).localeCompare(String(b)));
}

function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

// Parse study_period into a short label, e.g. "Semester 1, 2026 (23/02/...)" → "S1 2026".
// Falls back to semester_code if study_period is missing.
function semesterLabel(course) {
  const sp = course.study_period || "";
  const m = sp.match(/Semester\s+(\d),?\s+(\d{4})/i);
  if (m) return `S${m[1]} ${m[2]}`;
  const sm = sp.match(/Summer\s+Semester,?\s+(\d{4})/i);
  if (sm) return `Sum ${sm[1]}`;
  // Fallback: derive from semester_code via the teaching-period registry
  // (taxonomy/teaching-periods.json), which knows summer and special periods.
  const code = course.semester_code || "";
  const reg = STORE.teachingPeriods && STORE.teachingPeriods.periods;
  if (reg && reg[code] && reg[code].short) return reg[code].short;
  // Last resort: legacy hardcoded map (kept for registry-load failures)
  const codeMap = {
    "7460": "S2 2024", "7480": "Sum 2025", "7520": "S1 2025",
    "7560": "S2 2025", "7580": "Sum 2026", "7620": "S1 2026",
    "7660": "S2 2026", "7700": "S1 2027", "7740": "S2 2027",
  };
  return codeMap[code] || code;
}

// Chronological sort key for an offering, spanning both eras. Returns a
// comparable string like "2009.1" (year.period-ordinal). Works for current
// profiles (study_period carries the year) and legacy profiles alike, so a
// course's offerings line up oldest→newest regardless of which system they
// came from. Summer is ordered before its Semester 1 (it runs Nov–Feb).
function offeringChronKey(course) {
  const sp = course.study_period || "";
  let year = course.year;
  let periodOrd = 5; // unknown sorts last within a year
  let m = sp.match(/Semester\s+(\d),?\s+(\d{4})/i);
  if (m) { year = year || +m[2]; periodOrd = +m[1] === 1 ? 2 : 3; }
  else {
    m = sp.match(/Summer\s+Semester,?\s+(\d{4})/i);
    if (m) { year = year || +m[1]; periodOrd = 1; }
  }
  // Legacy entries carry explicit year/period fields as a fallback
  if (course.period) {
    if (/Semester 1/i.test(course.period)) periodOrd = 2;
    else if (/Semester 2/i.test(course.period)) periodOrd = 3;
    else if (/Summer/i.test(course.period)) periodOrd = 1;
  }
  return `${year || 0}.${periodOrd}`;
}

// Extract the 4-letter faculty prefix from a course code (e.g. "MGTS1601" → "MGTS").
// Used for Fun-theme faculty-colour coding on table rows.
function coursePrefix(code) {
  if (!code) return "";
  const m = String(code).match(/^([A-Z]{3,4})/);
  return m ? m[1] : "";
}

// Normalise a learning-outcome code for display. Source data sometimes has
// `lo.number = "LO1."` (already prefixed with "LO" and trailing period) and
// sometimes `lo.number = 1` (bare). Produce a canonical "LO1" form.
function loDisplayCode(lo) {
  if (!lo) return "";
  if (lo.code) return String(lo.code).trim().replace(/\.$/, "");
  const n = lo.number;
  if (n == null) return "";
  const s = String(n).trim().replace(/\.$/, "");
  // If already starts with "LO" (case-insensitive), normalise to uppercase
  if (/^lo\d+$/i.test(s)) return s.toUpperCase();
  // Otherwise prepend "LO"
  return `LO${s}`;
}

// Parse a "learning_outcomes_assessed" string into ["LO1","LO2",…].
// Handles variations: "L.O. 1", "LO1", "LO 1", "L01" (zero-typo), "1".
function parseLoRefs(s) {
  if (!s) return [];
  const text = String(s);
  const nums = new Set();
  // Pattern A: L + (O or 0) + optional dot + optional space + digits
  //   matches "LO1", "LO.1", "L.O.1", "L O 1", "L01", "L0.1"
  const reA = /L\.?[O0]\.?\s*(\d+)/gi;
  // Pattern B: bare numbers preceded by a comma/space/start (for strings
  //   like "1, 2, 3") — only used if Pattern A matched nothing
  const reB = /(?:^|[,;\s])(\d+)(?=[,;\s]|$)/g;
  let m;
  while ((m = reA.exec(text)) !== null) nums.add(m[1]);
  if (nums.size === 0) {
    while ((m = reB.exec(text)) !== null) nums.add(m[1]);
  }
  // Preserve first-seen order
  return Array.from(nums).map(n => `LO${n}`);
}

// Build a lookup { assessmentTitle → [LO1, LO2, …] } from assessment_details.
function buildAssessmentLoMap(c) {
  const map = {};
  if (!c || !Array.isArray(c.assessment_details)) return map;
  for (const d of c.assessment_details) {
    const title = (d && d.title ? String(d.title).trim() : "");
    if (!title) continue;
    const refs = parseLoRefs(d.learning_outcomes_assessed || d.learning_outcomes);
    if (refs.length) map[title] = refs;
  }
  return map;
}

// Normalise an assessment title for matching (case/space-insensitive).
// Mirrors _norm_title() in scraper/import_lo_overrides.py.
function normTitle(t) {
  return String(t || "").trim().replace(/\s+/g, " ").toLowerCase();
}

// Resolve the manual LO overrides for a course offering into a lookup keyed by
// normalised assessment title: { normTitle → { los:[…], notes } }.
// Precedence (most specific wins): an override scoped to this exact SI-NET
// class (class_number) beats an exact-semester override, which beats a
// blank-semester (all-semesters) override for the same assessment.
// Class-scoped overrides exist because parallel deliveries (MBA intensive vs
// standard, in-person vs external) can share an assessment title but map
// different LOs. A class-scoped entry never applies to a different class.
function getLoOverrideMap(courseCode, semesterCode, classCode) {
  const ov = STORE.loOverrides;
  if (!ov || !Array.isArray(ov.overrides) || !courseCode) return {};
  const blank = {}, exact = {}, exactClass = {};
  for (const o of ov.overrides) {
    if (o.course_code !== courseCode) continue;
    const los = Array.isArray(o.learning_outcomes) ? o.learning_outcomes : [];
    if (!los.length) continue;
    const rec = { los, notes: o.notes || null, source: o.source || "jac" };
    const nt = normTitle(o.assessment_title);
    const semMatches = o.semester_code && semesterCode && o.semester_code === semesterCode;
    if (o.class_number) {
      // Scoped to one class: applies only when both class and semester match.
      if (semMatches && classCode && String(o.class_number) === String(classCode)) {
        exactClass[nt] = rec;
      }
    } else if (semMatches) {
      exact[nt] = rec;
    } else if (!o.semester_code) {
      blank[nt] = rec;
    }
  }
  // most specific last so it wins the merge
  return Object.assign({}, blank, exact, exactClass);
}

// Produce the COMPLETE record for a course: the scraped profile with any
// missing/incomplete LO mappings restored from Jac (the authored curriculum
// record). Used by the JSON downloads so every user-facing surface serves
// complete data. Restored fields carry a provenance marker; the stored
// profiles/ JSONs remain raw ingestion (what UQ's published page contains).
function completeCourseJson(c) {
  const ovMap = getLoOverrideMap(c.course_code, c.semester_code, c.class_code);
  if (!Object.keys(ovMap).length) return c;
  const copy = JSON.parse(JSON.stringify(c));
  const restored = [];
  for (const d of (copy.assessment_details || [])) {
    const ov = ovMap[normTitle(d.title)];
    if (!ov) continue;
    d.learning_outcomes_assessed = ov.los.join(", ");
    d.learning_outcomes_assessed_source = "jac";
    restored.push((d.title || "").trim());
  }
  if (restored.length) {
    copy._lo_mapping_provenance = {
      note: "LO-to-assessment mappings for the assessments listed were restored from Jac (curriculum.uq.edu.au), the authored curriculum record. UQ's published course profile omits them due to a publishing fault.",
      restored_from_jac: restored,
    };
  }
  return copy;
}

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString("en-AU", { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch { return iso; }
}

function getQueryParam(name) {
  const p = new URLSearchParams(window.location.search);
  return p.get(name);
}

// Given a course code (e.g. ACCT1101) and taxonomy, return all program roles
function programRolesFor(code, taxonomy) {
  if (!taxonomy || !taxonomy.course_programs) return [];
  return taxonomy.course_programs[code] || [];
}

// Stable colour (hue 0-360) per program, so chips are consistent for a program
// and visually distinct between programs. Curated hues for the main programs;
// a spread hash covers anything else.
const PROGRAM_HUE = {
  BBusMan: 210, BCom: 280, BAB: 330, BAFE: 165, BTHEM: 30,
  MBA: 0, MBus: 48, MCom: 190, MBusAn: 100, MEI: 255,
  BBusManHons: 225, BComHons: 295, MFIM: 140, MTHEM: 15,
  GCBus: 60, GCFIM: 120, GCTHEM: 45, GCBusAn: 85, GCBusAdmin: 200,
  GCCom: 300, GCEI: 240,
};
function hueForProgram(code) {
  if (PROGRAM_HUE[code] != null) return PROGRAM_HUE[code];
  let h = 0;
  const s = String(code);
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return Math.round((h * 137.508) % 360);
}

// ---- export helpers -------------------------------------------------------

// Convert incidental HTML (from scraper-stripped fields) to plain text.
function htmlToText(html) {
  if (!html) return "";
  let t = String(html);
  t = t.replace(/<br\s*\/?>/gi, "\n");
  t = t.replace(/<\/p>/gi, "\n\n");
  t = t.replace(/<\/li>/gi, "\n");
  t = t.replace(/<\/div>/gi, "\n");
  t = t.replace(/<[^>]+>/g, "");
  t = t.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">");
  t = t.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&nbsp;/g, " ");
  return t.replace(/\n{3,}/g, "\n\n").trim();
}

function htmlToMarkdown(html) {
  if (!html) return "";
  let md = String(html);
  md = md.replace(/<strong>([\s\S]*?)<\/strong>/gi, "**$1**");
  md = md.replace(/<b>([\s\S]*?)<\/b>/gi, "**$1**");
  md = md.replace(/<em>([\s\S]*?)<\/em>/gi, "*$1*");
  md = md.replace(/<i>([\s\S]*?)<\/i>/gi, "*$1*");
  md = md.replace(/<a\s+href="([^"]*)"[^>]*>([\s\S]*?)<\/a>/gi, "[$2]($1)");
  md = md.replace(/<li>([\s\S]*?)<\/li>/gi, "- $1\n");
  md = md.replace(/<\/p>/gi, "\n\n");
  md = md.replace(/<br\s*\/?>/gi, "\n");
  md = md.replace(/<[^>]+>/g, "");
  md = md.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">");
  md = md.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&nbsp;/g, " ");
  return md.replace(/\n{3,}/g, "\n\n").trim();
}

function stripLoSuffix(topic) {
  return String(topic || "").replace(/\s*Learning outcomes?:.*$/i, "").trim();
}

function safeFilename(c, ext) {
  const parts = [c.course_code, c.class_code, c.semester_code].filter(Boolean);
  return `${parts.join("-") || "course"}.${ext}`;
}

// Trigger browser download of a text/bytes blob.
function downloadBlob(content, filename, mimeType) {
  const blob = content instanceof Blob ? content : new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}

// Generate a Markdown document from a full course JSON.
function buildCourseMarkdown(c, taxonomy) {
  const lines = [];
  const ovMap = getLoOverrideMap(c.course_code, c.semester_code, c.class_code);
  lines.push(`# ${c.course_code} — ${c.course_title || ""}`);
  lines.push("");
  const metaRows = [
    ["Full code", c.full_course_code],
    ["Study period", c.study_period],
    ["Study level", c.study_level],
    ["Units", c.units],
    ["Attendance mode", c.attendance_mode],
    ["Location", c.location],
    ["Coordinating unit", c.coordinating_unit],
    ["Administrative campus", c.administrative_campus],
    ["Course profile URL", c.url],
    ["Scraped", c.scraped_at],
  ].filter(([, v]) => v);
  for (const [k, v] of metaRows) lines.push(`- **${k}:** ${v}`);

  const roles = taxonomy ? programRolesFor(c.course_code, taxonomy) : [];
  if (roles.length) {
    lines.push("", "## Program mapping", "");
    for (const r of roles) {
      lines.push(`- **${r.program}** (${r.program_name || ""}): ${r.role || ""}`);
    }
  }

  if (c.course_description) {
    lines.push("", "## Course description", "", htmlToMarkdown(c.course_description));
  }
  if (c.course_aims) {
    lines.push("", "## Course aims", "", htmlToMarkdown(c.course_aims));
  }

  if (c.requirements && typeof c.requirements === "object") {
    const hasAny = Object.values(c.requirements).some(v => v && (Array.isArray(v) ? v.length : String(v).trim()));
    if (hasAny) {
      lines.push("", "## Requirements");
      for (const [key, label] of [
        ["prerequisites", "Prerequisites"],
        ["incompatible", "Incompatible courses"],
        ["companions", "Companions"],
        ["recommended_prerequisites", "Recommended prerequisites"],
        ["restrictions", "Restrictions"],
      ]) {
        const v = c.requirements[key];
        if (!v) continue;
        const items = Array.isArray(v) ? v : [v];
        if (!items.length) continue;
        lines.push("", `**${label}**`, "");
        for (const item of items) lines.push(`- ${String(item)}`);
      }
    }
  }

  if (Array.isArray(c.learning_outcomes) && c.learning_outcomes.length) {
    lines.push("", "## Course learning outcomes", "");
    for (const lo of c.learning_outcomes) {
      const code = loDisplayCode(lo);
      lines.push(`- **${code}** ${lo.description || ""}`);
    }
  }

  if (Array.isArray(c.assessment_summary) && c.assessment_summary.length) {
    lines.push("", "## Assessment summary", "");
    lines.push("| # | Task | Category | Weight | Due |");
    lines.push("|---|------|----------|--------|-----|");
    c.assessment_summary.forEach((a, i) => {
      const title = (a.title || "").replace(/\|/g, "/");
      const cat = (a.category || a.type || "").replace(/\|/g, "/");
      const w = (a.weighting || a.weight || "").replace(/\|/g, "/");
      const due = (a.due_date || a.due || "").replace(/\|/g, "/");
      lines.push(`| ${i + 1} | ${title} | ${cat} | ${w} | ${due} |`);
    });
  }

  if (Array.isArray(c.assessment_details) && c.assessment_details.length) {
    lines.push("", "## Assessment details", "");
    c.assessment_details.forEach((a, i) => {
      lines.push(`### ${i + 1}. ${a.title || a.name || "Assessment"}`);
      lines.push("");
      const meta = [];
      if (a.weighting || a.weight) meta.push(`**Weight:** ${a.weighting || a.weight}`);
      if (a.due_date || a.due) meta.push(`**Due:** ${a.due_date || a.due}`);
      if (a.category || a.type) meta.push(`**Category:** ${a.category || a.type}`);
      if (a.mode) meta.push(`**Mode:** ${a.mode}`);
      if (a.other_conditions) meta.push(`**Conditions:** ${a.other_conditions}`);
      if (meta.length) { lines.push(meta.join(" · ")); lines.push(""); }
      const ov = ovMap[normTitle(a.title)];
      const lo = ov ? ov.los : (a.learning_outcomes_assessed != null ? a.learning_outcomes_assessed : a.learning_outcomes);
      if (lo) {
        const loStr = Array.isArray(lo) ? lo.join(", ") : String(lo);
        if (loStr) { lines.push(`**Linked LOs:** ${loStr}${ov ? " _(from Jac, the authored curriculum record — omitted from the published profile)_" : ""}`); lines.push(""); }
      }
      if (Array.isArray(a.special_indicators) && a.special_indicators.length) {
        lines.push(`**Indicators:** ${a.special_indicators.join(", ")}`); lines.push("");
      }
      for (const [key, label] of [
        ["task_description", "Task description"],
        ["task", "Task"],
        ["exam_details", "Exam details"],
        ["submission_guidelines", "Submission guidelines"],
        ["deferral_or_extension", "Deferral or extension"],
        ["late_submission", "Late submission"],
        ["marking_criteria", "Marking criteria"],
        ["ai_statement", "AI / academic integrity"],
      ]) {
        const v = a[key];
        if (!v) continue;
        lines.push(`#### ${label}`, "");
        if (Array.isArray(v)) v.forEach(x => lines.push(`- ${String(x)}`));
        else lines.push(htmlToMarkdown(String(v)));
        lines.push("");
      }
      lines.push("---", "");
    });
  }

  if (Array.isArray(c.learning_activities) && c.learning_activities.length) {
    lines.push("", "## Weekly learning activities", "");
    lines.push("| Period | Type | Topic | LOs |");
    lines.push("|--------|------|-------|-----|");
    for (const la of c.learning_activities) {
      const period = (la.learning_period || "").replace(/\|/g, "/").replace(/\n/g, " ");
      const type = (la.activity_type || "").replace(/\|/g, "/");
      const topic = stripLoSuffix(la.topic).replace(/\|/g, "/").replace(/\n/g, " ");
      const los = Array.isArray(la.learning_outcomes) ? la.learning_outcomes.join(", ") : (la.learning_outcomes || "");
      lines.push(`| ${period} | ${type} | ${topic} | ${los} |`);
    }
  }

  if (c.learning_resources && typeof c.learning_resources === "object") {
    const entries = Object.entries(c.learning_resources).filter(([, v]) => v);
    if (entries.length) {
      lines.push("", "## Learning resources", "");
      for (const [k, v] of entries) {
        const label = k.replace(/_/g, " ").replace(/\b\w/g, s => s.toUpperCase());
        lines.push(`**${label}**`, "");
        if (Array.isArray(v)) v.forEach(x => lines.push(`- ${String(x)}`));
        else lines.push(htmlToMarkdown(String(v)));
        lines.push("");
      }
    }
  } else if (typeof c.learning_resources === "string" && c.learning_resources.trim()) {
    lines.push("", "## Learning resources", "", htmlToMarkdown(c.learning_resources));
  }

  if (c.timetable) {
    lines.push("", "## Timetable", "", htmlToMarkdown(String(c.timetable)));
  }

  if (Array.isArray(c.course_contacts) && c.course_contacts.length) {
    lines.push("", "## Course contacts", "");
    for (const s of c.course_contacts) {
      const bits = [s.name, s.role, s.email].filter(Boolean);
      lines.push(`- ${bits.join(" — ")}`);
    }
  }
  if (Array.isArray(c.course_staff) && c.course_staff.length) {
    lines.push("", "## Course staff", "");
    for (const s of c.course_staff) {
      const bits = [s.name, s.role, s.email].filter(Boolean);
      lines.push(`- ${bits.join(" — ")}`);
    }
  }

  if (c.policies_and_procedures) {
    lines.push("", "## Policies and procedures", "", htmlToMarkdown(String(c.policies_and_procedures)));
  }

  lines.push("", "---", "", `*Generated ${new Date().toLocaleDateString("en-AU")} from the [UQBS Course Profile Viewer](https://uq-business-school.github.io/uqbs-course-profiles/).*`);
  return lines.join("\n");
}

// Build a standalone HTML document optimised for print-to-PDF.
function buildPrintableHtml(c, taxonomy) {
  const esc = escapeHtml;
  const ovMap = getLoOverrideMap(c.course_code, c.semester_code, c.class_code);
  const roles = taxonomy ? programRolesFor(c.course_code, taxonomy) : [];
  const progLine = roles.length
    ? roles.map(r => `${esc(r.program)} (${esc(r.role || "")})`).join(" · ")
    : "";

  const parts = [];
  parts.push(`<!DOCTYPE html><html lang="en-AU"><head><meta charset="utf-8">
<title>${esc(c.course_code)} — ${esc(c.course_title || "")}</title>
<style>
  @page { size: A4; margin: 18mm 16mm; }
  body { font-family: Georgia, 'Times New Roman', serif; color: #222; font-size: 11pt; line-height: 1.5; max-width: 780px; margin: 0 auto; padding: 16px; }
  h1 { color: #51247A; font-size: 20pt; margin: 0 0 4px; }
  h2 { color: #51247A; font-size: 14pt; border-bottom: 2px solid #51247A; padding-bottom: 4px; margin: 22px 0 10px; }
  h3 { font-size: 12pt; margin: 16px 0 6px; }
  h4 { font-size: 11pt; color: #51247A; margin: 12px 0 4px; }
  .meta { color: #555; font-size: 10pt; margin-bottom: 6px; }
  .prog { background: #f6f0fa; border-left: 3px solid #BB9237; padding: 8px 12px; margin: 8px 0 14px; font-size: 10pt; }
  dl.kv { display: grid; grid-template-columns: max-content 1fr; gap: 4px 12px; margin: 8px 0 16px; font-size: 10pt; }
  dl.kv dt { font-weight: bold; color: #51247A; }
  table { width: 100%; border-collapse: collapse; font-size: 10pt; margin: 8px 0 14px; }
  th { background: #51247A; color: #fff; padding: 6px 8px; text-align: left; font-size: 10pt; }
  td { padding: 6px 8px; border-bottom: 1px solid #eee; vertical-align: top; }
  tr:nth-child(even) td { background: #faf7fd; }
  .assessment { border: 1px solid #ddd; border-radius: 6px; padding: 14px; margin-bottom: 12px; page-break-inside: avoid; }
  .footer { margin-top: 28px; font-size: 9pt; color: #888; border-top: 1px solid #ddd; padding-top: 8px; }
  ul, ol { margin: 6px 0 10px; padding-left: 22px; }
  li { margin-bottom: 3px; }
  a { color: #51247A; }
</style></head><body>`);

  parts.push(`<h1>${esc(c.course_code)} — ${esc(c.course_title || "")}</h1>`);
  const metaBits = [c.full_course_code, c.study_period, c.study_level, c.attendance_mode, c.location, c.units]
    .filter(Boolean).map(esc).join(" · ");
  if (metaBits) parts.push(`<div class="meta">${metaBits}</div>`);
  if (progLine) parts.push(`<div class="prog"><b>Program mapping:</b> ${progLine}</div>`);

  const over = [
    ["Coordinating unit", c.coordinating_unit],
    ["Administrative campus", c.administrative_campus],
    ["Source", c.url ? `<a href="${esc(c.url)}">${esc(c.url)}</a>` : null],
    ["Scraped", c.scraped_at],
  ].filter(([, v]) => v);
  if (over.length) {
    parts.push(`<dl class="kv">${over.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${k === "Source" ? v : esc(v)}</dd>`).join("")}</dl>`);
  }

  if (c.course_description) {
    parts.push(`<h2>Course description</h2><div>${renderLongText(c.course_description)}</div>`);
  }
  if (c.course_aims) {
    parts.push(`<h2>Course aims</h2><div>${renderLongText(c.course_aims)}</div>`);
  }

  if (c.requirements && typeof c.requirements === "object") {
    const rows = [];
    for (const [key, label] of [
      ["prerequisites", "Prerequisites"],
      ["incompatible", "Incompatible courses"],
      ["companions", "Companions"],
      ["recommended_prerequisites", "Recommended prerequisites"],
      ["restrictions", "Restrictions"],
    ]) {
      const v = c.requirements[key];
      if (!v) continue;
      if (Array.isArray(v) && v.length) rows.push(`<dt>${esc(label)}</dt><dd>${v.map(x => esc(String(x))).join("<br>")}</dd>`);
      else if (typeof v === "string" && v.trim()) rows.push(`<dt>${esc(label)}</dt><dd>${esc(v)}</dd>`);
    }
    if (rows.length) parts.push(`<h2>Requirements</h2><dl class="kv">${rows.join("")}</dl>`);
  }

  if (Array.isArray(c.learning_outcomes) && c.learning_outcomes.length) {
    parts.push(`<h2>Learning outcomes</h2><ol>`);
    for (const lo of c.learning_outcomes) {
      const code = loDisplayCode(lo);
      parts.push(`<li><b>${esc(code)}</b> ${esc(lo.description || "")}</li>`);
    }
    parts.push(`</ol>`);
  }

  if (Array.isArray(c.assessment_summary) && c.assessment_summary.length) {
    parts.push(`<h2>Assessment summary</h2><table><thead><tr><th>#</th><th>Task</th><th>Category</th><th>Weight</th><th>Due</th></tr></thead><tbody>`);
    c.assessment_summary.forEach((a, i) => {
      parts.push(`<tr><td>${i + 1}</td><td><b>${esc(a.title || "")}</b></td><td>${esc(a.category || a.type || "")}</td><td>${esc(a.weighting || a.weight || "")}</td><td>${esc(a.due_date || a.due || "")}</td></tr>`);
    });
    parts.push(`</tbody></table>`);
  }

  if (Array.isArray(c.assessment_details) && c.assessment_details.length) {
    parts.push(`<h2>Assessment details</h2>`);
    c.assessment_details.forEach((a, i) => {
      parts.push(`<div class="assessment"><h3>${i + 1}. ${esc(a.title || "Assessment")}</h3>`);
      const m = [];
      if (a.weighting || a.weight) m.push(`<b>Weight:</b> ${esc(a.weighting || a.weight)}`);
      if (a.due_date || a.due) m.push(`<b>Due:</b> ${esc(a.due_date || a.due)}`);
      if (a.category || a.type) m.push(`<b>Category:</b> ${esc(a.category || a.type)}`);
      if (a.mode) m.push(`<b>Mode:</b> ${esc(a.mode)}`);
      if (a.other_conditions) m.push(`<b>Conditions:</b> ${esc(a.other_conditions)}`);
      if (m.length) parts.push(`<p>${m.join(" · ")}</p>`);
      const ov = ovMap[normTitle(a.title)];
      const lo = ov ? ov.los : (a.learning_outcomes_assessed != null ? a.learning_outcomes_assessed : a.learning_outcomes);
      if (lo) {
        const loStr = Array.isArray(lo) ? lo.join(", ") : String(lo);
        if (loStr) parts.push(`<p><b>Linked LOs:</b> ${esc(loStr)}${ov ? " (from Jac, the authored curriculum record — omitted from the published profile)" : ""}</p>`);
      }
      for (const [key, label] of [
        ["task_description", "Task description"],
        ["task", "Task"],
        ["exam_details", "Exam details"],
        ["submission_guidelines", "Submission guidelines"],
        ["deferral_or_extension", "Deferral or extension"],
        ["late_submission", "Late submission"],
        ["marking_criteria", "Marking criteria"],
        ["ai_statement", "AI / academic integrity"],
      ]) {
        const v = a[key];
        if (!v) continue;
        if (Array.isArray(v)) parts.push(`<h4>${esc(label)}</h4><ul>${v.map(x => `<li>${esc(String(x))}</li>`).join("")}</ul>`);
        else parts.push(`<h4>${esc(label)}</h4>${renderLongText(String(v))}`);
      }
      parts.push(`</div>`);
    });
  }

  if (Array.isArray(c.learning_activities) && c.learning_activities.length) {
    parts.push(`<h2>Weekly learning activities</h2><table><thead><tr><th>Period</th><th>Type</th><th>Topic</th><th>LOs</th></tr></thead><tbody>`);
    for (const la of c.learning_activities) {
      const topic = stripLoSuffix(la.topic);
      const los = Array.isArray(la.learning_outcomes) ? la.learning_outcomes.join(", ") : (la.learning_outcomes || "");
      parts.push(`<tr><td>${esc(la.learning_period || "")}</td><td>${esc(la.activity_type || "")}</td><td>${esc(topic)}</td><td>${esc(los)}</td></tr>`);
    }
    parts.push(`</tbody></table>`);
  }

  if (c.learning_resources && typeof c.learning_resources === "object") {
    const rows = [];
    for (const [k, v] of Object.entries(c.learning_resources)) {
      if (!v) continue;
      const label = k.replace(/_/g, " ").replace(/\b\w/g, s => s.toUpperCase());
      if (Array.isArray(v)) rows.push(`<dt>${esc(label)}</dt><dd>${v.map(x => esc(String(x))).join("<br>")}</dd>`);
      else rows.push(`<dt>${esc(label)}</dt><dd>${renderLongText(String(v))}</dd>`);
    }
    if (rows.length) parts.push(`<h2>Learning resources</h2><dl class="kv">${rows.join("")}</dl>`);
  } else if (typeof c.learning_resources === "string" && c.learning_resources.trim()) {
    parts.push(`<h2>Learning resources</h2><div>${renderLongText(c.learning_resources)}</div>`);
  }

  if (c.timetable) parts.push(`<h2>Timetable</h2><div>${renderLongText(String(c.timetable))}</div>`);

  const staffRender = list => `<ul>${list.map(s => `<li><b>${esc(s.name || "")}</b>${s.role ? ` — ${esc(s.role)}` : ""}${s.email ? ` — <a href="mailto:${esc(s.email)}">${esc(s.email)}</a>` : ""}</li>`).join("")}</ul>`;
  if (Array.isArray(c.course_contacts) && c.course_contacts.length) parts.push(`<h2>Course contacts</h2>${staffRender(c.course_contacts)}`);
  if (Array.isArray(c.course_staff) && c.course_staff.length) parts.push(`<h2>Course staff</h2>${staffRender(c.course_staff)}`);

  if (c.policies_and_procedures) parts.push(`<h2>Policies and procedures</h2><div>${renderLongText(String(c.policies_and_procedures))}</div>`);

  parts.push(`<div class="footer">Generated ${esc(new Date().toLocaleDateString("en-AU"))} from the UQBS Course Profile Viewer · <a href="https://uq-business-school.github.io/uqbs-course-profiles/">uq-business-school.github.io/uqbs-course-profiles</a></div>`);
  parts.push(`</body></html>`);
  return parts.join("");
}

// Open a new window with the print-friendly HTML and trigger the print dialog.
function printCourseToPdf(c, taxonomy) {
  const html = buildPrintableHtml(c, taxonomy);
  const w = window.open("", "_blank");
  if (!w) {
    alert("Your browser blocked the print window. Please allow pop-ups for this site, or use Ctrl/⌘+P on this page.");
    return;
  }
  w.document.open(); w.document.write(html); w.document.close();
  // Wait for render, then print
  const trigger = () => { try { w.focus(); w.print(); } catch (e) { /* ignore */ } };
  if (w.document.readyState === "complete") setTimeout(trigger, 350);
  else w.addEventListener("load", () => setTimeout(trigger, 150));
}

function downloadCourseMarkdown(c, taxonomy) {
  const md = buildCourseMarkdown(c, taxonomy);
  downloadBlob(md, safeFilename(c, "md"), "text/markdown;charset=utf-8");
}

function downloadCourseJson(c) {
  const json = JSON.stringify(completeCourseJson(c), null, 2);
  downloadBlob(json, safeFilename(c, "json"), "application/json;charset=utf-8");
}

// =========================================================================
// Page: BROWSER (index.html)
// =========================================================================
async function initBrowser() {
  const $body = document.getElementById("courses-body");
  const $count = document.getElementById("course-count");
  const $meta = document.getElementById("meta-info");
  try {
    const [manifest, taxonomy, aol] = await Promise.all([loadManifest(), loadTaxonomy().catch(() => null), loadAol().catch(() => null), loadLoOverrides().catch(() => null), loadTeachingPeriods().catch(() => null)]);
    const courses = getAllCourses(manifest);
    STORE.allCourses = courses;
    STORE.taxonomy = taxonomy;
    STORE.aol = aol;
    $meta.innerHTML = `<span>Scrape generated</span> <b>${escapeHtml(fmtDate(manifest.generated_at))}</b> <span>· ${manifest.total_profiles} profiles</span>`;

    // Populate filter dropdowns
    populateSelect("filter-level", uniqueSorted(courses.map(c => c.study_level)));
    populateSelect("filter-mode", uniqueSorted(courses.map(c => c.attendance_mode)));
    populateSelect("filter-location", uniqueSorted(courses.map(c => c.location)));
    if (taxonomy && taxonomy.programs) {
      const progOpts = Object.entries(taxonomy.programs)
        .filter(([, v]) => v.is_programme !== false)
        .map(([k, v]) => ({ value: k, label: `${v.name} (${k})` }));
      populateSelect("filter-program", progOpts);
    }
    if (taxonomy && taxonomy.course_programs) {
      const majors = new Set();
      for (const lst of Object.values(taxonomy.course_programs)) {
        for (const r of lst) majors.add(`${r.program}: ${r.role || ""}`);
      }
      populateSelect("filter-major", [...majors].sort().map(m => ({ value: m, label: m })));
    }

    // Populate semester filter and default to most recent
    const semCodes = uniqueSorted(courses.map(c => c.semester_code));
    const semOpts = semCodes.map(code => {
      const sample = courses.find(c => c.semester_code === code);
      return { value: code, label: sample ? semesterLabel(sample) : code };
    });
    populateSelect("filter-semester", semOpts);
    // Default to most recent semester
    const $semFilter = document.getElementById("filter-semester");
    if ($semFilter && semCodes.length) {
      // Default to S1 2026 (7620) when present, else the most recent semester.
      $semFilter.value = semCodes.includes("7620") ? "7620" : semCodes[semCodes.length - 1];
    }

    // Initial render
    STORE.sort = { key: "course_code", dir: "asc" };
    STORE.renderFn = render;
    bindControls();
    render();
  } catch (err) {
    $body.innerHTML = `<tr><td colspan="10" class="error">Error loading data: ${escapeHtml(err.message)}</td></tr>`;
    console.error(err);
  }
}

function populateSelect(id, options) {
  const $sel = document.getElementById(id);
  if (!$sel) return;
  for (const opt of options) {
    const el = document.createElement("option");
    if (typeof opt === "string") { el.value = opt; el.textContent = opt; }
    else { el.value = opt.value; el.textContent = opt.label; }
    $sel.appendChild(el);
  }
}

function bindControls() {
  for (const id of ["search", "filter-semester", "filter-level", "filter-mode", "filter-location", "filter-program", "filter-major"]) {
    const el = document.getElementById(id);
    if (el) el.addEventListener("input", render);
  }
  // Sortable headers
  document.querySelectorAll("table.courses th[data-sort]").forEach(th => {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      if (STORE.sort.key === key) {
        STORE.sort.dir = STORE.sort.dir === "asc" ? "desc" : "asc";
      } else {
        STORE.sort = { key, dir: "asc" };
      }
      render();
    });
  });
  // CSV export
  const $export = document.getElementById("export-csv");
  if ($export) $export.addEventListener("click", exportFilteredAsCsv);
  const $zipMd = document.getElementById("export-zip-md");
  if ($zipMd) $zipMd.addEventListener("click", () => exportFilteredAsZip("md"));
  const $zipJson = document.getElementById("export-zip-json");
  if ($zipJson) $zipJson.addEventListener("click", () => exportFilteredAsZip("json"));
  setupSelection();
}

async function exportFilteredAsZip(format) {
  if (typeof JSZip === "undefined") {
    alert("ZIP library (JSZip) didn't load. Please check your network and try again.");
    return;
  }
  const courses = coursesForExport(STORE.filtered || []);
  if (!courses.length) {
    alert("No courses to export. Tick some rows, or adjust the filters.");
    return;
  }
  // Safety cap — warn the user for large selections
  if (courses.length > 300) {
    if (!confirm(`You're about to download ${courses.length} profiles. This may take a minute and will fetch ${courses.length} files. Continue?`)) return;
  }

  const $status = document.getElementById("bulk-status");
  const setStatus = msg => { if ($status) $status.textContent = msg; };
  setStatus(`Preparing ${courses.length} profile${courses.length === 1 ? "" : "s"}…`);

  const taxonomy = STORE.taxonomy;
  const zip = new JSZip();

  // Fetch with modest concurrency so we don't hammer the CDN or the browser.
  const CONCURRENCY = 6;
  let done = 0, failed = 0;
  let idx = 0;
  async function worker() {
    while (idx < courses.length) {
      const i = idx++;
      const c = courses[i];
      try {
        const full = await loadCourseJson(c.file);
        if (format === "md") {
          const md = buildCourseMarkdown(full, taxonomy);
          zip.file(`${safeFilename(full, "md")}`, md);
        } else {
          zip.file(`${safeFilename(full, "json")}`, JSON.stringify(completeCourseJson(full), null, 2));
        }
      } catch (err) {
        failed++;
        console.error(`Failed to fetch ${c.file}:`, err);
      }
      done++;
      if (done % 10 === 0 || done === courses.length) {
        setStatus(`Building ${format.toUpperCase()} ZIP · ${done}/${courses.length}${failed ? ` (${failed} failed)` : ""}`);
      }
    }
  }
  await Promise.all(Array.from({ length: Math.min(CONCURRENCY, courses.length) }, worker));

  // Add a manifest listing everything included, plus taxonomy if JSON.
  const manifestLines = [
    `# UQBS Course Profile Viewer — bulk export`,
    ``,
    `- Format: ${format.toUpperCase()}`,
    `- Courses: ${courses.length - failed}${failed ? ` (${failed} failed)` : ""}`,
    `- Generated: ${new Date().toISOString()}`,
    `- Filters applied at export time.`,
    ``,
  ];
  zip.file("README.md", manifestLines.join("\n"));

  setStatus(`Compressing ${format.toUpperCase()} ZIP…`);
  const blob = await zip.generateAsync({ type: "blob", compression: "DEFLATE", compressionOptions: { level: 6 } });
  const stamp = new Date().toISOString().slice(0, 10);
  const fname = `uqbs-courses-${stamp}-${courses.length}-${format}.zip`;
  downloadBlob(blob, fname, "application/zip");
  setStatus(`Done — ${courses.length - failed} profiles exported${failed ? `, ${failed} failed` : ""}.`);
  // Clear status after a short delay
  setTimeout(() => setStatus(""), 6000);
}

function exportFilteredAsCsv() {
  const courses = coursesForExport(STORE.filtered || []);
  const taxonomy = STORE.taxonomy;
  const columns = [
    "course_code", "course_title", "full_course_code", "study_level",
    "units", "attendance_mode", "location", "study_period",
    "coordinating_unit", "lo_count", "assessment_count",
    "programs", "scraped_at", "url",
  ];
  const csvEscape = v => {
    if (v == null) return "";
    const s = String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [columns.join(",")];
  for (const c of courses) {
    const roles = taxonomy ? programRolesFor(c.course_code, taxonomy) : [];
    const progs = roles.map(r => `${r.program}:${r.role || ""}`).join("; ");
    const row = columns.map(col => {
      if (col === "programs") return csvEscape(progs);
      return csvEscape(c[col]);
    });
    lines.push(row.join(","));
  }
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const now = new Date().toISOString().slice(0, 10);
  const filename = `uqbs-courses-${now}-${courses.length}.csv`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}

// ---- bulk selection (download multiple) -----------------------------------
// Courses to export: the ticked selection if any, else the current filtered set.
function coursesForExport(filtered) {
  const sel = STORE.selected;
  if (sel && sel.size) {
    return applySort((STORE.allCourses || []).filter(c => sel.has(c.file)));
  }
  return filtered || [];
}

// Wire row checkboxes, the select-all box, and a "N selected · Clear" indicator.
// Shared by both browsers; safe to call once per page.
function setupSelection() {
  const actions = document.querySelector(".bulk-actions");
  if (actions && !document.getElementById("sel-info")) {
    const info = document.createElement("span");
    info.id = "sel-info";
    info.className = "small muted";
    info.style.marginLeft = "4px";
    const clear = document.createElement("button");
    clear.id = "sel-clear";
    clear.type = "button";
    clear.className = "btn-link";
    clear.textContent = "Clear selection";
    clear.style.display = "none";
    const anchor = document.getElementById("bulk-status");
    actions.insertBefore(info, anchor);
    actions.insertBefore(clear, anchor);
    clear.addEventListener("click", () => {
      STORE.selected.clear();
      if (typeof STORE.renderFn === "function") STORE.renderFn();
    });
  }
  const body = document.getElementById("courses-body");
  if (body && !body._selBound) {
    body.addEventListener("change", (e) => {
      const cb = e.target && e.target.closest ? e.target.closest(".row-sel") : null;
      if (!cb) return;
      if (cb.checked) STORE.selected.add(cb.dataset.file);
      else STORE.selected.delete(cb.dataset.file);
      refreshSelectionUI();
    });
    body._selBound = true;
  }
  const all = document.getElementById("select-all");
  if (all && !all._selBound) {
    all.addEventListener("change", () => {
      const filtered = STORE.filtered || [];
      if (all.checked) filtered.forEach(c => STORE.selected.add(c.file));
      else filtered.forEach(c => STORE.selected.delete(c.file));
      if (typeof STORE.renderFn === "function") STORE.renderFn();
    });
    all._selBound = true;
  }
}

// Checkbox cell for a course row.
function selCell(c) {
  const checked = STORE.selected && STORE.selected.has(c.file) ? " checked" : "";
  return `<td class="sel-col"><input type="checkbox" class="row-sel" data-file="${escapeHtml(c.file)}" aria-label="Select ${escapeHtml(c.course_code || "")}"${checked}></td>`;
}

// Update the selected-count text, Clear button, and select-all tri-state.
function refreshSelectionUI() {
  const n = STORE.selected ? STORE.selected.size : 0;
  const info = document.getElementById("sel-info");
  if (info) info.textContent = n ? `${n} selected` : "";
  const clear = document.getElementById("sel-clear");
  if (clear) clear.style.display = n ? "" : "none";
  const all = document.getElementById("select-all");
  if (all) {
    const filtered = STORE.filtered || [];
    const inSel = filtered.reduce((acc, c) => acc + (STORE.selected.has(c.file) ? 1 : 0), 0);
    all.checked = filtered.length > 0 && inSel === filtered.length;
    all.indeterminate = inSel > 0 && inSel < filtered.length;
  }
}

function applyFilters(courses) {
  const q = (document.getElementById("search")?.value || "").trim().toLowerCase();
  const sem = document.getElementById("filter-semester")?.value;
  const level = document.getElementById("filter-level")?.value;
  const mode = document.getElementById("filter-mode")?.value;
  const loc = document.getElementById("filter-location")?.value;
  const prog = document.getElementById("filter-program")?.value;
  const major = document.getElementById("filter-major")?.value;

  return courses.filter(c => {
    if (q) {
      const hay = `${c.course_code} ${c.course_title || ""}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    if (sem && c.semester_code !== sem) return false;
    if (level && c.study_level !== level) return false;
    if (mode && c.attendance_mode !== mode) return false;
    if (loc && c.location !== loc) return false;
    if (prog && STORE.taxonomy && STORE.taxonomy.course_programs) {
      const roles = STORE.taxonomy.course_programs[c.course_code] || [];
      if (!roles.some(r => r.program === prog)) return false;
    }
    if (major && STORE.taxonomy && STORE.taxonomy.course_programs) {
      const roles = STORE.taxonomy.course_programs[c.course_code] || [];
      if (!roles.some(r => `${r.program}: ${r.role || ""}` === major)) return false;
    }
    return true;
  });
}

function applySort(courses) {
  const { key, dir } = STORE.sort;
  const mult = dir === "asc" ? 1 : -1;
  return [...courses].sort((a, b) => {
    const av = a[key], bv = b[key];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (typeof av === "number" && typeof bv === "number") return (av - bv) * mult;
    return String(av).localeCompare(String(bv), "en", { numeric: true }) * mult;
  });
}

function render() {
  const $body = document.getElementById("courses-body");
  const $count = document.getElementById("course-count");
  const courses = applySort(applyFilters(STORE.allCourses || []));
  STORE.filtered = courses;
  $count.textContent = courses.length;

  if (courses.length === 0) {
    $body.innerHTML = `<tr><td colspan="10" class="empty">No courses match the current filters.</td></tr>`;
    updateSortIndicators();
    refreshSelectionUI();
    return;
  }

  const taxonomy = STORE.taxonomy;
  const rows = courses.map(c => {
    const roles = taxonomy ? programRolesFor(c.course_code, taxonomy) : [];
    // One chip per program: "Program: role", coloured consistently by program.
    const progChips = roles.slice(0, 4).map(r => {
      const hue = hueForProgram(r.program);
      return `<span class="chip" style="--chip-hue:${hue}" title="${escapeHtml(r.program_name || r.program)} — ${escapeHtml(r.role || "")}">${escapeHtml(r.program)}: ${escapeHtml(r.role || "")}</span>`;
    }).join(" ");
    const more = roles.length > 4 ? `<span class="chip muted">+${roles.length - 4}</span>` : "";
    const levelClass = (c.study_level || "").toLowerCase().includes("post") ? "level-pill pg" : "level-pill";
    const fullCode = c.full_course_code || [c.course_code, c.class_code, c.semester_code].filter(Boolean).join("-");
    const pfx = coursePrefix(c.course_code);
    const codeCls = pfx ? `code prefix-${pfx}` : "code";
    const aolEntries = STORE.aol ? getAolForCourse(STORE.aol, c.course_code) : [];
    const aolCell = aolEntries.length
      ? aolEntries.map(e => `<span class="aol-chip ${(AOL_STATUS[e.status] || {}).cls || ''}" title="${escapeHtml(e.ga)}: ${escapeHtml((AOL_STATUS[e.status] || {}).label || e.status)}">${escapeHtml(e.ga)}</span>`).join(" ")
      : "";
    const semLabel = semesterLabel(c);
    return `
      <tr>
        ${selCell(c)}
        <td class="${codeCls}"><a href="course.html?file=${encodeURIComponent(c.file)}">${escapeHtml(c.course_code || "")}</a></td>
        <td>${escapeHtml(c.course_title || "")}</td>
        <td class="nowrap">${escapeHtml(semLabel)}</td>
        <td><span class="${levelClass}">${escapeHtml(c.study_level || "")}</span></td>
        <td>${escapeHtml(c.units || "")}</td>
        <td>${escapeHtml(c.attendance_mode || "")}</td>
        <td>${escapeHtml(c.location || "")}</td>
        <td>${progChips}${more}</td>
        <td class="aol-col">${aolCell}</td>
      </tr>`;
  }).join("");
  $body.innerHTML = rows;
  updateSortIndicators();
  refreshSelectionUI();
}

function updateSortIndicators() {
  document.querySelectorAll("table.courses th[data-sort]").forEach(th => {
    th.classList.remove("sort-asc", "sort-desc");
    if (th.dataset.sort === STORE.sort.key) {
      th.classList.add(STORE.sort.dir === "asc" ? "sort-asc" : "sort-desc");
    }
  });
}

// =========================================================================
// Page: COURSE DETAIL (course.html)
// =========================================================================
async function initCourseDetail() {
  const $root = document.getElementById("course-root");
  const filePath = getQueryParam("file");
  if (!filePath) {
    $root.innerHTML = `<div class="error">No course specified. Append <code>?file=profiles/{semester}/{course}.json</code> to the URL.</div>`;
    return;
  }
  try {
    const [course, manifest, manifestLegacy, taxonomy, aol] = await Promise.all([
      loadCourseJson(filePath), loadManifest(), loadManifestLegacy().catch(() => ({ periods: {} })), loadTaxonomyAll().catch(() => null), loadAol().catch(() => null), loadLoOverrides().catch(() => null), loadTeachingPeriods().catch(() => null)
    ]);
    STORE.currentCourse = course;
    STORE.currentTaxonomy = taxonomy;
    STORE.aol = aol;

    // Find all offerings of this course across both systems (current + legacy),
    // ordered newest→oldest. This is the spine of the per-course timeline.
    const currentOfferings = getAllCourses(manifest);
    // The all-of-UQ manifest covers non-UQBS courses that the UQBS manifest omits;
    // fall back to it so the timeline is complete for any course the viewer reached.
    let pool = currentOfferings.filter(c => c.course_code === course.course_code);
    if (pool.length === 0) {
      try {
        const all = await loadManifestAll();
        pool = getAllCourses(all).filter(c => c.course_code === course.course_code);
      } catch (_e) { /* keep UQBS pool */ }
    }
    const legacyOfferings = getLegacyCourses(manifestLegacy)
      .filter(c => c.course_code === course.course_code);
    const otherOfferings = pool.concat(legacyOfferings)
      .filter(c => c.file !== filePath)
      .sort((a, b) => offeringChronKey(b).localeCompare(offeringChronKey(a), undefined, { numeric: true }));

    renderCourseDetail($root, course, taxonomy, otherOfferings, filePath);
    document.title = `${course.course_code} — ${course.course_title}`;
    // Wire up download buttons after render
    const $pdf = document.getElementById("dl-pdf");
    const $md = document.getElementById("dl-md");
    const $json = document.getElementById("dl-json");
    if ($pdf) $pdf.addEventListener("click", () => printCourseToPdf(course, taxonomy));
    if ($md) $md.addEventListener("click", () => downloadCourseMarkdown(course, taxonomy));
    if ($json) $json.addEventListener("click", () => downloadCourseJson(course));
    // Wire the "Report an error" control — opens a prefilled email with the exact
    // course/offering location baked in so the fix can be pinpointed.
    const $report = document.getElementById("report-error");
    const $panel = document.getElementById("report-panel");
    const $send = document.getElementById("report-send");
    const $text = document.getElementById("report-text");
    if ($report && $panel) {
      $report.addEventListener("click", (e) => {
        e.preventDefault();
        $panel.hidden = !$panel.hidden;
        if (!$panel.hidden && $text) $text.focus();
      });
    }
    if ($send) {
      $send.addEventListener("click", () => {
        const desc = ($text && $text.value || "").trim();
        const $hint = document.getElementById("report-hint");
        if (!desc) { if ($hint) $hint.textContent = "Add a quick description first."; return; }
        if ($hint) $hint.textContent = "Opening your email app…";
        window.location.href = buildReportMailto(course, filePath, desc);
      });
    }
    // Wire the timeline compare control: fetch the picked offering and diff it.
    const $cmp = document.getElementById("cmp-pick");
    const $cmpResult = document.getElementById("cmp-result");
    if ($cmp && $cmpResult) {
      $cmp.addEventListener("change", async () => {
        const file = $cmp.value;
        if (!file) { $cmpResult.innerHTML = ""; return; }
        $cmpResult.innerHTML = `<div class="cmp-loading">Loading…</div>`;
        try {
          const other = await loadCourseJson(file);
          $cmpResult.innerHTML = renderOfferingDiff(computeOfferingDiff(course, other));
        } catch (e) {
          $cmpResult.innerHTML = `<div class="error">Could not load that offering: ${escapeHtml(e.message)}</div>`;
        }
      });
    }
  } catch (err) {
    $root.innerHTML = `<div class="error">Error loading profile: ${escapeHtml(err.message)}</div>`;
    console.error(err);
  }
}

// Build the per-course timeline widget. `others` is every OTHER offering of
// this course (current + legacy), already sorted newest→oldest. The current
// offering `c` is spliced into chronological position and marked. Legacy
// offerings get an era badge; a title change between adjacent offerings is
// flagged as an event (the course code was likely repurposed or renamed).
function buildCourseTimeline(c, others, currentFile) {
  others = others || [];
  if (others.length === 0) return "";

  // Assemble the full ordered list including the current offering.
  const currentEntry = {
    file: currentFile || getQueryParam("file"),
    course_code: c.course_code,
    course_title: c.course_title,
    study_period: c.study_period,
    year: c.year,
    period: c.period,
    system: c.system || (c.semester_code ? "current" : "legacy"),
    _current: true,
  };
  const all = others.concat([currentEntry])
    .sort((a, b) => offeringChronKey(b).localeCompare(offeringChronKey(a), undefined, { numeric: true }));

  const span = `${semesterLabel(all[all.length - 1])} → ${semesterLabel(all[0])}`;
  const nodes = all.map((o, i) => {
    const label = semesterLabel(o);
    const isLegacy = o.system === "legacy";
    const cls = ["tl-node"];
    if (o._current) cls.push("tl-current");
    if (isLegacy) cls.push("tl-legacy");
    // Title-change event: compare to the next-older offering in the list.
    const older = all[i + 1];
    let titleNote = "";
    if (older && normTitle(older.course_title) !== normTitle(o.course_title)) {
      titleNote = `<span class="tl-event" title="Title changed from “${escapeHtml(older.course_title || "")}”">title changed</span>`;
    }
    const eraTag = isLegacy ? `<span class="tl-era" title="Legacy profile (2009–S1 2024)">legacy</span>` : "";
    const inner = `${escapeHtml(label)}${eraTag}`;
    const body = o._current
      ? `<span class="tl-node-label" title="Currently viewing — ${escapeHtml(o.course_title || "")}">${inner}</span>`
      : `<a class="tl-node-label" href="course.html?file=${encodeURIComponent(o.file)}" title="${escapeHtml(o.course_title || "")}">${inner}</a>`;
    return `<li class="${cls.join(" ")}">${body}${titleNote}</li>`;
  }).join("");

  // Compare control: pick any other offering to diff against the one on screen.
  const cmpOptions = all.filter(o => !o._current).map(o =>
    `<option value="${escapeHtml(o.file)}">${escapeHtml(semesterLabel(o))}${o.system === "legacy" ? " (legacy)" : ""}</option>`
  ).join("");
  const cmpHtml = `
    <div class="tl-compare">
      <label for="cmp-pick">Compare this offering with</label>
      <select id="cmp-pick">
        <option value="">— choose an offering —</option>
        ${cmpOptions}
      </select>
    </div>
    <div id="cmp-result" class="cmp-result" aria-live="polite"></div>
  `;

  return `
    <div class="course-timeline" aria-label="Offerings of this course over time">
      <div class="tl-head">
        <span class="tl-title">Timeline</span>
        <span class="tl-span">${escapeHtml(span)} · ${all.length} offering${all.length === 1 ? "" : "s"}</span>
      </div>
      <ol class="tl-track">${nodes}</ol>
      ${cmpHtml}
    </div>
  `;
}

// Compute a structured diff between two full course profiles of the same course.
// Always oriented older→newer (by chronological key) so "added"/"dropped" read
// naturally as change over time. Assessment items are matched by normalised
// title; weight and LO-set changes on matched items are reported.
function computeOfferingDiff(profA, profB) {
  // Orient: older first, newer second.
  let older = profA, newer = profB;
  if (offeringChronKey(profA).localeCompare(offeringChronKey(profB), undefined, { numeric: true }) > 0) {
    older = profB; newer = profA;
  }
  const norm = s => normTitle(s || "");
  const loSet = row => {
    const refs = Array.isArray(row.learning_outcomes) ? row.learning_outcomes
      : parseLoRefs(row.learning_outcomes_assessed || row.learning_outcomes || "");
    return refs.map(x => String(x).replace(/^lo/i, "").replace(/\.$/, "")).filter(Boolean)
      .map(Number).filter(n => !isNaN(n)).sort((a, b) => a - b);
  };
  const normWeight = w => String(w == null ? "" : w).replace(/\s+/g, " ").trim();

  const aRows = older.assessment_summary || [];
  const bRows = newer.assessment_summary || [];
  const aByTitle = new Map(aRows.map(r => [norm(r.title), r]));
  const bByTitle = new Map(bRows.map(r => [norm(r.title), r]));

  const added = [], dropped = [], changed = [];
  for (const r of bRows) {
    if (!aByTitle.has(norm(r.title))) added.push({ title: r.title, weight: r.weight });
  }
  for (const r of aRows) {
    if (!bByTitle.has(norm(r.title))) dropped.push({ title: r.title, weight: r.weight });
  }
  for (const r of bRows) {
    const a = aByTitle.get(norm(r.title));
    if (!a) continue;
    const wOld = normWeight(a.weight), wNew = normWeight(r.weight);
    const loOld = loSet(a), loNew = loSet(r);
    const weightChanged = wOld !== wNew;
    const loChanged = JSON.stringify(loOld) !== JSON.stringify(loNew);
    if (weightChanged || loChanged) {
      changed.push({
        title: r.title,
        weight: weightChanged ? { from: a.weight, to: r.weight } : null,
        los: loChanged ? { from: loOld, to: loNew } : null,
      });
    }
  }

  const loCountOld = (older.learning_outcomes || []).length;
  const loCountNew = (newer.learning_outcomes || []).length;
  const titleChanged = norm(older.course_title) !== norm(newer.course_title);

  return {
    older, newer, added, dropped, changed,
    loCount: loCountOld !== loCountNew ? { from: loCountOld, to: loCountNew } : null,
    title: titleChanged ? { from: older.course_title, to: newer.course_title } : null,
    identical: !added.length && !dropped.length && !changed.length && loCountOld === loCountNew && !titleChanged,
  };
}

// Render an offering diff (from computeOfferingDiff) to HTML.
function renderOfferingDiff(diff) {
  const oLab = semesterLabel(diff.older), nLab = semesterLabel(diff.newer);
  const head = `<div class="cmp-head"><strong>${escapeHtml(oLab)}</strong> → <strong>${escapeHtml(nLab)}</strong></div>`;
  if (diff.identical) {
    return `<div class="cmp-panel">${head}<div class="cmp-none">No changes to title, learning outcomes count, or assessment items between these two offerings.</div></div>`;
  }
  const blocks = [];
  if (diff.title) {
    blocks.push(`<div class="cmp-row cmp-meta"><span class="cmp-tag">title</span> “${escapeHtml(diff.title.from || "")}” → “${escapeHtml(diff.title.to || "")}”</div>`);
  }
  if (diff.loCount) {
    blocks.push(`<div class="cmp-row cmp-meta"><span class="cmp-tag">LOs</span> ${diff.loCount.from} → ${diff.loCount.to} learning outcomes</div>`);
  }
  for (const a of diff.added) {
    blocks.push(`<div class="cmp-row cmp-add"><span class="cmp-tag">added</span> ${escapeHtml(a.title || "")}${a.weight ? ` <span class="cmp-w">(${escapeHtml(a.weight)})</span>` : ""}</div>`);
  }
  for (const d of diff.dropped) {
    blocks.push(`<div class="cmp-row cmp-drop"><span class="cmp-tag">dropped</span> ${escapeHtml(d.title || "")}${d.weight ? ` <span class="cmp-w">(${escapeHtml(d.weight)})</span>` : ""}</div>`);
  }
  for (const ch of diff.changed) {
    const bits = [];
    if (ch.weight) bits.push(`weight ${escapeHtml(String(ch.weight.from || "—"))} → ${escapeHtml(String(ch.weight.to || "—"))}`);
    if (ch.los) bits.push(`LOs ${ch.los.from.length ? "LO" + ch.los.from.join(", LO") : "—"} → ${ch.los.to.length ? "LO" + ch.los.to.join(", LO") : "—"}`);
    blocks.push(`<div class="cmp-row cmp-chg"><span class="cmp-tag">changed</span> ${escapeHtml(ch.title || "")} <span class="cmp-w">${bits.join(" · ")}</span></div>`);
  }
  return `<div class="cmp-panel">${head}${blocks.join("")}</div>`;
}

// Build a mailto: link for an error report, with the exact course/offering
// location baked into the body so a fix can be pinpointed (often an LO-mapping gap).
function buildReportMailto(c, filePath, description) {
  const to = SITE.reportEmail || "learningdesign@business.uq.edu.au";
  const code = c.full_course_code || c.course_code || "";
  const sem = semesterLabel(c);
  const subject = `Course profile error: ${c.course_code || ""} (${sem})`;
  const pageUrl = (typeof location !== "undefined" && location.href) || "";
  const body = [
    "Reported from the UQ Course Profiles viewer.",
    "",
    "What's wrong:",
    description || "(describe here)",
    "",
    "— Pinpoint (please leave this in) —",
    `Course: ${c.course_code || ""} — ${c.course_title || ""}`,
    `Full code: ${code}`,
    `Semester: ${sem} (${c.semester_code || c.period || ""})`,
    `Class no.: ${c.class_code || ""}`,
    `File: ${filePath || ""}`,
    `Page: ${pageUrl}`,
    `Edition: ${EDITION}`,
  ].join("\n");
  return `mailto:${encodeURIComponent(to)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

function renderCourseDetail($root, c, taxonomy, otherOfferings, currentFile) {
  // Default for backward compat
  otherOfferings = otherOfferings || [];
  const roles = taxonomy ? programRolesFor(c.course_code, taxonomy) : [];
  const progChips = roles.map(r => {
    const isCore = (r.role || "").toLowerCase() === "core";
    const cls = isCore ? "chip role-core" : "chip";
    return `<span class="${cls}" title="${escapeHtml(r.role || "")}"><a href="program.html?program=${encodeURIComponent(r.program)}">${escapeHtml(r.program_name || r.program)}</a> · ${escapeHtml(r.role || "")}</span>`;
  }).join(" ");

  const parts = [];

  // Per-course timeline: every offering across both systems (current + legacy),
  // ordered newest→oldest, with the current one marked and title-change events
  // surfaced so a repurposed course code is visible rather than hidden.
  const semPickerHtml = buildCourseTimeline(c, otherOfferings, currentFile);

  // Header card
  const filePath = currentFile || getQueryParam("file");
  const rawJsonLink = filePath ? `<a href="${escapeHtml(dataUrl(filePath))}" target="_blank" rel="noopener">Raw JSON ↗</a>` : "";
  // Legacy provenance badge — make clear a pre-cutover profile is being viewed,
  // so a 2011 ECP is never mistaken for current.
  const isLegacy = c.system === "legacy" || (c.url || "").includes("archive.course-profiles.uq.edu.au");
  const legacyBadge = isLegacy
    ? `<span class="era-badge" title="Archived profile from the legacy course-profiles system (2009–S1 2024). LO-to-assessment mappings are rendered as originally published.">Legacy profile · ${escapeHtml(semesterLabel(c))}</span>`
    : "";
  parts.push(`
    <div class="course-header">
      <div><span class="code">${escapeHtml(c.full_course_code || c.course_code)}</span> ${legacyBadge}</div>
      <h1>${escapeHtml(c.course_code || "")} — ${escapeHtml(c.course_title || "")}</h1>
      <div class="meta">
        ${escapeHtml(c.study_level || "")} · ${escapeHtml(c.units || "")} ·
        ${escapeHtml(c.attendance_mode || "")} · ${escapeHtml(c.location || "")}
        ${c.url ? ` · <a href="${escapeHtml(c.url)}" target="_blank" rel="noopener">View on course-profiles.uq.edu.au ↗</a>` : ""}
        ${rawJsonLink ? ` · ${rawJsonLink}` : ""}
        · <a href="#" id="report-error" title="Report something wrong on this page">Report an error ⚑</a>
      </div>
      <div class="meta small" style="margin-top:4px">Last scraped: ${escapeHtml(fmtDate(c.scraped_at))}</div>
      <div id="report-panel" class="report-panel" hidden>
        <p class="small">Spotted something wrong — a learning-outcome mapping, an assessment detail, anything? Describe it and we'll open an email with the exact location pre-filled.</p>
        <textarea id="report-text" rows="3" placeholder="e.g. The final exam should map to learning outcomes 2 and 4, not just 2."></textarea>
        <div class="report-actions">
          <button id="report-send" class="dl-btn" type="button">Compose email ✉</button>
          <span id="report-hint" class="small muted"></span>
        </div>
      </div>
      ${semPickerHtml}
      ${progChips ? `<div style="margin-top:10px">${progChips}</div>` : ""}
    </div>
  `);

  // Download bar
  parts.push(`
    <div class="download-bar" aria-label="Download this profile">
      <button id="dl-pdf" class="dl-btn" type="button" title="Opens a print-friendly view — use Save as PDF in the print dialog">
        <span aria-hidden="true">🖨️</span> Save as PDF
      </button>
      <button id="dl-md" class="dl-btn" type="button" title="Download a clean Markdown (.md) version — good for LLMs and notes">
        <span aria-hidden="true">📝</span> Download Markdown
      </button>
      <button id="dl-json" class="dl-btn" type="button" title="Download the raw profile JSON">
        <span aria-hidden="true">{ }</span> Download JSON
      </button>
    </div>
  `);

  // Overview
  const overviewRows = [
    ["Study period", c.study_period],
    ["Coordinating unit", c.coordinating_unit],
    ["Administrative campus", c.administrative_campus],
  ].filter(([_, v]) => v);
  if (overviewRows.length) {
    parts.push(`
      <div class="card">
        <h2 style="margin-top:0">Overview</h2>
        <dl class="kv-grid">
          ${overviewRows.map(([k, v]) => `<dt>${escapeHtml(k)}</dt><dd>${escapeHtml(v)}</dd>`).join("")}
        </dl>
      </div>
    `);
  }

  // Description
  if (c.course_description) {
    parts.push(`
      <div class="card">
        <h2>Course description</h2>
        <div>${renderLongText(c.course_description)}</div>
      </div>
    `);
  }

  // Requirements (dict: prerequisites, incompatible, restrictions — each a list)
  if (c.requirements && typeof c.requirements === "object") {
    const reqRows = [];
    for (const [key, label] of [
      ["prerequisites", "Prerequisites"],
      ["incompatible", "Incompatible courses"],
      ["companions", "Companions"],
      ["restrictions", "Restrictions"],
      ["recommended_prerequisites", "Recommended prerequisites"],
    ]) {
      const v = c.requirements[key];
      if (!v) continue;
      if (Array.isArray(v) && v.length) {
        reqRows.push(`<dt>${escapeHtml(label)}</dt><dd>${v.map(item => escapeHtml(String(item))).join("<br>")}</dd>`);
      } else if (typeof v === "string" && v.trim()) {
        reqRows.push(`<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(v)}</dd>`);
      }
    }
    if (reqRows.length) {
      parts.push(`
        <div class="card">
          <h2>Requirements</h2>
          <dl class="kv-grid">${reqRows.join("")}</dl>
        </div>
      `);
    }
  }

  // Aims
  if (c.course_aims) {
    parts.push(`
      <div class="card">
        <h2>Course aims</h2>
        <div>${renderLongText(c.course_aims)}</div>
      </div>
    `);
  }

  // Learning outcomes
  if (c.learning_outcomes && c.learning_outcomes.length) {
    parts.push(`
      <div class="card">
        <h2>Learning outcomes</h2>
        ${c.learning_outcomes.map(lo => {
          const code = loDisplayCode(lo);
          return `
            <div class="lo-item">
              <div class="lo-code">${escapeHtml(code)}</div>
              <div>${escapeHtml(lo.description || "")}</div>
            </div>
          `;
        }).join("")}
      </div>
    `);
  }

  // Assessment summary — merge LO mapping from assessment_details when
  // the summary rows don't carry it directly.
  if (c.assessment_summary && c.assessment_summary.length) {
    const loMap = buildAssessmentLoMap(c);
    const ovMap = getLoOverrideMap(c.course_code, c.semester_code, c.class_code);
    // Resolve the LO list for one assessment row: override wins, then any LOs
    // carried on the summary row, then the scraped assessment-details map.
    const resolveLos = (a) => {
      const title = (a.title || "").trim();
      const ov = ovMap[normTitle(title)];
      if (ov) return { los: ov.los, override: true, notes: ov.notes, source: ov.source || "jac" };
      if (a.learning_outcomes && a.learning_outcomes.length) return { los: a.learning_outcomes, override: false };
      if (title && loMap[title]) return { los: loMap[title], override: false };
      return { los: [], override: false };
    };
    const resolved = c.assessment_summary.map(resolveLos);
    const hasAnyLos = resolved.some(r => r.los && r.los.length);
    const anyOverride = resolved.some(r => r.override);
    const loHeader = hasAnyLos ? `<th>LOs</th>` : "";
    const rows = c.assessment_summary.map((a, i) => {
      const { los, override, notes, source } = resolved[i];
      const carried = source === "carried";
      const why = carried ? "Carried forward from the previous offering because the published profile dropped it" : "From Jac, the authored curriculum record — omitted from the published profile";
      const chips = los.length
        ? los.map(x => `<span class="lo-chip${override ? " override" : ""}"${override ? ` title="${why}${notes ? ": " + escapeHtml(notes) : ""}"` : ""}>${escapeHtml(x)}</span>`).join(" ")
        : "—";
      const mark = override ? ` <span class="lo-override-mark" title="${why}${carried && notes ? ": " + escapeHtml(notes) : " by a publishing fault"}">${carried ? "Carried" : "Jac"}</span>` : "";
      const loCell = hasAnyLos ? `<td class="lo-list">${chips}${mark}</td>` : "";
      return `
        <tr>
          <td><b>${escapeHtml(a.title || "")}</b>
            ${a.conditions && a.conditions.length ? `<span class="conditions">${a.conditions.map(escapeHtml).join(" · ")}</span>` : ""}
          </td>
          <td class="nowrap">${escapeHtml(a.category || a.type || "")}</td>
          <td class="weight nowrap">${escapeHtml(a.weighting || a.weight || "")}</td>
          <td>${escapeHtml(a.due_date || a.due || "")}</td>
          ${loCell}
        </tr>
      `;
    }).join("");
    const legend = anyOverride
      ? `<p class="lo-override-legend">Mappings marked <span class="lo-override-mark">Jac</span> are from the authored curriculum record in Jac; those marked <span class="lo-override-mark">Carried</span> were carried forward from the previous offering. UQ's published profile omits them due to a publishing fault.</p>`
      : "";
    parts.push(`
      <div class="card">
        <h2>Assessment</h2>
        <table class="assessment">
          <thead><tr><th>Task</th><th>Category</th><th>Weight</th><th>Due</th>${loHeader}</tr></thead>
          <tbody>${rows}</tbody>
        </table>
        ${legend}
      </div>
    `);
  }

  // AoL status card
  const aolEntries = STORE.aol ? getAolForCourse(STORE.aol, c.course_code) : [];
  if (aolEntries.length) {
    const aolRows = aolEntries.map(e => {
      const statusInfo = AOL_STATUS[e.status] || { label: e.status, icon: "?", cls: "" };
      return `<tr>
        <td>${escapeHtml(e.semester_label || e.semester_code)}</td>
        <td>${aolGaChip(e.ga)}</td>
        <td>${escapeHtml(e.assessment_title)}</td>
        <td><span class="aol-chip ${statusInfo.cls}">${statusInfo.icon} ${escapeHtml(statusInfo.label)}</span></td>
        <td>${e.rubric_url ? `<a href="${escapeHtml(e.rubric_url)}" target="_blank" rel="noopener">View rubric ↗</a>` : '<span class="muted">—</span>'}</td>
        <td class="muted small">${escapeHtml(e.notes || "")}</td>
      </tr>`;
    }).join("");
    parts.push(`
      <div class="card aol-card">
        <h2>Assurance of Learning</h2>
        <table class="assessment">
          <thead><tr><th>Semester</th><th>GA</th><th>Assessment</th><th>Status</th><th>Rubric</th><th>Notes</th></tr></thead>
          <tbody>${aolRows}</tbody>
        </table>
      </div>
    `);
  }

  // Assessment details
  if (c.assessment_details && c.assessment_details.length) {
    const ovMapDetail = getLoOverrideMap(c.course_code, c.semester_code, c.class_code);
    parts.push(`
      <div class="card">
        <h2>Assessment details</h2>
        ${c.assessment_details.map(a => renderAssessmentDetail(a, ovMapDetail)).join("")}
      </div>
    `);
  }

  // Timetable
  if (c.timetable) {
    parts.push(`
      <div class="card">
        <h2>Timetable</h2>
        <div>${renderLongText(c.timetable)}</div>
      </div>
    `);
  }

  // Contacts
  if (c.course_contacts && c.course_contacts.length) {
    parts.push(`
      <div class="card">
        <h2>Course contacts</h2>
        <div class="staff-list">
          ${c.course_contacts.map(renderStaffCard).join("")}
        </div>
      </div>
    `);
  }

  // Staff
  if (c.course_staff && c.course_staff.length) {
    parts.push(`
      <div class="card">
        <h2>Course staff</h2>
        <div class="staff-list">
          ${c.course_staff.map(renderStaffCard).join("")}
        </div>
      </div>
    `);
  }

  // Learning activities (list of {learning_period, activity_type, topic, learning_outcomes})
  if (Array.isArray(c.learning_activities) && c.learning_activities.length) {
    const rows = c.learning_activities.map(la => {
      // Strip trailing "Learning outcomes:..." which the scraper concatenates into topic
      const topic = (la.topic || "").replace(/\s*Learning outcomes?:.*$/i, "").trim();
      const los = Array.isArray(la.learning_outcomes) ? la.learning_outcomes.join(", ") : (la.learning_outcomes || "");
      return `<tr>
        <td class="nowrap">${escapeHtml(la.learning_period || "")}</td>
        <td class="nowrap">${escapeHtml(la.activity_type || "")}</td>
        <td>${escapeHtml(topic)}</td>
        <td class="nowrap small">${escapeHtml(los)}</td>
      </tr>`;
    }).join("");
    parts.push(`
      <div class="card">
        <h2>Learning activities</h2>
        <table class="assessment">
          <thead><tr><th>Period</th><th>Type</th><th>Topic</th><th>LOs</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `);
  }

  // Learning resources (dict: library_resources, etc. — may be string or list)
  if (c.learning_resources && typeof c.learning_resources === "object") {
    const lrRows = [];
    const labelMap = {
      library_resources: "Library resources",
      additional_resources: "Additional resources",
      required_resources: "Required resources",
      recommended_resources: "Recommended resources",
    };
    for (const [key, val] of Object.entries(c.learning_resources)) {
      if (!val) continue;
      const label = labelMap[key] || key.replace(/_/g, " ").replace(/\b\w/g, s => s.toUpperCase());
      let rendered;
      if (Array.isArray(val)) {
        rendered = val.map(v => escapeHtml(String(v))).join("<br>");
      } else {
        rendered = renderLongText(String(val));
      }
      lrRows.push(`<dt>${escapeHtml(label)}</dt><dd>${rendered}</dd>`);
    }
    if (lrRows.length) {
      parts.push(`
        <div class="card">
          <h2>Learning resources</h2>
          <dl class="kv-grid">${lrRows.join("")}</dl>
        </div>
      `);
    }
  } else if (typeof c.learning_resources === "string" && c.learning_resources.trim()) {
    parts.push(`
      <div class="card">
        <h2>Learning resources</h2>
        <div>${renderLongText(c.learning_resources)}</div>
      </div>
    `);
  }

  // Policies
  if (c.policies_and_procedures) {
    parts.push(`
      <div class="card">
        <h2>Policies and procedures</h2>
        <div>${renderLongText(c.policies_and_procedures)}</div>
      </div>
    `);
  }

  $root.innerHTML = parts.join("");
}

function renderAssessmentDetail(a, ovMap) {
  const meta = [];
  if (a.weighting || a.weight) meta.push(`<b>Weight:</b> ${escapeHtml(a.weighting || a.weight)}`);
  if (a.due_date || a.due) meta.push(`<b>Due:</b> ${escapeHtml(a.due_date || a.due)}`);
  if (a.category || a.type) meta.push(`<b>Category:</b> ${escapeHtml(a.category || a.type)}`);
  if (a.mode) meta.push(`<b>Mode:</b> ${escapeHtml(a.mode)}`);
  if (a.other_conditions) meta.push(`<b>Conditions:</b> ${escapeHtml(a.other_conditions)}`);

  // Learning outcomes assessed — a manual override (if present) is the
  // authoritative list; otherwise use the scraped value ("L01, L02" or list).
  const ov = ovMap ? ovMap[normTitle(a.title)] : null;
  let loStr = "", loOverride = false;
  if (ov) {
    loStr = ov.los.join(", ");
    loOverride = true;
  } else {
    const loField = a.learning_outcomes_assessed != null ? a.learning_outcomes_assessed : a.learning_outcomes;
    if (Array.isArray(loField)) loStr = loField.map(x => String(x)).join(", ");
    else if (loField) loStr = String(loField);
  }

  // Special indicators (list of strings)
  let indicators = "";
  if (Array.isArray(a.special_indicators) && a.special_indicators.length) {
    indicators = a.special_indicators.map(s => `<span class="chip">${escapeHtml(String(s))}</span>`).join(" ");
  }

  const sections = [];
  for (const [key, label] of [
    ["task_description", "Task description"],
    ["task", "Task"],
    ["exam_details", "Exam details"],
    ["submission_guidelines", "Submission guidelines"],
    ["deferral_or_extension", "Deferral or extension"],
    ["late_submission", "Late submission"],
    ["marking_criteria", "Marking criteria"],
    ["ai_statement", "AI / academic integrity"],
  ]) {
    const v = a[key];
    if (!v) continue;
    if (Array.isArray(v)) {
      sections.push(`<h4>${label}</h4><ul class="plain">${v.map(x => `<li>${escapeHtml(String(x))}</li>`).join("")}</ul>`);
    } else {
      sections.push(`<h4>${label}</h4>${renderLongText(String(v))}`);
    }
  }

  return `
    <div class="assessment-detail">
      <h4>${escapeHtml(a.title || a.name || "Assessment")}</h4>
      ${meta.length ? `<div class="a-meta">${meta.join(" · ")}</div>` : ""}
      ${indicators ? `<div style="margin-bottom:8px">${indicators}</div>` : ""}
      ${loStr ? `<div class="small muted">Linked LOs: ${escapeHtml(loStr)}${loOverride ? ` <span class="lo-override-mark" title="From Jac, the authored curriculum record — omitted from the published profile by a publishing fault">Jac</span>` : ""}</div>` : ""}
      ${sections.join("")}
    </div>
  `;
}

function renderStaffCard(s) {
  const name = s.name || "";
  const role = s.role || "";
  const email = s.email || "";
  return `
    <div class="staff-card">
      <div class="name">${escapeHtml(name)}</div>
      ${role ? `<div class="role">${escapeHtml(role)}</div>` : ""}
      ${email ? `<div class="email"><a href="mailto:${escapeHtml(email)}">${escapeHtml(email)}</a></div>` : ""}
    </div>
  `;
}

// Render long text: if already contains HTML-like content keep it conservatively as escaped paragraphs
function renderLongText(text) {
  if (!text) return "";
  // Split on double newlines; escape and wrap each paragraph
  const paras = String(text).split(/\n{2,}/).map(p => p.trim()).filter(Boolean);
  return paras.map(p => `<p>${escapeHtml(p).replace(/\n/g, "<br>")}</p>`).join("");
}

// =========================================================================
// Page: PROGRAM (program.html)
// =========================================================================
async function initProgram() {
  const $root = document.getElementById("program-root");
  const progKey = getQueryParam("program");

  try {
    const [manifest, taxonomy, aol] = await Promise.all([loadManifest(), loadTaxonomy(), loadAol().catch(() => null), loadTeachingPeriods().catch(() => null)]);
    const courses = getAllCourses(manifest);
    STORE.allCourses = courses;
    STORE.taxonomy = taxonomy;
    STORE.aol = aol;

    if (!progKey) {
      renderProgramIndex($root, taxonomy, courses);
    } else {
      renderProgramDetail($root, progKey, taxonomy, courses);
    }
  } catch (err) {
    $root.innerHTML = `<div class="error">Error: ${escapeHtml(err.message)}</div>`;
    console.error(err);
  }
}

function renderProgramIndex($root, taxonomy, courses) {
  document.title = "Programs — UQBS Course Profile Viewer";
  const coursesByCode = {};
  for (const c of courses) coursesByCode[c.course_code] = c;

  const programEntries = Object.entries(taxonomy.programs).filter(([, p]) => p.is_programme !== false);
  const items = programEntries.map(([key, p]) => {
    const scrapedCount = Object.entries(taxonomy.course_programs || {}).filter(([code, roles]) => {
      return roles.some(r => r.program === key) && coursesByCode[code];
    }).length;
    const codeLabel = p.program_code ? ` · ${p.program_code}` : "";
    return `
      <a class="program-card" href="program.html?program=${encodeURIComponent(key)}" style="display:block">
        <div class="level">${escapeHtml(p.level || "")}</div>
        <h3>${escapeHtml(p.name || key)}</h3>
        <div class="muted small">${escapeHtml(key)}${escapeHtml(codeLabel)}</div>
        <div class="count">${scrapedCount} course${scrapedCount === 1 ? "" : "s"} with scraped profile${scrapedCount === 1 ? "" : "s"}</div>
      </a>
    `;
  }).join("");

  $root.innerHTML = `
    <h1>Programs</h1>
    <p class="subtitle">${programEntries.length} UQBS programs. Click through to see core and majors.</p>
    <div class="program-list">${items}</div>
  `;
}

function renderProgramDetail($root, progKey, taxonomy, courses) {
  const p = taxonomy.programs[progKey];
  if (!p) {
    $root.innerHTML = `<div class="error">Unknown program: ${escapeHtml(progKey)}</div>`;
    return;
  }
  document.title = `${p.name} — UQBS Course Profile Viewer`;
  const coursesByCode = {};
  for (const c of courses) coursesByCode[c.course_code] = c;

  function renderCourseRow(code) {
    const c = coursesByCode[code];
    const pfx = coursePrefix(code);
    const codeCls = pfx ? `code prefix-${pfx}` : "code";
    const courseAol = STORE.aol ? getAolForCourse(STORE.aol, code) : [];
    const aolTd = courseAol.length
      ? `<td class="aol-col">${courseAol.map(e => `<span class="aol-chip ${(AOL_STATUS[e.status] || {}).cls || ''}" title="${escapeHtml((AOL_STATUS[e.status] || {}).label || e.status)}: ${escapeHtml(e.assessment_title)}">${escapeHtml(e.ga)}</span>`).join(" ")}</td>`
      : `<td class="aol-col"></td>`;
    if (c) {
      return `<tr>
        <td class="${codeCls}"><a href="course.html?file=${encodeURIComponent(c.file)}">${escapeHtml(code)}</a></td>
        <td>${escapeHtml(c.course_title || "")}</td>
        <td>${escapeHtml(c.units || "")}</td>
        <td>${escapeHtml(c.attendance_mode || "")}</td>
        ${aolTd}
      </tr>`;
    }
    return `<tr>
      <td class="${codeCls} muted">${escapeHtml(code)}</td>
      <td class="muted"><em>not in current scrape</em></td>
      <td></td><td></td>
      ${aolTd}
    </tr>`;
  }

  const codeLabel = p.program_code ? ` · ${p.program_code}` : "";
  const parts = [`
    <a href="program.html" class="small">← All programs</a>
    <h1 style="margin-top:8px">${escapeHtml(p.name)}</h1>
    <p class="subtitle">${escapeHtml(progKey)}${escapeHtml(codeLabel)} · ${escapeHtml(p.level || "")}</p>
  `];

  // Pathway info (for Grad Certs)
  if (p.pathway_to) {
    const dest = taxonomy.programs[p.pathway_to];
    const destName = dest ? dest.name : p.pathway_to;
    parts.push(`<p class="muted small" style="margin-top:-8px">Pathway to: <a href="program.html?program=${encodeURIComponent(p.pathway_to)}">${escapeHtml(destName)}</a></p>`);
  }

  // Helper: render a named course-list section
  function renderSection(title, codes) {
    if (!codes || !codes.length) return;
    parts.push(`
      <div class="card">
        <h2>${escapeHtml(title)} <span class="muted small">(${codes.length})</span></h2>
        <table class="assessment">
          <thead><tr><th>Code</th><th>Title</th><th>Units</th><th>Mode</th><th>AoL</th></tr></thead>
          <tbody>${codes.map(renderCourseRow).join("")}</tbody>
        </table>
      </div>
    `);
  }

  renderSection("Core courses", p.core);
  renderSection("Foundational courses", p.foundational_courses);
  renderSection("Flexible core", p.flexible_core);
  renderSection("Flexible core A", p.flexible_core_a);
  renderSection("Flexible core B", p.flexible_core_b);
  renderSection("Capstone", p.capstone);
  renderSection("Program electives", p.program_electives);
  renderSection("Research courses", p.research_courses);
  renderSection("Advanced courses", p.advanced_courses);
  renderSection("General pathway courses", p.general_pathway_courses);
  renderSection("Pathway prerequisites", p.pathway_prerequisites);

  if (p.majors && Object.keys(p.majors).length) {
    // Use contextual heading based on programme level
    const majorHeading = (p.level === "PG") ? "Fields / Specialisations" : "Majors";
    parts.push(`<h2>${majorHeading}</h2>`);
    for (const [major, codes] of Object.entries(p.majors)) {
      if (!codes.length) {
        parts.push(`
          <div class="card major-section">
            <h3>${escapeHtml(major)} <span class="muted small">(no courses listed)</span></h3>
            <p class="muted small"><em>Course list not available — see my.UQ for details.</em></p>
          </div>
        `);
      } else {
        parts.push(`
          <div class="card major-section">
            <h3>${escapeHtml(major)} <span class="muted small">(${codes.length})</span></h3>
            <table class="assessment">
              <thead><tr><th>Code</th><th>Title</th><th>Units</th><th>Mode</th></tr></thead>
              <tbody>${codes.map(renderCourseRow).join("")}</tbody>
            </table>
          </div>
        `);
      }
    }
  }

  if (p.electives && p.electives.length) {
    renderSection("Electives", p.electives);
  }

  $root.innerHTML = parts.join("");
}

// =========================================================================
// Display mode — one control cycling Auto → Light → Dark → Fun.
// "Fun" is the dark-neon theme; Auto/Light/Dark are the classic theme with the
// matching palette. Shared across all pages and both editions.
// =========================================================================
const MODES = ["auto", "light", "dark", "fun"];
const MODE_LABELS = { auto: "Auto", light: "Light", dark: "Dark", fun: "Fun" };
const MODE_ICONS = { auto: "☾", light: "☀", dark: "●", fun: "✦" };
const MODE_STORAGE_KEY = "uqbs-mode";

// Synthwave neon pairs [primary, secondary]. Fun rolls one of these each time
// it's selected, so the accent colours vary while the look stays coherent.
const FUN_PALETTES = [
  ["#ff4fd8", "#2de2e6"], // pink + cyan
  ["#b16bff", "#5cf08a"], // violet + green
  ["#ff9f45", "#45c8ff"], // orange + sky
  ["#2de2e6", "#ff4fd8"], // cyan + pink
  ["#c08cff", "#34e7e7"], // violet + cyan
  ["#ff5e5e", "#4d9fff"], // coral + blue
  ["#5cf08a", "#b16bff"], // green + violet
  ["#ffd23f", "#ff4fd8"], // gold + pink
];
const FUN_PALETTE_KEY = "uqbs-fun-palette";

function applyFunPalette(i) {
  const n = FUN_PALETTES.length;
  const p = FUN_PALETTES[((i % n) + n) % n];
  const r = document.documentElement;
  r.style.setProperty("--neon-1", p[0]);
  r.style.setProperty("--neon-2", p[1]);
}
function clearFunPalette() {
  const r = document.documentElement;
  r.style.removeProperty("--neon-1");
  r.style.removeProperty("--neon-2");
}
function rollFunPalette() {
  const i = Math.floor(Math.random() * FUN_PALETTES.length);
  try { localStorage.setItem(FUN_PALETTE_KEY, String(i)); } catch (_) { /* ignore */ }
  applyFunPalette(i);
}
function storedFunPalette() {
  try {
    const v = parseInt(localStorage.getItem(FUN_PALETTE_KEY), 10);
    if (!isNaN(v)) { applyFunPalette(v); return; }
  } catch (_) { /* ignore */ }
  rollFunPalette();
}

function getMode() {
  try {
    const stored = localStorage.getItem(MODE_STORAGE_KEY);
    if (MODES.includes(stored)) return stored;
  } catch (_) { /* ignore */ }
  if (document.documentElement.getAttribute("data-theme") === "fun") return "fun";
  const cm = document.documentElement.getAttribute("data-color-mode");
  return MODES.includes(cm) ? cm : "auto";
}

function applyMode(mode) {
  if (!MODES.includes(mode)) mode = "auto";
  const root = document.documentElement;
  if (mode === "fun") {
    root.setAttribute("data-theme", "fun");
    root.removeAttribute("data-color-mode");
    rollFunPalette();   // new neon pair each time Fun is chosen
  } else {
    root.setAttribute("data-theme", "classic");
    if (mode === "light" || mode === "dark") root.setAttribute("data-color-mode", mode);
    else root.removeAttribute("data-color-mode");
    clearFunPalette();
  }
  try { localStorage.setItem(MODE_STORAGE_KEY, mode); } catch (_) { /* ignore */ }
  updateModeButton(mode);
}

function updateModeButton(mode) {
  const $btn = document.getElementById("mode-toggle");
  if (!$btn) return;
  const $label = $btn.querySelector(".mt-label");
  const $icon = $btn.querySelector(".mt-icon");
  if ($label) $label.textContent = MODE_LABELS[mode];
  if ($icon) $icon.textContent = MODE_ICONS[mode];
  const next = MODES[(MODES.indexOf(mode) + 1) % MODES.length];
  $btn.title = `Display: ${MODE_LABELS[mode]} (click for ${MODE_LABELS[next]})`;
  $btn.setAttribute("aria-label", `Display mode: ${MODE_LABELS[mode]}. Click to switch to ${MODE_LABELS[next]}.`);
}

function initMode() {
  const mode = getMode();
  if (mode === "fun") storedFunPalette();  // keep the chosen pair stable across pages
  updateModeButton(mode);
  const $btn = document.getElementById("mode-toggle");
  if ($btn && !$btn.dataset.modeBound) {
    $btn.dataset.modeBound = "1";
    $btn.addEventListener("click", () => {
      const cur = getMode();
      applyMode(MODES[(MODES.indexOf(cur) + 1) % MODES.length]);
    });
  }
}

if (typeof document !== "undefined") {
  initMode();
}

// =========================================================================
// Page: AOL DASHBOARD (aol.html)
// =========================================================================
async function initAol() {
  const $root = document.getElementById("aol-root");
  try {
    const [manifest, taxonomy, aol] = await Promise.all([
      loadManifest(), loadTaxonomy(), loadAol(), loadTeachingPeriods().catch(() => null)
    ]);
    STORE.allCourses = getAllCourses(manifest);
    STORE.taxonomy = taxonomy;
    STORE.aol = aol;
    renderAolDashboard($root, aol, taxonomy, STORE.allCourses);
  } catch (err) {
    $root.innerHTML = `<div class="error">Error: ${escapeHtml(err.message)}</div>`;
    console.error(err);
  }
}

function renderAolDashboard($root, aol, taxonomy, courses) {
  if (!aol || !aol.semesters || !Object.keys(aol.semesters).length) {
    $root.innerHTML = `
      <h1>Assurance of Learning Dashboard</h1>
      <div class="card"><p>No AoL data loaded. Add entries to <code>taxonomy/aol-template.csv</code> and run <code>python scraper/import_aol.py</code>.</p></div>
    `;
    return;
  }

  const coursesByCode = {};
  for (const c of courses) coursesByCode[c.course_code] = c;

  const parts = [];
  parts.push(`<h1>Assurance of Learning Dashboard</h1>`);

  // Summary stats across all semesters
  const allEntries = [];
  for (const [sem, data] of Object.entries(aol.semesters)) {
    for (const e of (data.entries || [])) {
      allEntries.push({ ...e, semester_code: sem, semester_label: data.label });
    }
  }

  const statusCounts = {};
  const gaCounts = {};
  const uniqueCourses = new Set();
  for (const e of allEntries) {
    statusCounts[e.status] = (statusCounts[e.status] || 0) + 1;
    gaCounts[e.ga] = (gaCounts[e.ga] || 0) + 1;
    uniqueCourses.add(e.course_code);
  }

  parts.push(`
    <div class="stat-bar">
      <div class="stat"><b>${allEntries.length}</b><span>AoL entries</span></div>
      <div class="stat"><b>${uniqueCourses.size}</b><span>courses with AoL</span></div>
      <div class="stat"><b>${Object.keys(aol.semesters).length}</b><span>semester${Object.keys(aol.semesters).length === 1 ? '' : 's'}</span></div>
    </div>
  `);

  // Status summary cards
  const statusOrder = Object.keys(AOL_STATUS);
  const statusCards = statusOrder.map(s => {
    const info = AOL_STATUS[s] || {};
    const count = statusCounts[s] || 0;
    return `<div class="aol-stat-card ${info.cls || ''}"><div class="aol-stat-icon">${info.icon || '?'}</div><div class="aol-stat-count">${count}</div><div class="aol-stat-label">${escapeHtml(info.label || s)}</div></div>`;
  }).join("");
  parts.push(`<div class="aol-status-summary">${statusCards}</div>`);

  // Per-semester sections
  for (const [sem, data] of Object.entries(aol.semesters).sort(([a],[b]) => b.localeCompare(a))) {
    const entries = data.entries || [];
    if (!entries.length) continue;

    // Group by programme (via taxonomy)
    const byProg = {};
    const noProg = [];
    for (const e of entries) {
      const progRoles = taxonomy && taxonomy.course_programs ? (taxonomy.course_programs[e.course_code] || []) : [];
      if (progRoles.length) {
        for (const r of progRoles) {
          byProg[r.program] = byProg[r.program] || [];
          byProg[r.program].push(e);
        }
      } else {
        noProg.push(e);
      }
    }

    parts.push(`<h2>${escapeHtml(data.label || sem)}</h2>`);

    // GA coverage heatmap for this semester
    const gaNames = aol._metadata?.graduate_attributes || {};
    const gas = ["GA1", "GA2", "GA3", "GA4", "GA5", "GA6"];
    const semGaCounts = {};
    for (const e of entries) {
      semGaCounts[e.ga] = (semGaCounts[e.ga] || 0) + 1;
    }
    const gaHeatRow = gas.map(g => {
      const n = semGaCounts[g] || 0;
      const label = gaNames[g] || g;
      const intensity = n === 0 ? "aol-heat-0" : n <= 2 ? "aol-heat-1" : n <= 4 ? "aol-heat-2" : "aol-heat-3";
      return `<td class="aol-heat ${intensity}" title="${escapeHtml(label)}: ${n} course${n === 1 ? '' : 's'}">${g}<br><b>${n}</b></td>`;
    }).join("");
    parts.push(`
      <div class="card">
        <h3 style="margin-top:0">GA Coverage</h3>
        <table class="aol-heatmap"><tr>${gaHeatRow}</tr></table>
      </div>
    `);

    // Full entry table for this semester
    const rows = entries.map(e => {
      const info = AOL_STATUS[e.status] || {};
      const c = coursesByCode[e.course_code];
      const courseLink = c ? `<a href="course.html?file=${encodeURIComponent(c.file)}">${escapeHtml(e.course_code)}</a>` : escapeHtml(e.course_code);
      const progRoles = taxonomy && taxonomy.course_programs ? (taxonomy.course_programs[e.course_code] || []) : [];
      const progChips = progRoles.slice(0, 2).map(r => `<span class="chip">${escapeHtml(r.program)}</span>`).join(" ");
      return `<tr>
        <td class="code">${courseLink}</td>
        <td>${c ? escapeHtml(c.course_title || '') : '<span class="muted">—</span>'}</td>
        <td>${aolGaChip(e.ga)}</td>
        <td>${escapeHtml(e.assessment_title)}</td>
        <td><span class="aol-chip ${info.cls || ''}">${info.icon || ''} ${escapeHtml(info.label || e.status)}</span></td>
        <td>${e.rubric_url ? `<a href="${escapeHtml(e.rubric_url)}" target="_blank" rel="noopener">Rubric ↗</a>` : ''}</td>
        <td>${progChips}</td>
      </tr>`;
    }).join("");

    parts.push(`
      <div class="card">
        <h3 style="margin-top:0">All AoL Entries</h3>
        <table class="assessment aol-table">
          <thead><tr><th>Code</th><th>Title</th><th>GA</th><th>Assessment</th><th>Status</th><th>Rubric</th><th>Programs</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `);
  }

  $root.innerHTML = parts.join("");
}

// =========================================================================
// Page: ALL-OF-UQ BROWSER (browse-all.html)
// =========================================================================
async function initAllBrowser() {
  const $body = document.getElementById("courses-body");
  const $count = document.getElementById("course-count");
  const $meta = document.getElementById("meta-info");
  try {
    const [manifest, taxonomy] = await Promise.all([loadManifestAll(), loadTaxonomyAll().catch(() => null), loadTeachingPeriods().catch(() => null)]);
    const courses = getAllCourses(manifest);
    STORE.allCourses = courses;
    STORE.taxonomy = taxonomy;   // all-UQ program/major taxonomy (all-programs.json)
    STORE.aol = null;
    $meta.innerHTML = `<span>Scrape generated</span> <b>${escapeHtml(fmtDate(manifest.generated_at))}</b> <span>· ${manifest.total_profiles} profiles</span>`;

    // Populate filter dropdowns
    populateSelect("filter-level", uniqueSorted(courses.map(c => c.study_level)));
    populateSelect("filter-mode", uniqueSorted(courses.map(c => c.attendance_mode)));
    populateSelect("filter-location", uniqueSorted(courses.map(c => c.location)));
    populateSelect("filter-school", uniqueSorted(courses.map(c => c.coordinating_unit)));
    if (taxonomy && taxonomy.course_programs) {
      const progs = new Set();
      for (const lst of Object.values(taxonomy.course_programs)) {
        for (const r of lst) progs.add(r.program);
      }
      populateSelect("filter-program", [...progs].sort().map(p => ({ value: p, label: p })));
    }

    // Populate semester filter and default to most recent
    const semCodes = uniqueSorted(courses.map(c => c.semester_code));
    const semOpts = semCodes.map(code => {
      const sample = courses.find(c => c.semester_code === code);
      return { value: code, label: sample ? semesterLabel(sample) : code };
    });
    populateSelect("filter-semester", semOpts);
    const $semFilter = document.getElementById("filter-semester");
    if ($semFilter && semCodes.length) {
      // Default to S1 2026 (7620) when present, else the most recent semester.
      $semFilter.value = semCodes.includes("7620") ? "7620" : semCodes[semCodes.length - 1];
    }

    // Initial render
    STORE.sort = { key: "course_code", dir: "asc" };
    STORE.renderFn = renderAllBrowser;
    bindAllBrowserControls();
    renderAllBrowser();
  } catch (err) {
    $body.innerHTML = `<tr><td colspan="10" class="error">Error loading data: ${escapeHtml(err.message)}</td></tr>`;
    console.error(err);
  }
}

function bindAllBrowserControls() {
  for (const id of ["search", "filter-semester", "filter-level", "filter-mode", "filter-location", "filter-school", "filter-program"]) {
    const el = document.getElementById(id);
    if (el) el.addEventListener("input", renderAllBrowser);
  }
  document.querySelectorAll("table.courses th[data-sort]").forEach(th => {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      if (STORE.sort.key === key) {
        STORE.sort.dir = STORE.sort.dir === "asc" ? "desc" : "asc";
      } else {
        STORE.sort = { key, dir: "asc" };
      }
      renderAllBrowser();
    });
  });
  // CSV export
  const $export = document.getElementById("export-csv");
  if ($export) $export.addEventListener("click", exportAllFilteredAsCsv);
  const $zipMd = document.getElementById("export-zip-md");
  if ($zipMd) $zipMd.addEventListener("click", () => exportFilteredAsZip("md"));
  const $zipJson = document.getElementById("export-zip-json");
  if ($zipJson) $zipJson.addEventListener("click", () => exportFilteredAsZip("json"));
  setupSelection();
}

function applyAllFilters(courses) {
  const q = (document.getElementById("search")?.value || "").trim().toLowerCase();
  const sem = document.getElementById("filter-semester")?.value;
  const level = document.getElementById("filter-level")?.value;
  const mode = document.getElementById("filter-mode")?.value;
  const loc = document.getElementById("filter-location")?.value;
  const school = document.getElementById("filter-school")?.value;
  const prog = document.getElementById("filter-program")?.value;

  return courses.filter(c => {
    if (q) {
      const hay = `${c.course_code} ${c.course_title || ""} ${c.coordinating_unit || ""}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    if (sem && c.semester_code !== sem) return false;
    if (level && c.study_level !== level) return false;
    if (mode && c.attendance_mode !== mode) return false;
    if (loc && c.location !== loc) return false;
    if (school && c.coordinating_unit !== school) return false;
    if (prog && STORE.taxonomy && STORE.taxonomy.course_programs) {
      const roles = STORE.taxonomy.course_programs[c.course_code] || [];
      if (!roles.some(r => r.program === prog)) return false;
    }
    return true;
  });
}

function renderAllBrowser() {
  const $body = document.getElementById("courses-body");
  const $count = document.getElementById("course-count");
  const courses = applySort(applyAllFilters(STORE.allCourses || []));
  STORE.filtered = courses;
  $count.textContent = courses.length;

  if (courses.length === 0) {
    $body.innerHTML = `<tr><td colspan="10" class="empty">No courses match the current filters.</td></tr>`;
    updateSortIndicators();
    refreshSelectionUI();
    return;
  }

  const taxonomy = STORE.taxonomy;
  const rows = courses.map(c => {
    const levelClass = (c.study_level || "").toLowerCase().includes("post") ? "level-pill pg" : "level-pill";
    const pfx = coursePrefix(c.course_code);
    const codeCls = pfx ? `code prefix-${pfx}` : "code";
    const semLabel = semesterLabel(c);
    const school = c.coordinating_unit || "";
    const roles = taxonomy ? programRolesFor(c.course_code, taxonomy) : [];
    const progChips = roles.slice(0, 3).map(r => {
      const hue = hueForProgram(r.program);
      const label = r.role ? `${r.program}: ${r.role}` : r.program;
      const title = `${r.program_name || r.program}${r.role ? " — " + r.role : ""}`;
      return `<span class="chip" style="--chip-hue:${hue}" title="${escapeHtml(title)}">${escapeHtml(label)}</span>`;
    }).join(" ");
    const progMore = roles.length > 3 ? `<span class="chip muted">+${roles.length - 3}</span>` : "";
    return `
      <tr>
        ${selCell(c)}
        <td class="${codeCls}"><a href="course.html?file=${encodeURIComponent(c.file)}">${escapeHtml(c.course_code || "")}</a></td>
        <td>${escapeHtml(c.course_title || "")}</td>
        <td class="nowrap">${escapeHtml(semLabel)}</td>
        <td><span class="${levelClass}">${escapeHtml(c.study_level || "")}</span></td>
        <td>${escapeHtml(c.units || "")}</td>
        <td>${escapeHtml(c.attendance_mode || "")}</td>
        <td>${escapeHtml(c.location || "")}</td>
        <td class="school-col">${escapeHtml(school)}</td>
        <td>${progChips}${progMore}</td>
      </tr>`;
  }).join("");
  $body.innerHTML = rows;
  updateSortIndicators();
  refreshSelectionUI();
}

function exportAllFilteredAsCsv() {
  const courses = coursesForExport(STORE.filtered || []);
  if (!courses.length) return;
  const headers = ["course_code", "course_title", "semester_code", "study_level", "units", "attendance_mode", "location", "coordinating_unit"];
  const csvRows = [headers.join(",")];
  for (const c of courses) {
    const row = headers.map(h => {
      const v = c[h] ?? "";
      return `"${String(v).replace(/"/g, '""')}"`;
    });
    csvRows.push(row.join(","));
  }
  downloadBlob(csvRows.join("\n"), "uq-all-courses.csv", "text/csv;charset=utf-8");
}

// Export to window so inline <script> hooks can call them
window.UQBS = {
  initBrowser,
  initAllBrowser,
  initCourseDetail,
  initProgram,
  initAol,
  initMode,
  applyMode,
  // exposed for tests
  offeringChronKey,
  buildCourseTimeline,
  getLegacyCourses,
  computeOfferingDiff,
  renderOfferingDiff,
  EDITION,
  renderNav,
  dataUrl,
};

// Render the header nav from the edition, so the markup stays identical across
// pages and the dual-build needs no HTML surgery. The UQBS edition shows the
// AoL + Programs tabs; the All-UQ edition is a lean course browser.
function renderNav() {
  if (typeof document === "undefined") return;
  const page = (document.body && document.body.dataset.page) || "";
  if (page === "landing") return; // the splash front door has no section nav
  const nav = document.querySelector("header.site nav");
  if (!nav) return;
  const repoUrl = SITE.repoUrl || "https://github.com/UQ-Business-School/uqbs-course-profiles";
  // One site, both dashboards as sub-pages.
  const links = [
    ["index.html", "⌂ Home", "_home"],
    ["business.html", "UQBS", "home"],
    ["browse-all.html", "All UQ", "all"],
    ["program.html", "Programs", "programs"],
    ["aol.html", "AoL", "aol"],
  ];
  const html = links
    .map(([href, label, key]) => `<a href="${href}"${key === page ? ' class="active"' : ""}>${escapeHtml(label)}</a>`)
    .join("\n      ")
    + `\n      <a href="${escapeHtml(repoUrl)}" target="_blank" rel="noopener">Repository ↗</a>`;
  nav.insertAdjacentHTML("afterbegin", html + "\n      ");
}

(function initChrome() {
  if (typeof document === "undefined") return;
  const run = () => { try { renderNav(); } catch (_e) { /* non-fatal */ } };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run);
  else run();
})();
