# Project Log — UQBS Course Profile Scraper

> **Last updated:** 2026-06-08 (Session 17) — **State audit + two-edition architecture decided.** Verified against the live site + GitHub API: the Session 16 timeline + diff is PUSHED & LIVE (commit 7fa6b52f, 2026-06-06 — #46 closed); the previous header saying it was local-only was stale. Live counts: UQBS 873 / all-UQ 8,020 / legacy 5,288. NOTE: `taxonomy/aol-status.json` was never committed — it is local-only sample/placeholder data, so no real AoL data is or was public. Next: split the viewer into two audience editions (All-UQ public + UQBS) from one codebase (#47–#49).
> _Prior (Session 16):_ Legacy data integrated into the viewer (#43 + #45 CLOSED): per-course timeline (walk a course 2009→2026, title-changes flagged, legacy badged) + an offering diff view (pick any two, see assessment add/drop/change, weight + LO shifts). Separate `manifest-legacy.json` keeps the live UQBS viewer unaffected. Sessions 12–15 PUSHED (#39 closed, range 02b1f575..31b58be9).
> **Project:** UQBS Course Profile Viewer and Learning Design Intelligence Platform
> **Tech stack:** Python 3 / BeautifulSoup / requests / GitHub Actions / GitHub Pages
> **Repository:** [UQ-Business-School/uqbs-course-profiles](https://github.com/UQ-Business-School/uqbs-course-profiles) (transferred from uqsmitc6 in September 2026; Pages now at https://uq-business-school.github.io/uqbs-course-profiles/)

---

## Current State

The scraper is built, tested, and **production-ready**. It extracts a comprehensive field set from UQ course profile pages — significantly richer than Geoff's JacSON scraper (which covers the whole university but with fewer fields). As of Session 9 (2026-06-02), the scraper supports **all of UQ** via the `--all-uq` flag (3,271 courses across 1,750 per semester), while the live UQBS viewer remains completely isolated via dual manifests. The all-of-UQ expansion is driven by ATLAS, a TIG-funded project that consumes this scraper's JSON as its data spine.

As of Session 12 (2026-06-04): all current-system semesters (S2 2024→S2 2026) are scraped and pushed; the LO override layer is **live** with Jac-provenance framing (Jac is the official source — Sean's reframe); the Drupal bug's onset is dated to the **S2 2024 publishing-system cutover** (legacy archive pages render mappings correctly); every offering of every current UQ course back to ~2009 is indexed in `data/offerings-index.json`; all six faculties' current program structures are extracted from Jac (Science's file-write pending, #35); and an overnight fetch of all 5,234 UQBS legacy profiles (to 2009) is caching raw HTML for the legacy parser (#34) — **still running as of 2026-06-05**.

As of Session 16 (2026-06-06): **fifteen years of UQBS profile history is structured data AND browsable.** All 5,288 legacy profiles (2009–S1 2024) are parsed, pushed (#39), and now wired into the viewer via a separate `manifest-legacy.json` and a **per-course timeline** that lets you walk a course across 2009→2026 in one view, with title-change events flagged and legacy profiles badged. The build is local-only pending a push (#46); the diff view (#45) is the next analytical layer.

**Evolving vision:** The project started as a way to easily navigate published ECPs and download info from the browser (the bulk export is a standout feature). It's now actively becoming a **learning design intelligence platform** for the UQBS team. Two overlay data layers are now built and integrated: **Assurance of Learning (AoL)** and the **LO-to-assessment override** layer (Session 10, patches UQ's Drupal bug that drops LO mappings fully or partially). The AoL layer uses an overlay architecture: team maintains a CSV (`taxonomy/aol-template.csv`), an import script converts it to JSON (`taxonomy/aol-status.json`), and the viewer loads it at runtime to show AoL status across course, programme, and dashboard views. This same pattern will be used for GA mapping, assessment typologies, Indigenous curriculum tracking, and assessment security classification.

**AoL lifecycle:** TBD → Identified → Rubric in Dev → Active → Established. Grain: semester + course + GA + assessment item + rubric link. Data starts from Sem 1 2026 onwards. If a mapping doesn't go ahead, the row is simply removed (no "disrupted" or "N/A" status needed).

**GA vs AoL relationship (confirmed with AD L&T):** GA mapping is broader than AoL and persists independently — it's about constructive alignment against PLOs. AoL is a subset that gets the full rubric integration treatment. More GAs will be mapped than AoL implemented in most cases. The goal is for all GAs to be covered by some AoL criteria, but not necessarily all within a single assessment. GA mapping is a precursor to AoL, but GA mapping will continue to exist and matter even after AoL is fully rolled out. All courses targeted for AoL mapping starting Sem 2 2026.

### Key Architecture Decisions in Effect

- "Standalone repo, separate from Geoff's JacSON" — decided 2026-04-13. Keeps UQBS-enriched data independent from university-wide scrapes.
- "GitHub Actions as primary runner" — confirmed working 2026-04-13. UQ's `course-profiles.uq.edu.au` domain is accessible from GitHub Actions runners (Geoff's concern about IP blocking applies to `programs-courses.uq.edu.au`, not course profiles).
- "GitHub Tree API for URL discovery" — decided 2026-04-13. Uses Geoff's JacSON repo file listing to find profile URLs (class codes + semester codes) instead of hitting `programs-courses.uq.edu.au` which returns 405 from GitHub Actions.
- "Course list from taxonomy JSON" — decided 2026-04-13, overhauled 2026-04-15. Uses uqbs-programs.json (323 courses, 23 programmes) as source of truth for UQBS scrapes. Verified against my.UQ structured data for all programmes.
- "All-of-UQ via JacSON index" — decided 2026-06-02. `--all-uq` flag bypasses taxonomy and uses full JacSON repo index (3,271 courses, 1,750 in current semester). UQBS taxonomy remains the filter for the viewer manifest.
- "Dual manifests — keep 'em separated" — decided 2026-06-02. `manifest.json` is UQBS-only (powers the live viewer, never affected by all-of-UQ data). `manifest-all.json` is everything (consumed by ATLAS). Built from a single scan of profiles/.
- "Local Mac for historical backfill, Actions for ongoing" — decided 2026-06-02. One-off historical semester scrapes run locally (~15 min per semester at --delay 0.5). Weekly cron stays UQBS-only by default; all-of-UQ available via manual dispatch.
- "Local Mac runner kept as secondary option" — script and launchd plist available for local runs.
- "Overlay architecture for internal data layers" — decided 2026-04-15. Each data layer (AoL, GA, typologies, etc.) has its own CSV→JSON import pipeline and JSON overlay file, loaded by the viewer at runtime. Keeps each layer independently updatable and avoids bloating uqbs-programs.json.
- "AoL lifecycle: TBD → Identified → Rubric in Dev → Active → Established" — decided 2026-04-15, TBD added after team feedback. Simpler than textbook AACSB 5-stage model; matches UQBS team's actual workflow. "Disrupted" status removed — unmapped items are simply deleted.
- "AoL data starts Sem 1 2026 onwards" — decided 2026-04-15. No need to backfill historical data.

---

## Open Items

| # | Category | Description | Since | Priority | Notes |
|---|----------|-------------|-------|----------|-------|
| 1 | DONE | ~~First live test run~~ | 2026-04-13 | — | Completed via GitHub Actions (5 runs) |
| 2 | DONE | ~~Verify LO extraction across layouts~~ | 2026-04-13 | — | Fixed off-by-one bug; tested against both server HTML and browser DOM |
| 3 | DONE | ~~Create GitHub repo and push initial code~~ | 2026-04-13 | — | Repo: uqsmitc6/uqbs-course-profiles |
| 4 | DONE | ~~Run a broader test (multiple courses, e.g. --max 5)~~ | 2026-04-13 | — | Completed with full semester scrape (Run 9, 202 profiles) |
| 5 | TODO | Set up launchd scheduling on Sean's Mac (optional) | 2026-04-13 | Low | GitHub Actions is primary; local is secondary |
| 6 | NOTE | GA mapping in taxonomy spreadsheet is draft/WIP | 2026-04-13 | Info | Program-course mappings are correct; GA and typology columns are not finalised |
| 7 | TODO | Consider updating JacSON Viewer to read from this repo's enriched data | 2026-04-13 | Low | Future integration |
| 8 | DONE | ~~Update README.md~~ | 2026-04-13 | — | Session 16: README now documents the legacy parser, profiles-legacy/ output, the third manifest, and the timeline + diff features; deploy section covers profiles-legacy staging |
| 9 | DONE | ~~Post-deploy bug fixes: LO codes, assessment→LO mapping, policy-text run-ons~~ | 2026-04-14 | — | All three fixed in Session 6 |
| 10 | DONE | ~~Viewer polish: Classic/Fun theme, downloads, dark-mode toggle~~ | 2026-04-14 | — | Shipped in Session 6 |
| 11 | DONE | ~~Taxonomy overhaul: 14→23 programmes, verified against my.UQ~~ | 2026-04-15 | — | Shipped in Session 7 |
| 12 | TODO | Populate empty major course lists (BAFE Economics/Finance, 3 MEI fields) | 2026-04-15 | Low | my.UQ only provides plan codes, not individual courses |
| 13 | DONE | ~~Add missing program_code values to 11 legacy programmes~~ (9 of 11) | 2026-04-15 | — | Session 14: 9 codes added from Jac program-rules (BBusMan 2171, BCom 2336, BTHEM 2473, MBus 5583, MCom 5584, MEI 5690, MBA 5770, MBusAn 5188, MTHEM 5585). 'Elective' and 'Grad Dip' aren't real programs — no codes exist |
| 14 | TODO | **Graduate Attribute (GA) mapping** — integrate GA data into taxonomy/viewer | 2026-04-15 | High | See Phase 3A below |
| 15 | DONE | ~~**Assurance of Learning (AoL) mapping** — semester-aware status tracking~~ | 2026-04-15 | — | Shipped in Session 8: overlay architecture, import script, viewer integration, dashboard |
| 16 | TODO | **Assessment typologies mapping** | 2026-04-15 | Med | See Phase 3C below |
| 17 | TODO | **Indigenising the curriculum** — tracking and visibility | 2026-04-15 | Med | See Phase 3D below |
| 18 | TODO | **Assessment security** — classification per assessment item | 2026-04-15 | Med | See Phase 3E below |
| 19 | TODO | **Visual redesign** — more colourful Classic mode + radical Fun mode overhaul | 2026-04-15 | Low | Separate project, partially underway |
| 20 | TODO | **Scrape automation audit** — confirm weekly cron is running, review what Sean needs to do manually | 2026-04-15 | Med | See "Scrape Automation Status" section |
| 21 | TODO | **Scrape history / change tracking** — decide on approach for maintaining profile history | 2026-04-15 | Med | See "Scrape History" section |
| 22 | DONE | ~~**All-of-UQ scraper expansion** — --all-uq flag, dual manifests, --delay flag~~ | 2026-06-02 | — | Shipped in Session 9 |
| 23 | DONE | ~~**Backfill historical semesters** — run --all-uq locally for semesters 7450–7620~~ | 2026-06-02 | — | Session 12: all current-system semesters (S2 2024→S2 2026) backfilled & pushed. 7450=0 by design (pre-cutover; legacy system) |
| 24 | TODO | **Switch weekly cron to all-of-UQ** — once backfill is verified, update cron default | 2026-06-02 | Med | Currently cron stays UQBS-only for safety |
| 25 | DONE | ~~**All-of-UQ browser page** — browse-all.html with school filter~~ | 2026-06-02 | — | Shipped in Session 9 |
| 26 | DONE | ~~**LO-to-assessment override system** — manual CSV overrides for courses where Drupal doesn't render the mapping~~ | 2026-06-02 | — | Shipped in Session 10: replace-per-assessment overlay + coverage diagnostic |
| 27 | DONE | ~~**Backfill remaining semesters** — 7450, 7460, 7480, 7490, 7520, 7560, 7580, 7590, 7660~~ | 2026-06-02 | — | Session 12: done & pushed. 7490/7590 saved nothing ('S'-suffix course codes rejected by regex — minor fix, parked) |
| 28 | DONE | ~~**Fill in LO override CSV**~~ | 2026-06-03 | — | Session 11: all 135 rows filled from Jac API, 0 warnings |
| 29 | DONE | ~~**Review 9 suspected-partial courses**~~ | 2026-06-03 | — | Session 11: 8 MISSING_SOME filled from Jac; ECON3430 verified correct (LO5/6 genuinely unassessed) |
| 30 | DONE | ~~**Persist activity-to-LO mapping**~~ | 2026-06-03 | — | Saved to `taxonomy/sources/activity-lo-mapping-jac-7620.json` (43 courses, 753 rows) via gzip+base64 transfer |
| 31 | DONE | ~~**Commit & push the filled overrides**~~ | 2026-06-03 | — | Session 12: pushed (commits 5839218 + a4f2d37 incl. Jac-reframe). Live & verified; ATLAS merged the overlay |
| 32 | NOTE | **MBA courses are a special case** — run multiple offerings per semester (weekend/intensive/teaching periods) with *different* assessments; use SI-NET class-number matching, not semester-period matching | 2026-06-03 | Med | `jac_extract.js` now supports `{code:[classNumber]}` matching; MGTS7812 was the example this round |
| 33 | DONE | ~~rsync legacy cache when overnight fetch finishes~~ | 2026-06-04 | — | Done by Sean before Session 15: cache verified in the Cowork folder (5,288 profiles × 6 sections = 31,728 files, exact) |
| 34 | DONE | ~~**Build legacy ECP parser**~~ | 2026-06-04 | — | Session 15: `scraper/parse_legacy.py` built, verified (470-profile independent cross-check, 0 mismatches), batch-run over all 5,288 → `profiles-legacy/{year}-{period}/`, 0 errors. Incl. native LO mappings, GA-to-LO matrices, activity-to-LO refs |
| 35 | DONE | ~~**Land the Science faculty file**~~ | 2026-06-04 | — | Session 14: `taxonomy/sources/sci-programs-jac-202601.json` (62 programs, 1,244 courses in compact reverse map, 3 cross-ref Grad Certs flagged). Per-chunk checksums caught a 1-char transcription error; gzip-verified clean. All six faculty files now on disk — push via #39 |
| 36 | DONE | ~~**Broken-era UQBS LO backlog**~~ (UQBS portion) | 2026-06-05 | — | Session 14: 108 offerings / 340 mappings filled & verified, incl. class-scoped overrides + stale-matrix audit. All-of-UQ scope (~3,000) remains a separate decision |
| 37 | TODO | **Recurring per-semester LO patch routine** — S2 2026+ publishes broken weekly while UQ's Drupal bug lives; run coverage report after bulk publish, batch-extract gaps from Jac, push | 2026-06-05 | Med | ~20 min/semester with existing machinery |
| 38 | TODO | **Program-rules time series** — extract ALL versions (not just current) per program, diff consecutive versions for course movements (core↔major etc.); Jac retains versions with effective dates back to ~2021 | 2026-06-05 | Med | Same machinery minus the current-version filter. Pre-2021 structure not recoverable from Jac (pre-dates the system) |
| 39 | DONE | ~~**Push the Sessions 12–15 local-only work**~~ | 2026-06-04 | — | Pushed 2026-06-06 (range 02b1f575..31b58be9): code/taxonomy/data commit + separate profiles-legacy commit (31b58be9, 5,288 files, 40.7 MiB pack). Cache correctly excluded |
| 40 | DONE | ~~**Deleted-courses Jac org-pull (UQBS, org 29)**~~ | 2026-06-03 | — | Session 14: 3,450 instances pulled; 59 discontinued / 5 newborn / 2 indeterminate classified → `taxonomy/sources/uqbs-deleted-courses-jac.json`. Residue check (which still have archive pages) = Sean's `--codes-file` run on the Mac |
| 41 | DONE | ~~**Wire teaching-periods.json into viewer**~~ | 2026-06-04 | — | Session 14: app.js loads the registry (5 init sites); semesterLabel uses registry `short` (fixes 7480 'Sum 2025'→'Sum 24/25', adds 7490/7590 medical labels); hardcoded map kept as last-resort fallback. 7/7 sandbox tests |
| 42 | TODO | **Program-rules time series, the SelectionList unlock** — historical (pre-~2024) rule records hold UUIDs only; capture the UI's list-resolution endpoint on a historical record, then batch all versions for the 21 UQBS programs and diff | 2026-06-05 | Med | Probe findings + recipe in 2026-06-05 FINDING entry. Supersedes the extraction half of #38 |
| 43 | DONE | ~~**Integrate profiles-legacy into the viewer/manifests**~~ | 2026-06-06 | — | Session 16: `manifest-legacy.json` builder (separate from UQBS/all), Pages + serve_local plumbing, per-course timeline (current+legacy offerings, chronological, title-change events), legacy provenance badge. Node-sandbox + local-serve verified. Local-only until pushed |
| 45 | DONE | ~~**Timeline v2 — the diff view**~~ | 2026-06-06 | — | Session 16: compare control under the timeline; `computeOfferingDiff` (older→newer orientation, title-matched assessment add/drop/change incl. weight + LO-set shifts, LO-count + title deltas) + `renderOfferingDiff`. Node-verified on real ACCT1101 2009/2024/2026 |
| 46 | DONE | ~~**Push Session 16 viewer integration (timeline + diff)**~~ | 2026-06-06 | — | Pushed 2026-06-06 (commit 7fa6b52f); Pages redeployed, timeline + diff live. Verified against the live site + GitHub API in Session 17 |
| 47 | DONE | ~~**Edition-flag viewer + dual-build**~~ | 2026-06-08 | — | Session 17: `assets/site-config.js` (edition/dataBase/repoUrl) + app.js `EDITION`/`dataUrl()`/`renderNav()`; nav now app-rendered from edition. `scraper/build_editions.py` emits build/all + build/uqbs. 16/16 Node-sandbox tests + local-serve smoke test pass. Built local-only; deploy is #48 |
| 48 | TODO | **Stand up two fresh repos + auto-mirror** — All-UQ public (ATLAS source) + UQBS edition; UQBS repo auto-mirrors via GitHub Action to the team repo that already mirrors to teach.business.uq.edu.au | 2026-06-08 | High | Sean's infra. Needs team-repo mirror details (trigger, push access / deploy key) |
| 49 | TODO | **Repoint ATLAS to the new All-UQ URL** once it is live | 2026-06-08 | Med | ATLAS currently reads `manifest-all.json` from the old `uqsmitc6.github.io/uqbs-course-profiles` URL |
| 50 | TODO | **Real AoL data source** — replace local sample `aol-status.json` with the team's actual spreadsheet→CSV→JSON before the UQBS edition ships AoL | 2026-06-08 | Med | Confirmed sample/placeholder in Session 17; AoL data starts Sem 1 2026 |
| 44 | TODO | **Decide profiles-legacy QA follow-ups** — 137 profiles have no staff-person block (88% coverage, source-genuine); 22 summary rows source-blank LO cells (list in Session 15 entry); IBUS7302-28119 (2009-S2) has per-stream summary variants (5 rows / 3 details — legitimate) | 2026-06-06 | Low | Nothing blocking; documented for the record |

---

## Phase 3 Roadmap — Learning Design Intelligence Layer

The next major phase turns this from a course profile viewer into a learning design intelligence platform. All of these features involve **internal team data** that isn't published in official UQ systems, so the core architecture challenge is: how do we ingest, store, and update this data without it being a pain to maintain?

### Data Ingestion Strategy (applies to all Phase 3 features)

The team needs to be able to update this data easily — not one course at a time, but by dumping a spreadsheet. Proposed approach:

- **Spreadsheet as source of truth:** Each data layer (GA, AoL, typologies, etc.) has a canonical CSV/XLSX that the team maintains (likely on SharePoint alongside rubrics)
- **Import script:** A Python script (similar to `build_manifest.py`) that reads the spreadsheet and merges it into the taxonomy JSON or a separate overlay JSON
- **Overlay architecture:** Rather than cramming everything into `uqbs-programs.json`, consider separate data files (e.g. `taxonomy/ga-mapping.json`, `taxonomy/aol-status.json`) that the viewer loads and merges at runtime. This keeps each data layer independently updatable
- **Semester awareness:** AoL status in particular changes semester to semester. The data structure needs a semester dimension — e.g. `{ "MGTS1601": { "7620": { "status": "delivered", "rubric_url": "..." }, "7660": { "status": "proposed" } } }`
- **Validation on import:** Script should flag missing courses, unknown programme keys, etc. before writing

### Phase 3A — Graduate Attribute (GA) Mapping

**What:** Each course is mapped to one or more of UQ's Graduate Attributes. This mapping tells us which GAs are assessed in which courses across each programme.

**Current state:** Item #6 notes GA mapping in the taxonomy spreadsheet is draft/WIP. The programme-course mappings are now solid (Session 7), so GA integration can proceed.

**Key considerations:**
- GA mapping is at the course level (which GAs does this course assess?) but the interesting views are at the programme level (GA coverage heatmap across a programme's courses)
- The viewer could show GA chips per course (like the existing programme chips) and a programme-level GA coverage matrix
- GAs are relatively stable across semesters — this is more of a "set and occasionally revise" dataset

### Phase 3B — Assurance of Learning (AoL) Mapping

**What:** AACSB Assurance of Learning tracks whether specific learning goals are being assessed, collected, and reviewed. This is closely related to GA mapping but has its own lifecycle.

**Key considerations:**
- AoL status changes semester to semester: proposed → delivered → collected → reviewed → closed-the-loop
- The mapping is through **rubrics** — each AoL measure is assessed via a rubric criterion in a specific assessment item
- Need to link to rubric files (likely on Teams SharePoint) — so the data structure needs a `rubric_url` or similar field per AoL measure
- The viewer needs a way to show "where are we at across the portfolio this semester" — a status dashboard, not just a per-course view
- Multiple semesters of data need to coexist (to show progress over time for AACSB reporting) but this shouldn't become an infinite backwards database — probably keep 2–3 years / 4–6 semesters and archive older data

### Phase 3C — Assessment Typologies

**What:** Classification of each assessment item by type (e.g. exam, essay, presentation, group project, portfolio, etc.) — richer than what's in the published ECP.

**Key considerations:**
- Some typology data may already be inferrable from the scraped assessment summaries (title patterns, weight, etc.)
- The team likely has a more nuanced classification than what's published
- Useful for portfolio-level views: "how many exams vs. authentic assessments across the programme?"

### Phase 3D — Indigenising the Curriculum

**What:** Tracking which courses have embedded Indigenous perspectives, content, or pedagogies, and to what degree.

**Key considerations:**
- This is sensitive data that should be accurate and not performative
- Likely a per-course flag or scale, possibly with notes on what the Indigenous content involves
- Useful for programme-level reporting on progress toward UQ's reconciliation commitments

### Phase 3E — Assessment Security

**What:** Classification of assessment items by security level (e.g. invigilated exam, online proctored, take-home, open-book, AI-permitted, etc.).

**Key considerations:**
- Relevant to academic integrity discussions and AI policy
- Could partially be inferred from scraped ECP data (exam vs. assignment) but the team likely has more granular classifications
- Changes semester to semester as assessment designs evolve

---

## Scrape Automation Status

**Current setup:** The scraper runs via GitHub Actions on a **weekly cron schedule** (every Sunday at 9 PM AEST / 11:00 UTC). It can also be triggered manually via workflow dispatch with optional filters (specific semester, course codes, or max count for testing).

**What's automated:**
- URL discovery (via Geoff's JacSON repo tree API)
- Profile scraping and JSON output
- Manifest regeneration (`build_manifest.py`)
- Git commit and push of new/updated profiles
- GitHub Pages redeployment (triggered by the push)

**What Sean needs to do manually:** Effectively nothing for routine scrapes. The weekly cron handles it. Manual intervention only needed for: adding new courses to the taxonomy (which triggers inclusion in future scrapes), or running an ad-hoc scrape via the GitHub Actions UI.

**Question to resolve:** Is the weekly cron actually firing? Sean should check the Actions tab for recent automated runs. If it hasn't run since the initial setup, the cron may need the workflow to exist on the default branch.

---

## Scrape History & Change Tracking

**Current behaviour:** Each scrape **overwrites** the existing JSON files in `profiles/{semester}/`. The only history is git commit history — each commit is timestamped and includes a profile count, so you can `git diff` between commits to see what changed. But there's no structured changelog or archive.

**Geoff's approach (JacSON):** Worth investigating — does JacSON maintain historical snapshots or just overwrite?

**Design questions to resolve:**
- **How much history matters?** For the LD team's purposes, do we need to know "MGTS1601's assessment changed between week 3 and week 8 of Sem 1"? Or is "here's the latest for each semester" sufficient?
- **Semester as natural boundary:** Profiles change within a semester (coordinators update ECPs), but the most meaningful comparison is probably semester-over-semester. Consider: keep one "canonical" snapshot per semester (e.g. the week-1 scrape) and flag if later scrapes detect changes.
- **Storage concern:** Sean doesn't want this to become an infinite backwards database or unwieldy. Options: (a) git history only (current — lightweight but hard to query), (b) structured diff log (a JSON changelog per course noting what fields changed and when), (c) semester snapshots (keep `profiles/7620-week1/` alongside `profiles/7620-latest/`), (d) keep N semesters and archive older ones to a separate branch or release.
- **Recommended starting point:** Add a lightweight diff step to the scraper that, after writing updated profiles, generates a `changes.json` summary listing which courses had field changes since last scrape. This gives visibility without storing full historical copies.

---

## Session History

### Session 17 — 2026-06-08 — State audit + two-edition architecture decided

**Focus:** Sean asked for an accurate read of where things actually stand (the docs had drifted), then floated splitting the viewer into two audience editions. Audit + decisions, then built the edition-flag viewer and dual-build (#47, local-only).

**Audit (verified against the live site + GitHub API, not just the docs):**
- **#46 is LIVE, not pending.** Last commit `7fa6b52f` (2026-06-06T03:55Z) is exactly the timeline + diff push; Pages redeployed. The PROJECT_LOG header and the #46 row were stale — both corrected this session.
- Live manifest counts confirmed: UQBS 873 / all-UQ 8,020 / legacy 5,288.
- **AoL data is not, and never was, public.** The viewer scaffolding (AoL tab, table column, dashboard, overlay loader with graceful 404 fallback) is deployed, but `taxonomy/aol-status.json` is **not committed** to `main` (checked the repo contents API) — it lives only in the local working copy and is Session-8 sample/placeholder data (ACCT1101 with dummy SharePoint rubric links). Confirmed sample by Sean. Boarded as #50.
- **GA mapping has no data yet.** No `ga-*.json` overlay exists; the legacy GA-to-LO matrices are raw material only (Phase 3A still to build).
- Architecture confirmed: the public **manifest** is a lean index (no AoL/GA embedded); sensitive layers are runtime overlays only. So stripping them for a public build is trivial.

**Decisions (Sean):**
- Ship **two audience editions** with **fresh repos + URLs for both** (current repo retired): an **All-UQ public** edition (no AoL/GA — ATLAS consumes it) and a **UQBS** edition (with AoL/GA).
- **Not secret** — public repos are fine. The split is about giving each audience a clean view, not access control.
- **Single viewer codebase** with an `EDITION='uqbs'|'all'` flag — no forked copies.
- UQBS edition lives in **one of Sean's own GitHub repos**, auto-mirrored via a GitHub Action to the **team repo** that already mirrors to **teach.business.uq.edu.au**. Chain: Sean's UQBS repo → (Action push) → team repo → (existing mirror) → school server.

**Team repo / server mapping (learned this session):** the UQBS edition's home is the team repo **`UQ-Business-School/courses`**, which auto-mirrors to **`teach.business.uq.edu.au/ld/`** ~15 min after a push (the server pulls; no GitHub Pages or Action involved). Layout is folder-per-thing, each with its own `index.html` (e.g. `acct/index.html` → `/ld/acct/`). Sean's space is **`uqbsld/`** (already holds `nine-things`, `rubrics`, `time-machine`). Plan: the UQBS edition lands in `uqbsld/profiles/` → `teach.business.uq.edu.au/ld/uqbsld/profiles/`. So the earlier "own repo + auto-mirror" idea is optional — pushing the built edition straight into the team repo is enough.

**What was built (#47, local-only — not pushed):**
1. **`docs/assets/site-config.js`** — the one file the build swaps per edition: `{edition, dataBase, repoUrl}`. Source copy is the self-contained UQBS default (so local dev/tests are unchanged). Wired into all five pages before `app.js`.
2. **`docs/assets/app.js`** — added `SITE`/`EDITION`/`DATA_BASE`; `dataUrl(rel)` prefixes bulk data (profile JSONs + `manifest-all`/`manifest-legacy`) with `dataBase` when set, else same-origin; applied to `loadCourseJson`, the raw-JSON link, and the big manifests (primary `manifest.json` + overlays stay local). Nav is now **rendered by `renderNav()` from the edition** (UQBS → UQBS/Programs/AoL tabs; All-UQ → lean All-UQ browser), so the build needs no HTML surgery. Pages tag `<body data-page=…>` for active state.
3. **`scraper/build_editions.py`** — emits `build/all/` (self-contained public, AoL/GA stripped, `browse-all.html`→`index.html`, ATLAS source) and `build/uqbs/` (light: viewer + UQBS manifest + overlays incl. AoL; bulk data fetched from `--all-data-base`). Flags: `--editions`, `--all-data-base`, `--all-repo`, `--uqbs-repo`, `--uqbs-self-contained`, `--skip-data`. `build/` is git-ignored.

**Verification:** `node --check` OK; 16/16 Node-sandbox assertions (EDITION resolves per config incl. no-`SITE` fallback; nav link sets + active state + repo link per edition; `dataUrl` remote vs local incl. leading-`./` strip); structural build correct (all-UQ tree carries no `aol.html`/`program.html`/`aol-status.json`; UQBS tree carries the overlays and only its small `manifest.json`); local-serve smoke test (all/index = All-UQ browser, `aol.html` 404, edition "all"; uqbs/index = UQBS browser, `aol.html` 200, `aol-status.json` 200, `manifest-all.json` 404 locally → fetched remote). UQBS build ~1 MB, all-UQ manifests ~11 MB before profiles.

**Deployment recipe (Sean, when ready — not done yet, this is #48):**
1. Create the two fresh repos (e.g. `uqbsld/profiles` folder in `UQ-Business-School/courses` for UQBS; a new public repo for All-UQ + enable Pages).
2. Decide the All-UQ Pages URL, then build: `python3 scraper/build_editions.py --all-data-base https://<all-uq-pages-url> --all-repo <all-repo-url> --uqbs-repo https://github.com/UQ-Business-School/courses`
3. Push `build/all/` to the All-UQ repo (root or docs/, set Pages source accordingly); push `build/uqbs/` into the team repo's `uqbsld/profiles/`.
4. Confirm CORS works (All-UQ Pages serves `Access-Control-Allow-Origin: *`, so the UQBS edition on teach.business can fetch its profile JSON).
5. Repoint ATLAS to the All-UQ URL (#49); swap the sample `aol-status.json` for real team data before sharing the UQBS edition (#50).

**Landmines / watch out for:**
- UQBS edition depends on the All-UQ host being up for profile data (timeline/diff/course detail). Acceptable; or build it `--uqbs-self-contained` to carry its own data (heavier).
- `course.html` calls `loadManifest()` (the UQBS manifest) without a catch — both editions ship `manifest.json`, so don't drop it from either build.
- The current single repo (`uqsmitc6/uqbs-course-profiles`) is being **retired** in favour of the two fresh repos; ATLAS must be repointed before the old URL goes away.

**Front-door landing page (added same session, Sean's request):** a splash `index.html` with a short rationale and two big buttons — **Strictly Business** (UQBS + AoL/GA) and **All of UQ** (no AoL fields). The UQBS course browser moved from `index.html` to **`business.html`**; the all-UQ browser stays `browse-all.html`. `index.html` is now the landing on both editions. Button targets are config-driven (`site-config.js` `uqbsUrl`/`allUrl`, set by build args `--uqbs-url`/`--all-url`, absolute so the same splash works anywhere); the landing reads them via a small inline script. `renderNav()` now points "home" at `business.html`/`browse-all.html` and adds an "⌂ Editions" link back to the splash; it skips rendering on `data-page="landing"`. Landing styles appended to `styles.css` (`.landing`, `.edition-card*`, theme-variable based). Phase-1 defaults: All-of-UQ button → existing live `…/browse-all.html` (works against the current site today), Strictly-Business button → `…/uqbsld/profiles/business.html`. Re-verified: 11/11 Node-sandbox assertions + serve smoke test (uqbs ships index/business/course/program/aol; all ships index/browse-all/course, no business.html).

**Landing copy (after Sean's review):** positive framing, no swipe at Jac/Drupal — "more complete than the published Drupal pages, easier to navigate than Jac, with a couple of extra features to boot"; mentions search, the side-by-side offering compare, and bulk download. "Strictly Business" card flags AoL/GA as *coming soon* (not yet shipped). Card note is "For UQBS staff" (the LD team are UQBS staff — dropped the redundant pairing).

**Bulk multi-select download (#51, DONE):** added a checkbox column + a select-all (filtered) box to both browsers. A shared selection model (`STORE.selected` keyed by `course.file`) drives it: `coursesForExport()` returns the ticked set if any rows are selected, else the full filtered set; the existing CSV / ZIP-MD / ZIP-JSON exports now honour it. A "N selected · Clear selection" indicator sits by the export buttons. One implementation (`setupSelection`/`selCell`/`refreshSelectionUI` + `STORE.renderFn`) serves both `render()` and `renderAllBrowser()`. (Note for Sean: a "download multiple" capability already existed — the ZIP buttons export everything matching the current filters — this adds per-row picking on top.) Verified: `node --check`, CSS balanced (258/258), 7/7 selection-logic assertions, serve check (checkbox column present in both editions).

**Landing tweak:** removed the "For UQBS"/"For everyone" badge pills above the card titles (Sean — labels stand on their own). The note line under each card stays.

**Report-an-error (#52, DONE):** course-detail header now has a "Report an error ⚑" link that toggles a small panel (textarea + "Compose email"). On send it opens a `mailto:` to `reportEmail` (config-driven, default `uqsmitc6@uq.edu.au`) with the description plus a pinpoint block baked in — course code, full code, semester+code, class number, file path, page URL, edition. So a report lands in Sean's inbox with the exact location; paste it back and the fix (usually an LO-mapping override) is targeted. `reportEmail` added to `site-config.js` + build (`--report-email`). Verified: `node --check`, CSS balanced (262/262), 6/6 mailto-builder assertions, serve check.

**Aesthetic pass (Sean's review, both editions):**
- **Landing copy** cut to one line ("Every UQ course profile in one place. Search, compare across years, and download in bulk."), no em dash; card badge pills removed; card subs trimmed.
- **Removed the gold rule** under the purple header (`header.site` border-bottom none; active-tab underline switched from gold to white).
- **One display control instead of two.** The separate Classic/Fun theme toggle and Auto/Light/Dark colour-mode toggle are merged into a single `#mode-toggle` button that cycles **Auto → Light → Dark → Fun**. Storage unified to one key `uqbs-mode`; the FOUC `<head>` script + `app.js` (`getMode`/`applyMode`/`updateModeButton`/`initMode`) set `data-theme`/`data-color-mode` from it. Old `initTheme`/`applyTheme`/`initColorMode`/`applyColorMode` removed; exports updated to `initMode`/`applyMode`.
- **Fun is now dark-neon** (Sean's pick), replacing the old magazine/editorial look: near-black purple-tinted base (`#0e0c16`), neon-violet primary (`#c08cff`), cyan links (`#34e7e7`), glow on the header title / mode button / hovers. Self-contained and independent of light/dark (selecting Fun clears `data-color-mode`); the old fun+colour-mode override blocks were removed so they can't fight it.

Verified: `node --check`, CSS balanced (235/235), 10/10 mode-cycle assertions, serve check (single button, `uqbs-mode` key, no `theme-toggle`, both editions). All rebuilt into `build/uqbs/`.

**UQBS browser tweaks (#54, DONE):**
- New **"Core / Major" column** (UQBS browser only — the all-UQ view has no taxonomy). Shows where the course lives per program from `taxonomy.course_programs[code][].role`: "Core" (highlighted) or the major/list name (Finance, Business Economics, I&E, Program Electives, …), program name in the chip tooltip. Programs column unchanged; the two columns read in the same order. `render()` row + `business.html` thead + colspans (10→11) updated; verified 5/5 render assertions (11 cells, Core/role-major chips, program codes retained).
- **Default semester is now S1 2026** (code 7620) in both browsers, falling back to the most recent if 7620 isn't present (was: always most recent).

Verified: `node --check`, rebuilt into `build/uqbs/` (header + default confirmed via serve check).

**Major-name normalisation (#55, DONE):** the same UG major was abbreviated in one program and spelled out in another (Sean spotted I&E vs Innovation and Entrepreneurship on TIMS3310). Standardised five to full names in `taxonomy/uqbs-programs.json` — both the `programs[].majors` keys and the `course_programs[].role` values: I&E→Innovation and Entrepreneurship, BIS→Business Information Systems, HR→Human Resources, IB→International Business, BSAN→Business Analytics (6 major-key renames + 50 role renames, 0 abbreviations remaining, JSON valid). PG majors that are genuinely separate (MBus Human Resource Management, MBus/MCom Information Systems, MCom Professional Accounting / Applied Finance) and the BTHEM/MTHEM tourism/hotel variants were left as-is by design. Labels are display-only (no effect on search or the program filter). Rebuilt into `build/uqbs/`. Note: a course in the same major across two programs now shows that major twice in the Core/Major column (correct, tooltips name each program); dedupe is a trivial later tweak if wanted.

**Open items added:** #47 (DONE — edition-flag viewer + dual-build + landing), #48 (two fresh repos + deploy/mirror), #49 (repoint ATLAS), #50 (real AoL data source), #51 (DONE — bulk multi-select download), #52 (DONE — report-an-error), #53 (DONE — merged display toggle + dark-neon Fun + landing polish), #54 (DONE — Core/Major column + S1 2026 default), #55 (DONE — major-name normalisation).

**Still open / unblocked by this work:** #37 recurring LO patch routine; #42 program-rules time series; #24 cron switch.

---

### Session 16 — 2026-06-06 — Legacy data goes live in the viewer: the per-course timeline (#43 closed)

**Focus:** Wire the parsed legacy profiles (Session 15) into the viewer so fifteen years of history is browsable, and build the per-course timeline. Followed straight on from the #39 push earlier the same day.

**Decision (Sean's "begin real work" + my stated lean):** the timeline is keyed on **course code** but **surfaces title changes as visible events** — drift (a code repurposed or renamed) is signal an LD team wants, not noise to hide.

**What shipped (all local-only — push is #46):**
1. **`scraper/build_manifest.py`** — new `manifest-legacy.json`, built from a dedicated `profiles-legacy/{year}-{period}/` scan, grouped into `{year}-{S1|S2|SS}` buckets. Kept **entirely separate** from `manifest.json` (UQBS) and `manifest-all.json` (ATLAS) per the "keep 'em separated" principle — the live UQBS viewer is byte-for-byte unaffected (verified: still 873). Legacy summary entries carry `system/legacy_id/year/period` so the timeline can order and badge them. 5,288 legacy profiles across 46 periods.
2. **Pages plumbing** — `pages.yml` copies `profiles-legacy/` into `docs/` and adds it to the trigger globs; `serve_local.sh` symlinks it; `.gitignore` covers `docs/profiles-legacy`. Same pattern as the existing `profiles/`/`taxonomy/` staging.
3. **Viewer (`docs/assets/app.js`)** — `loadManifestLegacy()` + `getLegacyCourses()` (graceful fallback to empty); `offeringChronKey()` (cross-era chronological sort, summer ordered before its S1); `initCourseDetail()` now merges current + all-of-UQ-fallback + legacy offerings of the course; `buildCourseTimeline()` renders the ordered strip with the current offering marked, legacy era tags, and title-change events; a **legacy provenance badge** on the header (keyed on `system`/archive URL) so a pre-cutover ECP is never mistaken for current. The old `.semester-picker` block is superseded by the timeline.
4. **`docs/assets/styles.css`** — `.course-timeline`/`.tl-*`/`.era-badge` styles, all on existing theme variables so Classic/Fun + light/dark all inherit. Braces 225/225.

**Verification:** `node --check` OK; CSS balanced; manifest builder run (873 UQBS unchanged / 8,020 all / 5,288 legacy). Node-sandbox test against **real** app.js + real manifests on ACCT1101 (present in both eras: 42 legacy + 4 current offerings): `getLegacyCourses` flattens to 42; merged sort gives newest→oldest correctly (S1 2026 … S1 2009) with summer ordered before S1 within a year (2020.1 < 2020.2 < 2020.3); timeline spans "S1 2009 → S1 2026 · 47 offerings" with 42 era tags + current marker; synthetic title-change case fires the event. Local-serve smoke test: `manifest-legacy.json` 200, a legacy profile 200 and parses (3 assessment rows).

**Timeline v2 — the diff view (#45, same session):** a compare control under the timeline lets you pick any other offering and diff it against the one on screen. `computeOfferingDiff(profA, profB)` orients older→newer by chron key, matches assessment items by normalised title, and reports **added / dropped / changed** items (weight shifts and LO-set shifts on matched items) plus LO-count and title deltas; `renderOfferingDiff` paints it (green added / amber dropped / chip changed). Fetches the picked offering on demand via `loadCourseJson`. Node-verified on real ACCT1101: 2009→2024 = full assessment turnover (3 dropped, 3 added, LOs 15→5); 2024→2026 correctly matches "End-of-Semester Examination" across a case difference and flags its weight+LO change while showing the Inspera items as added; orientation robust when args are reversed; self-vs-self reads identical.

**Landmines / watch out for:**
- Local-only; **not pushed** (#46). On push, Pages redeploys and the timeline + diff go live; the UQBS viewer's existing pages are unchanged until a user opens a course that has legacy history.
- The all-of-UQ-fallback in `initCourseDetail` makes one extra fetch (`manifest-all.json`) only when a course isn't in the UQBS manifest — keeps the timeline complete for non-UQBS courses reached via the All-UQ browser, at no cost to UQBS course loads.
- The diff matches assessment items by **title** — a renamed-but-same item reads as drop+add rather than a change. Acceptable (and arguably honest); a fuzzy match could be a later refinement.

**The #46 push block (Sean's terminal — comment-free, run from the git repo):**

```
cd /Users/uqsmitc6_local/Documents/GitHub/uqbs-course-profiles
rsync -av "/Users/uqsmitc6_local/Claude Projects/Course Profile Repository/uqbs-course-profiles/scraper/build_manifest.py" scraper/build_manifest.py
rsync -av "/Users/uqsmitc6_local/Claude Projects/Course Profile Repository/uqbs-course-profiles/docs/assets/app.js" docs/assets/app.js
rsync -av "/Users/uqsmitc6_local/Claude Projects/Course Profile Repository/uqbs-course-profiles/docs/assets/styles.css" docs/assets/styles.css
rsync -av "/Users/uqsmitc6_local/Claude Projects/Course Profile Repository/uqbs-course-profiles/docs/serve_local.sh" docs/serve_local.sh
rsync -av "/Users/uqsmitc6_local/Claude Projects/Course Profile Repository/uqbs-course-profiles/.github/workflows/pages.yml" .github/workflows/pages.yml
rsync -av "/Users/uqsmitc6_local/Claude Projects/Course Profile Repository/uqbs-course-profiles/.gitignore" .gitignore
rsync -av "/Users/uqsmitc6_local/Claude Projects/Course Profile Repository/uqbs-course-profiles/PROJECT_LOG.md" PROJECT_LOG.md
python3 scraper/build_manifest.py
git add scraper/build_manifest.py docs/assets/app.js docs/assets/styles.css docs/serve_local.sh .github/workflows/pages.yml .gitignore PROJECT_LOG.md docs/assets/manifest.json docs/assets/manifest-all.json docs/assets/manifest-legacy.json
git commit -m "Legacy viewer integration: per-course timeline + offering diff (items 43, 45)"
git push
```

---

### Session 15 — 2026-06-06 — Legacy ECP parser: 15 years of profiles parsed (item #34 closed)

**Focus:** Build the legacy ECP parser against the completed offline cache (`data/legacy_html/`, 5,288 UQBS profiles 2009–S1 2024, 6 section files each) and batch-run it. Sean's standing orders: offline only, iterate carefully, verify against known courses before batch-running, accuracy over speed, nothing pushed without say-so.

**Decisions (Sean, via session questions):**
- Output layout: `profiles-legacy/{year}-{period_key}/` (period keys S1/S2/SS), NOT invented pre-7450 semester codes. Keeps the legacy era cleanly separate; viewer/manifest integration deferred (#43).
- Field scope: full parity with the 25-field schema where the legacy layout carries the data, plus additive legacy-only fields.

**Survey findings (whole-cache census before any code):**
- The legacy template is a **single uniform layout across all 5,288 profiles** and all 15 years. Section headings 1.1–6.2 are numbered and stable; the only variants: 2.3 Graduate Attributes absent in the 198 2024-era profiles ("Aims and Learning Objectives" era), 3.4's school name varies (Business/Economics/Law), 5.3/5.4 occasionally absent.
- All 5,288 assessment summary tables have the four-column layout incl. a dedicated **Learning Objectives** column; detail blocks carry **Learning Objectives Assessed** — confirming the Session 12 single-course finding at full scale.
- 1.1 Course Details is `<p><strong>Label:</strong> value</p>` rows; core labels 100% present.

**Built: `scraper/parse_legacy.py`** (offline, resumable via `--resume`, chunkable via `--time-budget`). Schema mapping notes:
- `class_code`/`semester_code` are null (legacy archive has no SI-NET class number); `legacy_id` carries the archive id; `full_course_code` = `{COURSE}-{legacy_id}-{year}{PK}`; `system: "legacy"`.
- `assessment_summary` rows carry a **native `learning_outcomes` list** (faithful refs, e.g. ["1","2"]) + `anchor_id` cross-linked to detail ids (`detail_matched`).
- `assessment_details.learning_outcomes_assessed` is the faithful page string ("1, 2, 4"), matching current-era convention; `category` = the page's "Type:" (verified identical to the summary `<em>` 254/254).
- `learning_outcomes[].number` is the faithful bare number ("1").
- Additive legacy-only fields: `graduate_attributes` (the 2.3 **GA-to-LO matrix** — feeds Phase 3A), `course_grading`, `late_submission`, `other_assessment_information`, `course_introduction`, `other_learning_activities_information`, `contact_hours_per_week`; `learning_activities` carry native LO refs (75,894 of 103,706 activities).
- Enrichment join on `legacy_id` from `data/offerings-index.json` gives `study_period` with date brackets.

**Verification (before batch):** independent regex-based extraction (separate code path) cross-checked against the parser on 205 profiles incl. known courses (ACCT1101 2009 + 2024, MGTS1601 2009, FINM1416 Summer-2020 + 2024) — 663 summary rows + 667 detail blocks, 0 mismatches; summary-vs-detail LO agreement 473/473; eyeball checks vs raw HTML on both era endpoints.

**Two parser bugs found by the batch QA sweep (both fixed, affected profiles re-parsed):**
1. **Multiple summary tables (70 profiles):** 5.1 can contain several summary tables (per assessment group / delivery stream); parser read only the first. NB the independent checker shared the same assumption — a correlated blind spot the count audit caught. Lesson: count-consistency audits catch what correlated extractors miss. Also: source pages can repeat identical tables verbatim (deduped) or carry genuinely distinct per-stream rows (kept — IBUS7302-28119 has 3 sit dates for one exam).
2. **Activities layout variant B (2,915 profiles):** 4.1 has two layouts — grid (Date + per-type columns) and list (Date | Activity | Learning Objectives, with native LO refs and the type in parentheses). Variant B tables use a **malformed `<body>` tag instead of `<tbody>`**, so row discovery must not rely on tbody structure.

**Batch result:** 5,288/5,288 parsed, 0 errors → `profiles-legacy/` (46 semester dirs, 2009-S1…2024-S1, 262 MB). Coverage: 100% on title/period/level/location/mode/units/coordinating unit/timetable/LOs/assessment summary+details/resources/activities/policies/grading; 99.9% description; 97.5% requirements; 96.3% graduate_attributes (the 2024 era dropped the section); 88% course_staff (source-genuine). LO mapping: **16,975/16,997 summary rows carry LO refs (99.87%)**; the 22 blanks verified source-blank; 0 unmatched anchors.

**Drupal-bug receipts:** across all 5,288 legacy profiles (2009–S1 2024), 99.87% of assessment rows carry LO mappings vs ~65–68% OK in the current system (Session 12 audit) — the cutover regression is now bracketed with full-scale evidence on both sides.

**Landmines / watch out for:**
- `profiles-legacy/` and the parser are **local-only, not pushed** — and at 262 MB the push strategy needs Sean's decision (#43).
- `scraper/_reparse_chunk.py` is a session helper (chunked overwrite re-parses); safe to delete.
- Sandbox quirks this session: background processes are killed between tool calls (hence `--time-budget` + `--resume` chunking), and file **deletes** in the mounted folder are blocked — overwrite instead.

---

### Session 14 — 2026-06-05 — Broken-era UQBS backlog plugged; class-scoped overrides; stale-matrix audit

**Focus:** Item #36 — restore LO mappings for the broken-era UQBS semesters (S2 2024 → Summer 2025-26) from Jac, via Claude in Chrome on Sean's logged-in session. Sean's standing orders this session: accuracy over speed, no multitasking, strictly read-only in Jac.

**Scope & result:** Coverage diagnostic found 108 flagged offerings (112 class instances; 79 MISSING_ALL / 31 MISSING_SOME / 2 UNREFERENCED) across 7460/7480/7520/7560/7580. All extracted from Jac's API (historical instances matched by SI-NET class number), all filled: **340 new override rows (335 shared + 5 class-scoped), 0 title mismatches, coverage now 108/108 carrying an override.** 12 assessments are unmapped in Jac itself and correctly stay blank. Not yet pushed (see #39 — this session's work rides the same push).

**Three findings that matter beyond this batch:**
1. **Stale-matrix trap (the big one):** an instance's matrix component can keep LO columns from an old draft; positional decode is then wrong. Defence: audit matrix heading texts against the published LO list for every instance; resolve mismatches from Jac's rendered grid. Backlog: 1 stale (PSYC3052 7520, corrected); 7620 batch re-audited: all 44 clean.
2. **Parallel deliveries genuinely diverge** (MGTS7812 intensive vs in-person; ENVM7524 in-person vs external) → built class-scoped overrides (`class_number` column, exact-class precedence) end-to-end: import, viewer, exports, 13/13 sandbox tests against real app.js + real overlay, render checks on real profiles.
3. **Title drift is real:** the 7620 re-scrape silently unhooked 2 Session-11 overrides (spacing changes); caught by --validate-only, fixed. Run --validate-only after every scrape.

Also: TOUR7051-60338-7460's published page drops the entire LO list (new fault facet, logged); RBUS7999 'Report' is the one published-vs-Jac contradiction (Jac verified by rendered grid; Jac wins).

**Process note (honesty):** an early extraction loop was launched with a too-narrow matrix detector, and my attempt to halt it failed (for…of holds its array reference), so two loops briefly raced — harmless to Jac (read-only) and fully recovered (every casualty re-run with the fixed extractor; final dataset verified complete), but the lesson is logged: use a generation guard on in-page loops, and don't relaunch until the old loop provably stopped.

---

### Session 13 — 2026-06-05 — Morning scoping, then crash & recovery handover

**Focus:** Short morning session answering two scoping questions, then the conversation hit repeated API 529 errors exactly as Sean asked for the tidy-up; this entry was written in the recovery session the same day (Sean supplied the full transcript).

**Scoping answers given (both logged as PLAN entries in the changelog and boarded as open items):**
- **Structure over time (#38):** the six faculty extractions capture *current* (S1 2026) program structure only. Jac retains every rule version with effective dates back to ~2021, so course movements (core↔major etc.) are recoverable for 2021+ by re-running the extraction without the current-version filter and diffing consecutive versions. Pre-2021 isn't in Jac; Sean confirmed pre-2021 is less relevant.
- **LO gap coverage (#36/#37):** what's plugged is **S1 2026 UQBS only** (43 courses / 135 mappings). Remaining: UQBS broken-era backlog ~106 course-semesters (7460/7480/7520/7560/7580); the S2 2026+ "running tap" (recurring per-semester routine needed while the Drupal bug lives); all-of-UQ ~3,000 course-semesters if scoped in later. Pre-S2-2024 needs no patching at all — legacy pages render mappings correctly, so historical truth comes from scraping, not patching.

**State at handover:** the overnight legacy fetch was (and still is) running in Sean's terminal — see Session 12 and HANDOVER.md.

---

### Session 12 — 2026-06-04 — The marathon: deploy, reframe, backfill, harvest, bug timeline, six faculties, overnight fetch

**Focus:** A very large day spanning deployment of the Session 10–11 work, a philosophical reframe, the historical backfill, the offerings harvest, dating the Drupal bug, extracting all six faculties' program structures from Jac, and launching an overnight legacy-HTML fetch. Detail lives in the 2026-06-04 changelog entries; this is the connective tissue.

1. **Deployed the LO override system** (commit 5839218) after a symlink gotcha (`docs/taxonomy` is a git-ignored symlink — stage `taxonomy/lo-overrides.json`, never `docs/taxonomy/...`). Verified live; ATLAS independently merged the published overlay.
2. **Jac-is-official reframe** (Sean's call, commit a4f2d37): Jac is the authoritative source the academic wrote; the published ECP is a lossy rendering. "✎ manually corrected" became a neutral **Jac provenance badge** everywhere; JSON downloads now serve the completed record with `learning_outcomes_assessed_source: "jac"`. ATLAS advised to flip its internal marker visible with source-framing ("sourced from the curriculum system"), not correction-framing.
3. **Backfill complete & pushed:** all current-system semesters S2 2024→S2 2026 (~8,020 all-of-UQ profiles). UQBS manifest 835→873.
4. **Bug timeline built; onset = the S2 2024 system cutover.** Legacy archive pages render LO mappings correctly; the new system was broken from its first semester (~⅓ of courses affected every semester since).
5. **Offerings harvest:** `discover_offerings.py` (parser rewritten against real markup mid-session) catalogued 3,290 courses → 51,294 offerings back to ~2009, 0 failures. UQBS-to-2020 = 2,614 legacy profiles; to-2009 = 5,234.
6. **All six faculties extracted from Jac (read-only):** BEL, HMBS, HASS, EAIT filed in `taxonomy/sources/`; **Science extracted but file-write pending** (stashed in browser `localStorage['sci_export_b64']`). UQBS calibration: zero contradictions vs the hand-audited taxonomy.
7. **`taxonomy/teaching-periods.json`** created — semester-code registry covering MBA/intensive/summer/medical oddities.
8. **Overnight fetch launched:** `fetch_legacy.py` caching raw legacy HTML for all 5,234 UQBS profiles back to 2009 (print endpoint unavailable → 7 section-requests/profile, ~16 h; resumable; oldest-first; cache git-ignored). Survived a network blip (2 failures, retryable). **Still running at session end.**

**Landmine:** everything from this session is local-only — nothing pushed since a4f2d37 (see #39).

---

### Session 11 — 2026-06-03 — Jac extraction: all 43 mappings recovered & filled

**Focus:** Fill the (blank) `lo-overrides.csv` with the real, authoritative LO-to-assessment mappings for all 43 affected courses, pulled from UQ's Jac curriculum system via Claude in Chrome.

**Key discovery — the mapping is in Jac and recoverable via API:** UQ's Jac (curriculum.uq.edu.au/cms/classes) holds the authoritative assessment↔LO mapping that the published ECP drops. The published HTML and even the page-rendered grid hide the mapped state in a visual matrix (cells carry a `span.active-cell` only when mapped — no accessible label). Rather than scrape 43 rendered pages, the whole thing was done via Jac's internal REST API:
- **Auth:** the Jac SPA stores a JWT in `localStorage['token']`; sent as `Authorization: Bearer`. (Used in-session only, never printed/exfiltrated.)
- **Search:** `POST /api/v1/classes/get-resources` `{courseCode, pageSize:100, …}` → `items[]` with `classId`, `curriculumVersionId`, `fromYYYYSS`, `stateName`. `fromYYYYSS` encodes year+period: **202601 = Semester 1 2026** (= our semester code 7620).
- **Mapping:** `GET /api/v1/curriculums/v2/{curriculumVersionId}/components` → 487-item form-builder array. The two mapping matrices sit in a component whose `changeTracking[last].value` parses to `{headings:[{title:"N. …"}], rows:[{subformInstanceTitle, cells:[{active}]}]}`. A cell is mapped iff `cell.active`; column i = LO(i+1). First matrix (lower index) = **Assessment**, second = **Activity** (confirmed by subform header text).
- Dead ends (both return `[]`): `/complex-mappings/curriculum-mappings/{id}` (program-level), `/entity-references/{id}/links`.
- **Reusable recipe saved:** `scraper/jac_extract.js` (browser console snippet) — re-runs assessment + activity extraction for any course list / semester. Use it next semester (change `TARGET`).

**Extraction run:** All 43 courses pulled via the API in chunked browser calls (≈7s/course; the components payload is heavy). 100% success, 0 errors. Every assessment came back with a non-empty LO list — confirming the bug is purely a publish/render fault and the data is intact upstream.

**Fill pipeline (`outputs/jac_assess_mapping.json` → `fill_from_jac.py` → CSV):**
- Joined Jac assessment titles onto the scaffolded CSV rows (which carry scraped ECP titles), keeping the scraped title so the viewer matches at runtime. Matching via alphanumeric-only normalisation (handles "Power Point" vs "PowerPoint") with a difflib fallback.
- Result: **135/135 rows filled across 43 courses, 0 warnings** on import (every title matches a scraped assessment, every LO in range, nothing clobbered).
- Provenance copy: `taxonomy/sources/lo-overrides-source-jac-7620.json`.

**Two edge cases resolved:**
- **MGTS7812 — dual offerings.** Runs two Sem-1-2026 classes (20136 & 22215) with *genuinely different* A1 assessments ("Organisation Case-Study" vs "Stakeholder Simulation"). Pulled both Jac instances and filled both offerings' titles. (General note: a course can have >1 instance per semester with different assessments; `jac_extract.js` takes the first Published — iterate `cands` if every offering is needed.)
- **ECON3430 — false-positive partial.** The coverage diagnostic flagged it `UNREFERENCED` (LO5/LO6 assessed by nothing). Jac confirms LO5/LO6 are *genuinely not assessed* by any item, and the scraped mapping already matches Jac exactly. So it's correct as published — **no override needed**. (Exactly the intended workflow: diagnostic flags candidates, human/Jac verification clears the false positives.)

**Verification:** import 0 warnings; coverage report shows 43/44 flagged courses now carry an override (ECON3430 correctly excluded); 6-course render spot-check (incl. dual-offering MGTS7812 and several partial-drops) all PASS — override chips + ✎ legend present and correct.

**Open items closed:** #28 (fill CSV) → DONE. #29 (review 9 suspected partials) → DONE: the 8 `MISSING_SOME` filled from Jac; ECON3430 verified correct.

**Activity-to-LO mapping:** captured in-session for all 43 (Sean asked to keep it "for later"). Not persisted to a file this session — the 57 KB exceeded the console export channel cleanly, and nothing consumes it yet. Re-pull on demand with `scraper/jac_extract.js` (returns `activity` alongside `assess`). **TODO #30** added.

**Follow-ups added after first report (same session):**
- **MBA robustness:** `jac_extract.js` rewritten to match by SI-NET class number (`{code:[classNumber]}`) as well as year+period. MBA courses run multiple offerings per semester with different assessments and don't map cleanly to a single period — class-number matching (the middle number in our `COURSE-CLASSNUM-SEM` filenames) ties a Jac instance to the exact scraped class. Instance metadata (class number, year, period, mode) lives in `item.metadataValues` keyed by `metadataClassConfigId` (6=class number, 7=year, 8=period). See item #32.
- **Activity mapping persisted:** `taxonomy/sources/activity-lo-mapping-jac-7620.json` (43 courses, 753 activity rows). Transferred out of the browser via gzip+base64 (the plain JSON was too big for the console channel and duplicated). Item #30 closed.
- **Shareable how-to doc:** `Recovering the dropped LO mappings - how it was done.md` (in the repo root folder) — plain-language explainer for a colleague.

**Landmine for next session:** the override CSV/JSON now contains real data but is **not yet committed/pushed** — Sean needs to `git add taxonomy/ docs/taxonomy/ scraper/jac_extract.js && commit && push` to deploy via GitHub Pages. Until then the live viewer is unchanged.

---

### Session 10 — 2026-06-03 — LO-to-assessment override overlay

**Focus:** Build the manual override system (open item #26) for the 30 UQBS courses where UQ's Drupal-published ECP drops the learning-outcome-to-assessment mapping. Mid-session, Sean's colleague flagged a twist: the bug can also drop *only some* of an assessment's LOs (partial render), not just the whole mapping.

**Why the twist matters (design pivot):** The original plan (item #26) was a gap-fill overlay — "scraped data wins, override only fills empty mappings." That assumes an assessment either has its full LO list or nothing. A *partial* render means scraped data is present but wrong, so a gap-fill override would never fire and the partial would silently stand. A partial also looks identical to a legitimate "this assessment only assesses some LOs" — nothing automatic can tell them apart with certainty.

**Decision — REPLACE per assessment (not gap-fill):** An override row is the authoritative full LO list for one course+assessment. If a row exists it wins entirely; otherwise scraped data stands. One rule handles all three cases: missing entirely, partially dropped, correct (no row). Confirmed with Sean (he was unsure; I made the call). Easy to switch to union later if data entry feels heavy.
- **Safety net for replace:** the bug only ever *drops* LOs, never invents them, so a half-typed override could clobber LOs Drupal *did* render. `import_lo_overrides.py` warns loudly when an override omits an LO the scraper captured ("override drops scraped LOx — intended?").

**New files:**
- `taxonomy/lo-overrides.csv` — source of truth. Columns: `semester_code` (optional; blank = all semesters, value = that semester only, exact wins over blank), `course_code`, `assessment_title`, `learning_outcomes` (tolerant: "LO1, LO2" / "1,2" / "L01,L02"), `notes`. Scaffolded with 135 blank rows across 43 course offerings (all MISSING_ALL + MISSING_SOME in 7620, UQBS-only). Assessment titles pulled from scraped `assessment_summary` so they match exactly.
- `scraper/import_lo_overrides.py` — CSV→JSON overlay (mirrors `import_aol.py`). Validates: course in taxonomy, assessment_title matches a scraped assessment (lists candidates on mismatch), LO refs within course LO range, duplicate rows, and the drop-scraped-LO safety warning. Writes flat-array overlay to `taxonomy/lo-overrides.json` + `docs/taxonomy/lo-overrides.json`. Modes: `--validate-only`, `--scaffold [--uqbs-only] [--semester]`. Blank LO rows are skipped (not errors) so a half-filled CSV imports cleanly.
- `scraper/lo_coverage_report.py` — diagnostic that scans profiles and flags `MISSING_ALL` (whole mapping dropped), `MISSING_SOME` (partial — some assessments have refs, some don't), `UNREFERENCED` (a course LO assessed by nothing — suspected partial), `OK`. Writes `logs/lo-coverage-report.csv`. Flags are *candidates* — a dropped LO is indistinguishable from a deliberately-unassessed one, so humans confirm.

**Diagnostic earned its keep immediately:** semester 7620 UQBS-only — 35 MISSING_ALL (matches the original audit), but **8 MISSING_SOME + 1 UNREFERENCED that the original 30-course audit completely missed** because they render *some* LO mapping and therefore looked fine. New cases (none in the original list): BISM7221, BISM7808, MGTS3301, MGTS4603, MGTS7308, MGTS7809, MGTS7812, RBUS4411 (partial), ECON3430 (LO5/LO6 unreferenced). This is exactly the failure mode the colleague warned about.

**Viewer changes (`docs/assets/app.js`):**
- `loadLoOverrides()` + `STORE.loOverrides` + `DATA_PATHS.loOverrides` (graceful fallback to empty on 404).
- `normTitle()` (mirrors Python `_norm_title`) and `getLoOverrideMap(courseCode, semesterCode)` → `{ normTitle → {los, notes} }` with exact-semester-wins-over-blank precedence.
- Applied with replace precedence (override → summary-row LOs → scraped details map) in: course-detail assessment summary table, assessment-detail "Linked LOs" line, Markdown export, printable-HTML export. Overridden mappings render with a distinct amber `.lo-chip.override` chip, a ✎ mark, and a legend ("manually corrected — UQ's published course profile omitted it"). Exports carry an inline "(manually corrected …)" note.
- `loadLoOverrides()` added to `initBrowser` and `initCourseDetail` load chains.

**Other files:**
- `docs/assets/styles.css` — `.lo-chip.override`, `.lo-override-mark`, `.lo-override-legend` + dark-mode variants (amber accent reads on both palettes). Brace balance 217/217.
- `.github/workflows/scrape.yml` — added "Rebuild LO overrides overlay" step after the AoL step (`taxonomy/` and `docs/taxonomy/` already in `git add`, so the generated JSON commits automatically).

**Verification:**
- `node --check docs/assets/app.js` → OK; `py_compile` both scripts → OK; CSS 217/217; both JSON overlays valid; workflow YAML parses.
- Import validation tested against a fixture CSV — every edge case caught: duplicate, bad title (+ candidate list), out-of-range LO, drop-scraped-LO clobber warning, unknown course.
- Resolver logic tested by loading the real `app.js` in a Node VM sandbox: 7/7 pass — full-missing replace, partial replace (adds dropped LO), blank-semester applies when no exact, exact-semester wins over blank, no-override → null, case/space-insensitive title match, parseLoRefs zero-typo.
- End-to-end render test (real BISM2207 profile + an override): override chips, ✎ mark, and legend all present, and only on the overridden assessment (override chip count = 2, exactly the override's LOs).
- Deliverable left clean: `lo-overrides.json` restored to 0 overrides (no test data committed); CSV holds 135 blank scaffold rows for the team.

**Landmines / watch out for:**
- The CSV ships **blank** — the feature is dormant (viewer shows no change) until the team fills LO lists from curriculum docs and reruns `import_lo_overrides.py`. That's correct behaviour, not a bug.
- `assessment_title` in the CSV must match the scraped title. The scaffold pre-fills them correctly; if a coordinator renames an assessment in a future semester, the import will warn (title not found) — re-scaffold or fix by hand.
- Replace semantics: entering only the *missing* LOs for a partial will drop the correct ones. The import warns, but the team should enter the **full** authoritative list per assessment.
- `--scaffold` only seeds courses where an assessment has *no* scraped LOs (MISSING_ALL/SOME). `UNREFERENCED` courses (e.g. ECON3430) won't be scaffolded — handle those by hand from the coverage report.

---

### Session 9 — 2026-06-02 — All-of-UQ scraper expansion

**Focus:** Expand the scraper from UQBS-only (323 courses) to all of UQ (~1,900 courses per semester) while keeping the live UQBS viewer completely unaffected. Driven by ATLAS, a separate TIG-funded project that uses this scraper's JSON as its data spine and needs profiles for non-UQBS courses.

**Design principle — keep 'em separated:**
- The UQBS viewer (`manifest.json`) is never affected by all-of-UQ data
- Default scraper behaviour (no flags) remains UQBS-only
- All-of-UQ is opt-in via `--all-uq` flag
- Two manifests: `manifest.json` (UQBS-filtered) and `manifest-all.json` (everything)
- ATLAS reads `manifest-all.json`; the UQBS viewer reads `manifest.json`

**Changes to `scraper/scrape.py`:**
- Added `--all-uq` flag: bypasses UQBS taxonomy, uses full JacSON repo index as course list
- Added `--delay` / `-d` flag: adjustable request spacing (default 1.0s, minimum 0.2s) for faster historical backfills
- `load_all_uq_course_list()`: new function that pulls all course codes from JacSON index, optionally filtered to a specific semester
- `main()` accepts `all_uq` and `delay` parameters
- Pre-fetches JacSON index before course list loading (needed for both discovery and all-of-UQ enumeration)

**Changes to `scraper/build_manifest.py`:**
- Now produces two manifests from a single scan of `profiles/`
- `manifest.json`: filtered to courses in `taxonomy/uqbs-programs.json` (831 UQBS profiles)
- `manifest-all.json`: all profiles (838 currently, will grow to ~1,900+ per semester after backfill)
- Falls back gracefully if taxonomy file is missing

**Changes to `.github/workflows/scrape.yml`:**
- Added `all_uq` boolean input for manual workflow dispatch
- Scheduled cron stays UQBS-only (safe default)
- Commits now include `manifest-all.json`

**Verification:**
- Both Python files pass syntax check
- Manifest builder tested: 831 UQBS / 838 all-of-UQ (7 non-taxonomy courses correctly excluded from UQBS manifest)
- JacSON repo confirmed active (13,621 commits, updated 5 hours ago) with ~1,908 files in semester 7620

**Historical backfill instructions (run on Mac):**
```bash
cd /Users/uqsmitc6_local/Documents/GitHub/uqbs-course-profiles

# Test with a small batch first
python scraper/scrape.py --all-uq --semester 7620 --max 10

# Then do each semester (oldest to newest), ~30 min each at default delay
python scraper/scrape.py --all-uq --semester 7450
git add profiles/ && git commit -m "Backfill: semester 7450 (all-of-UQ)"
git push

# Repeat for 7460, 7480, 7490, 7520, 7560, 7580, 7590, 7620, 7660
# Use --delay 0.5 to halve the time for historical (static) semesters
```

**ATLAS connection:** ATLAS is a TIG-funded platform helping academics redesign assessments for the AI era. It consumes this scraper's JSON as its data spine. The first ATLAS component is a course visualiser with Bloom's/SOLO analysis, assessment security classification, and constructive alignment checks. ATLAS gates UQBS-specific features (GA, AoL) by `coordinating_unit` field — the scraper just provides faithful data for all courses.

**Scale confirmed from JacSON repo:**
- Semester 7620: ~1,908 profile files (GitHub truncated listing at 1,000 + 908 omitted)
- 11 semester folders: 7450, 7460, 7480, 7490, 7520, 7560, 7580, 7590, 7620, 7660
- Course prefixes span all faculties: ABTS, ACCT, ADPS, AERO, AGRC, MINE, etc.
- Non-UQBS profiles use identical HTML structure (same course-profiles.uq.edu.au template)

**Backfill executed:** Semester 7620 backfilled locally on Sean's Mac — 1,750 courses, 1,906 profiles scraped (1 failure), pushed to repo.

**All-of-UQ browser page (`docs/browse-all.html`):**
- Separate page reading `manifest-all.json`, with School/Faculty filter instead of Programme/AoL columns
- Same search, sort, semester filter, level/mode/location filters, CSV/ZIP exports
- Nav links updated across all pages: "Courses" renamed to "UQBS", new "All UQ" link added
- `initAllBrowser()`, `renderAllBrowser()`, `applyAllFilters()`, `exportAllFilteredAsCsv()` added to app.js

**LO-to-assessment mapping audit:**
- Investigated BISM2207 — Drupal bug confirmed. The LO-to-assessment mapping data exists in curriculum documents but Drupal doesn't render it in the published ECP HTML. No hidden data in the DOM.
- Audited all 202 UQBS profiles in semester 7620: 167 have LO mapping (83%), 35 are missing it
- 30 of the 35 missing are Business School courses (see list below)
- Proposed solution: manual override CSV in `taxonomy/lo-overrides.csv`, same overlay pattern as AoL. Scraper never touches it. Viewer merges at runtime — scraped data takes precedence, override fills gaps.
- Courses missing LO-assessment mapping: ACCT3101, ACCT7106, BISM2207, BISM2208, BISM3208, BISM7807, EVNT7052, FINM7407, FINM7805, HOSP2005, HOSP7052, IBUS2301, IBUS2302, IBUS3306, IBUS7302, IBUS7306, IBUS7312, MGTS3601, MGTS3609, MGTS7309, MGTS7619, MGTS7803, MGTS7810, MGTS7820, MKTG7503, MKTG7510, TIMS7317, TOUR7020, TOUR7023, TOUR7032

---

### Session 8 — 2026-04-15 — Assurance of Learning (AoL) integration

**Focus:** Build the first internal data overlay layer — Assurance of Learning tracking — from data model through to viewer integration and a dedicated dashboard page.

**Requirements gathered:**
- AoL tracking is currently scattered/informal across the team — no single structured tracker
- Lifecycle is simpler than textbook AACSB: Identified → Rubric in Dev → Active → Established (+ Disrupted)
- Granularity: semester + course + GA + assessment item + rubric (SharePoint links)
- Start from Sem 1 2026 onwards — no historical backfill needed
- 2 GAs per course (per existing GA rubric integration skill rules)

**Architecture decisions:**
- **Overlay architecture** — AoL data lives in `taxonomy/aol-status.json`, separate from the programme taxonomy. Loaded by the viewer at runtime and merged client-side. This pattern will be reused for GA mapping, typologies, etc.
- **CSV as source of truth** — Team maintains `taxonomy/aol-template.csv` (7 columns: semester_code, course_code, ga, assessment_title, status, rubric_url, notes). Import script converts to JSON with validation.
- **5 lifecycle statuses** — `identified` (team flagged a match), `rubric_in_dev` (rubric being built), `active` (rubric built and in use), `established` (loop closed — data collected and reviewed), `disrupted` (assessment/mapping changed, needs remapping).

**New files created:**
- `taxonomy/aol-template.csv` — Template CSV with 11 sample entries across 7 courses for Sem 1 2026
- `taxonomy/aol-status.json` — Generated JSON overlay (also written to `docs/taxonomy/`)
- `scraper/import_aol.py` — Import script: reads CSV, validates against taxonomy (flags unknown courses, bad statuses, duplicates), writes JSON overlay to both `taxonomy/` and `docs/taxonomy/`. Supports `--validate-only` mode.
- `docs/aol.html` — Dedicated AoL dashboard page

**Files changed:**
- `docs/assets/app.js` — Major additions:
  - `loadAol()` data loader with graceful fallback
  - `getAolForCourse()` helper, `AOL_STATUS` config, `aolStatusChip()` and `aolGaChip()` display helpers
  - `initBrowser()` — loads AoL data; `render()` — adds AoL column to course browser table
  - `initCourseDetail()` / `renderCourseDetail()` — loads AoL; shows AoL status card (semester, GA, assessment, status, rubric link, notes)
  - `initProgram()` / `renderProgramDetail()` — loads AoL; adds AoL column to programme course tables
  - `initAol()` / `renderAolDashboard()` — new dashboard with summary stats, status cards, GA coverage heatmap per semester, full entry tables with course links
  - Updated `window.UQBS` exports
- `docs/assets/styles.css` — AoL chip styles (5 status colours), GA chips, dashboard stat cards, heatmap cells, dark mode overrides for all AoL colours
- `docs/index.html` — Added AoL nav link, AoL table header column, updated colspan
- `docs/course.html` — Added AoL nav link
- `docs/program.html` — Added AoL nav link
- `.github/workflows/scrape.yml` — Added "Rebuild AoL overlay" step after manifest; updated git add to include taxonomy/ and docs/taxonomy/

**Verification:**
- `node --check docs/assets/app.js` → OK
- CSS brace balance: 202/202 — OK
- JSON validation: aol-status.json, docs/taxonomy/aol-status.json, uqbs-programs.json — all valid
- AoL import validation: 11 entries, 0 errors, 0 warnings (all courses found in taxonomy)
- All 4 HTML files structurally valid

**Sample AoL data (11 entries for demonstration):**
- 7 courses: MGTS1601, MGTS2604, MGTS3601, ACCT1101, MKTG1501, ECON1011, FINM1416
- Status distribution: 3 identified, 3 rubric_in_dev, 3 active, 1 established, 1 disrupted
- GAs covered: GA1, GA2, GA3, GA4, GA5, GA6

**Workflow for the team going forward:**
1. Edit `taxonomy/aol-template.csv` (add/update rows)
2. Run `python scraper/import_aol.py` (or let GitHub Actions do it on next scrape)
3. Commit and push — GitHub Pages redeploys automatically
4. AoL dashboard and per-course/programme views update with new data

---

### Session 7 — 2026-04-15 — Taxonomy overhaul: 14→23 programmes

**Focus:** Full audit and rebuild of `taxonomy/uqbs-programs.json` based on structured data from 18 my.UQ programme pages. A deep research audit (using only UQ sources) revealed material errors across 10 of 14 existing programmes.

**Audit findings (errors in the original taxonomy):**
- **MBus:** 11→9 fields — "Leadership" renamed to "Law for Business", "Strategy and Entrepreneurship" renamed to "Entrepreneurship and Innovation", "International Management" dropped, "Sustainable Business" added
- **MEI:** 6→7 fields — all names changed (e.g. "Community Engagement" → "Civil Society and International Development", "Food Entrepreneurship" → "Food and Agribusiness Innovation")
- **MBusAn:** fake "Applied Analytics" and "Strategic Analytics" majors removed (no majors exist); core expanded 2→12
- **MBA:** fake "Strategy" and "Leadership" majors removed (no majors exist); restructured to flexible core A/B + program electives
- **Grad Dip:** fake "Applied Business" major removed; restructured to flexible core + program electives + research courses
- **BAB:** core fixed 16→14 (removed 2 erroneous codes), confirmed 8 majors
- **BAFE:** core fixed 19→18 (removed 1 erroneous code), added flexible core (18) and general pathway courses (2)
- **MFIM:** renamed from "Master of Financial and Investment Management" to "Master of Finance and Investment Management"
- **MTHEM:** renamed from "Master of Tourism, Hospitality and Event Management" to "Master of Tourism, Hotel and Event Management"; added pathway prerequisites
- **BAFE/BAB:** added "(Honours)" suffix to display names

**New programmes added (9):**
- BBusManHons — Bachelor of Business Management (Honours) (2129)
- BComHons — Bachelor of Commerce (Honours) (2131)
- GCBus — Graduate Certificate in Business (5248)
- GCBusAdmin — Graduate Certificate in Business Administration (5769)
- GCBusAn — Graduate Certificate in Business Analytics (5726)
- GCCom — Graduate Certificate in Commerce (5326)
- GCEI — Graduate Certificate in Entrepreneurship and Innovation (5689)
- GCFIM — Graduate Certificate in Finance and Investment Management (5764)
- GCTHEM — Graduate Certificate in Tourism, Hotel and Event Management (5547)

**New taxonomy fields introduced:**
- `program_code` — UQ numeric programme code (e.g. 5248)
- `is_programme` — `false` for the Elective cross-programme tag
- `foundational_courses` — prerequisite/bridging courses (GCBus, MBus)
- `capstone` — capstone course list (MBus, MEI)
- `pathway_to` — key of the master's programme this Grad Cert feeds into
- `pathway_prerequisites` — courses required before entering the pathway (MTHEM)
- `flexible_core`, `flexible_core_a`, `flexible_core_b` — flexible/elective core variants
- `program_electives` — programme-level elective pools
- `research_courses`, `advanced_courses`, `general_pathway_courses` — specialised course categories

**Taxonomy stats after rebuild:** 23 programmes (7 UG + 15 PG + 1 Elective tag), 323 unique courses, 521 course→programme mappings. Reverse mapping (`course_programs`) validated — 0 integrity errors.

**Viewer updates:**
- `renderProgramDetail()` now renders all new course-list fields (foundational, flexible core, capstone, pathway prerequisites, etc.) with descriptive section headings
- `renderProgramIndex()` filters out `is_programme: false` entries, shows `program_code` where available
- Programme filter dropdown on course browser excludes non-programme entries
- PG programmes show "Fields / Specialisations" heading instead of "Majors"
- Empty major course lists show a "see my.UQ for details" note instead of an empty table

**Known limitations:**
- 5 major/field course lists are empty: BAFE Economics, BAFE Finance (my.UQ references plan codes only, not individual courses), MEI Agri-Food Chains, MEI Business Management, MEI Data and AI
- 11 legacy programmes still lack `program_code` values
- MBus "Law for Business" field inherited old "Leadership" course list — may not be fully accurate
- GCEI "Food Entrepreneurship" field name differs from MEI's "Food and Agribusiness Innovation" — possible naming inconsistency in UQ systems

**Files changed:**
- `taxonomy/uqbs-programs.json` — Full rebuild (3898→4626 lines)
- `docs/assets/app.js` — Programme detail renderer extended for new fields; programme index and filter updated for `is_programme`

**Verification:**
- Forward/reverse mapping integrity: 323/323 courses, 0 errors
- `node --check docs/assets/app.js` → syntax valid
- All 23 programme core/major counts match my.UQ structured data

---

### Session 6 — 2026-04-14 — Viewer polish: bug fixes, themes, downloads, dark mode

**Focus:** Tidy up three bugs visible on the live viewer (LO code duplication, missing assessment→LO mapping, policy-text word-run-on), then add visual polish (Classic/Fun theme toggle, Auto/Light/Dark colour-mode toggle) and richer downloads.

**Bug fixes (live-site issues):**
1. **Learning-outcome codes rendered as `L0L01`** — data shape varied (`lo.number` could be `"LO1."`, `"L01"`, `1`, or `"1"`). Added `loDisplayCode(lo)` helper that trims a trailing period, upper-cases, and prepends `LO` only if not already present. Applied in the viewer, markdown export, and printable HTML.
2. **Assessment-summary "LOs" column empty** — data captured in `assessment_details.learning_outcomes_assessed` was never merged into the summary table. Added `parseLoRefs()` that tolerates `"LO1, LO2"`, `"L01, L02"` (common zero-typo in source), `"L.O. 1, L.O. 2"`, and bare-number `"1, 2, 3"` variants; and `buildAssessmentLoMap()` keyed by assessment title. Summary renderer now merges and hides the LOs column entirely when no assessment has any LOs.
3. **Policy-and-procedure text a "hot mess"** — `soup.get_text(strip=True)` in the original scraper concatenated sibling text nodes without separators, producing artefacts like `"Policyand Procedure"`, `"UQand the"`, `"Learn.UQormy SI-netto"`. Fixed both for historical data and future scrapes:
   - `scraper/clean_existing.py` gained a closed-vocabulary rule set (`_VOCAB_WORDS` = Policy, Procedure, Guide, Service, Report, Manual, Library, Integrity, Assessment, Examination, etc. + plurals; `_STOPWORDS` = and, or, the) plus targeted joins for `UQ`, `my.UQ`, `Learn.UQ`, and `SI-net`. URLs and emails are shielded with `\x00N\x00` placeholders to prevent damage. Applied in a 2-pass loop so `"Procedureand thePolicy"` fully expands in one clean run.
   - `scraper/scrape.py` mirrors the same rules via `_apply_stopword_joins()` inside `normalise_ws()`, so new scrapes won't reintroduce the artefacts.

**Viewer polish (new features):**
- **Classic/Fun theme toggle** — `data-theme="classic"` (default, understated UQ branding) and `data-theme="fun"` (magazine/editorial: gradient header with halftone dots, serif display font at 16px base, larger radii, zebra rows, faculty-prefix colour-coded course codes, pull-quote-styled assessment details, pill-shaped buttons). Toggle button in header nav; selection persisted in `localStorage["uqbs-theme"]`. Inline `<script>` in `<head>` applies the attribute before first paint to prevent FOUC.
- **Manual Auto/Light/Dark colour-mode toggle** — second header button, independent of theme. `data-color-mode="light"` / `"dark"` force a palette; "auto" (the default, attribute absent) falls back to `@media (prefers-color-scheme: dark)`. CSS duplicates the dark variable block across the media query (narrowed with `:not([data-color-mode="light"]):not([data-color-mode="dark"])`) and explicit manual selectors, so manual choice wins cleanly. Persisted in `localStorage["uqbs-color-mode"]`. Separate FOUC script in each HTML file.
- **Faculty-prefix colour coding** (Fun theme only) — 10 accent colours mapped by course-code prefix (`ACCT`, `FINM`, `MGTS`, `MKTG`, `TIMS`, `LAWS`, `BUSN`, `ECON`, `LEIS`, `TOUR`). Applied via `td.code.prefix-XXXX a` rules; helper `coursePrefix(code)` added to app.js.

**Downloads (richer exports):**
- Per-course download bar on `course.html`: JSON, Markdown, printable HTML (opens in new window, A4 print stylesheet hides header/nav/toggles).
- Bulk actions on `index.html`: CSV of filtered courses, ZIP of filtered Markdown, ZIP of filtered raw JSON. Uses JSZip 3.10.1 loaded via CDN; filename based on active filters.

**Files changed:**
- `docs/assets/app.js` — LO helpers (`loDisplayCode`, `parseLoRefs`, `buildAssessmentLoMap`), column-hide logic, theme + colour-mode modules, per-course and bulk download logic, `coursePrefix()` helper.
- `docs/assets/styles.css` — Full theming refactor to CSS variables, Classic vs Fun variants, manual + auto dark-mode blocks, mode-toggle button styles, print stylesheet updated to hide both toggles.
- `docs/index.html`, `docs/course.html`, `docs/program.html` — FOUC script extended to cover colour mode; second header button added; JSZip loaded on index only.
- `scraper/clean_existing.py` — `_VOCAB_WORDS`, `_STOPWORDS`, `_SPECIFIC_JOINS` (8 rules), 2-pass application inside `_insert_boundaries()`.
- `scraper/scrape.py` — Mirrored stopword rules via `_apply_stopword_joins()`; integrated into `normalise_ws()`.

**Verification:**
- `node --check docs/assets/app.js` → OK
- CSS brace balance: 161/161
- localStorage round-trip (Node simulation): `applyColorMode('dark' → 'light' → 'auto' → 'bogus')` behaves correctly (attribute removed for `auto`, `bogus` normalised to `auto`)
- All 838 historical profiles re-processed through `clean_existing.py` — 0 remaining stopword artefacts

**User-reported outcome after deploy:**
- LO codes display correctly (`LO1`, not `L0L01`)
- Assessment summary shows LOs as chips per assessment
- Policies and procedures text reads cleanly
- Classic/Fun toggle confirmed working
- Dark-mode button added (this session) alongside theme toggle

---

### Session 5 — 2026-04-14 — Phase 2: viewer + automation

**Focus:** Build a static-site visualiser that reads the scraped JSON directly, hosted on GitHub Pages, auto-redeployed when the scraper commits new data.

**Design decisions:**
- **Vanilla HTML/JS, no build step** — opens locally, no framework drift, anyone on the LD team can clone + tweak
- **Pull from repo on load** (not rebuild-per-change) — site fetches `manifest.json` + individual course JSONs at runtime; GitHub Pages just serves static files
- **Same repo as scraper** — `docs/` folder inside `uqbs-course-profiles`; one source of truth
- **Deploy via Actions workflow** (not "deploy from folder") — lets us stage `profiles/` and `taxonomy/` into the pages artefact without duplicating files in the repo

**New files:**
- `scraper/build_manifest.py` — Generates `docs/assets/manifest.json`, a lean index of every profile with summary fields (~200-byte entries vs ~10KB full JSONs). Browser loads this once for the table view, fetches full JSONs on demand.
- `docs/index.html` — Course browser: searchable/filterable table (search, program, level, mode, location), sortable columns, program chips per course
- `docs/course.html` — Per-course detail view, one card per JSON section (description, aims, LOs, assessment summary + details, contacts, staff, activities, resources, policies, timetable, requirements)
- `docs/program.html` — Program index + program detail pages with core + majors from taxonomy
- `docs/assets/styles.css` — UQ purple + gold palette, responsive
- `docs/assets/app.js` — Shared fetch/render logic, page-specific init functions
- `docs/serve_local.sh` — Local dev: regenerates manifest, symlinks profiles/taxonomy into docs/, serves on :8000
- `.github/workflows/pages.yml` — Pages deploy workflow (triggered on push to profiles/, taxonomy/, docs/, or build_manifest.py; plus manual dispatch)

**Changes to existing files:**
- `.github/workflows/scrape.yml` — Added manifest regen step before commit; now commits both `profiles/` and `docs/assets/manifest.json` so the pages workflow fires with fresh data
- `.gitignore` — Ignore `docs/profiles` and `docs/taxonomy` (created as symlinks by serve_local.sh)
- `README.md` — Updated Scheduling section (GitHub Actions now primary, not experimental); added Viewer section

**Local verification:**
- `build_manifest.py`: 202 profiles indexed from single semester (7620)
- `python3 -m http.server` in docs/: all endpoints return 200 (index, manifest, taxonomy, individual course JSON)
- Cross-lookup verified: manifest + taxonomy combined correctly gives ACCT1101 → BBusMan Core, BTHEM Core
- JS syntax validated with `node -c`

**Outstanding — user action required:**
- Enable GitHub Pages in repo settings: Settings → Pages → Build and deployment → Source: "GitHub Actions"
- First pages deploy will run automatically on next push

**Phase 3 candidates (deferred):**
- Interactive dashboard (Streamlit/Observable) with cross-course analytics
- GA coverage heatmap (pending finalised GA mappings in the taxonomy spreadsheet)
- Assessment landscape view (weight × timing × type by program)
- Compare-two-courses side-by-side view
- Diff reports when profiles change week-to-week

---

### Session 4 — 2026-04-14 — Full semester validation

**Focus:** Run a full-semester scrape to validate all accumulated fixes hold at scale.

**Run 9 (full Semester 1 2026, 308 courses):**
- Duration: ~4 minutes (11:12:04 → 11:17:03 UTC)
- 308 courses processed, 198 found in JacSON index, 202 profiles scraped (some courses have multiple class offerings)
- 0 failures
- 110 warnings — all "No profiles found in JacSON repo" (courses not offered in Sem 1 2026; expected, not bugs)

**Quality sweep across all 202 profiles:**

| Field | Coverage | Notes |
|-------|----------|-------|
| `course_description` | 202 / 202 (100%) | |
| `learning_outcomes` | 202 / 202 (100%) | LO count range 3–7; no heading-prefix bugs; no LO-code leakage across boundaries |
| `assessment_summary` | 202 / 202 (100%) | Clean titles; indicators captured as `conditions` |
| `assessment_details` | 202 / 202 (100%) | |
| `timetable` | 202 / 202 (100%) | |
| `learning_activities` | 202 / 202 (100%) | |
| `learning_resources` | 202 / 202 (100%) | |
| `policies_and_procedures` | 202 / 202 (100%) | |
| `course_aims` | 201 / 202 (99.5%) | 1 legitimately empty (ADVT7512) |
| `course_staff` | 194 / 202 (96.0%) | 8 courses with no separate staff section |
| `requirements` | 192 / 202 (95.0%) | 10 courses with no stated pre/corequisites |
| `course_contacts` | 186 / 202 (92.1%) | Some courses use only `course-staff` |

**Bug sweeps — all clean at scale:**
- LO heading-prefix contamination: 0 / 202
- LO-code leakage across boundaries: 0 / 202
- Staff duplicates (same name + role): 0 / 202
- Assessment summary title contamination: 0 / 202 (earlier false-positive flags were legitimate titles like "Online Quiz", "AI Assisted Case Study")
- Empty LO descriptions: 0 / 202
- Critical field missing (desc + LOs + assessment): 0 / 202

**Verdict:** Production-ready. All Session 1–3 fixes hold at scale. Remaining coverage gaps (aims 99.5%, staff 96%, contacts 92%) reflect genuinely absent sections on source pages rather than scraper bugs — spot-checked and confirmed.

**Changes to codebase:**
- `PROJECT_LOG.md`: Updated with Run 9 results and Session 4 validation notes.

---

### Session 3 — 2026-04-13 (evening, continued)

**Focus:** Broader testing and iterative data quality fixes across multiple courses.

**Run 6 (5 ACCT courses, semester 7620):**
- 3 of 5 courses had profiles (ACCT1101, ACCT1102, ACCT1110). ACCT1111 and ACCT1112 not offered in Sem 1 2026.
- LOs correct across all three. Assessment detail scoping working.
- Found: summary title concatenation, staff role/dedup issues, aims missing on ACCT1101.

**Run 7 (MGTS1301, BSAN1201, MGTS7610, MGTS2603, MGTS7619, semester 7620):**
- 4 of 5 courses had profiles. BSAN1201 not in JacSON repo.
- MGTS1301, MGTS2603, MGTS7610: all fields correct including aims, contacts, staff with roles, clean assessment titles with conditions.
- MGTS7619 issues: staff role assignment wrong (interleaved role groups inside single wrapper), assessment detail LOs genuinely absent from page.
- Cross-checked all findings via browser JavaScript on live pages.

**Fixes applied:**
1. **Assessment summary titles had indicators jammed in** — e.g. `"Final ExaminationIdentity VerifiedIn-person"`. Root cause: the title `<td>` contains an `<a>` tag (title) followed by a `<ul class="icon-list">` (indicators like "Identity Verified", "In-person", "Team or group-based"). Using `get_text()` on the whole cell concatenated everything. Fix: extract just the `<a>` text for the title; capture indicators separately as a `conditions` list.
2. **Staff extraction missing roles and duplicating entries** — The staff section uses `<h3 class="staff-cards__role">` as a group heading above the cards (unlike contacts where role is inside each card). Fix: iterate `.staff-cards` groups, get role from heading, then iterate cards within. Added dedup by name+email.
3. **Due dates concatenated** — Multiple `<p>` tags in the due date cell were joined without separators. Fix: use `get_text(separator="; ")`.

4. **Aims extraction missed bare text nodes** — ACCT1101's aims text is a bare text node directly inside the `<section>`, not wrapped in a `<p>` tag (server HTML: `<p></p>Text here.`). The original code explicitly skipped `NavigableString` children. Fix: now captures bare text nodes (with `len > 10` filter). Verified via browser JS on the live ACCT1101 page.
5. **Staff role groups interleaved inside single wrapper** — MGTS7619's staff section has one `.staff-cards` div containing multiple `<h3>` role headings ("Lecturer", "Course facilitator") with their `.staff-cards__cards` divs interleaved. Previous code used `select(".staff-cards")` which found the single wrapper, then grabbed only the first `<h3>`. Fix: now walks `h3.staff-cards__role` headings directly and finds the next `.staff-cards__cards` sibling for each. Dedup changed from `(name, email)` to `(name, role)` to allow same person under different roles.

**Investigations (no fix needed):**
- ACCT1102 missing contacts: browser-verified — page has no `course-contact` section at all, only staff cards. Data is correct as-is.
- MGTS7619 missing assessment detail LOs: browser-verified — the page's `<dl>` for each assessment item simply has no "Learning outcomes" DT. Genuinely absent from the course profile.
- Assessment detail LOs show `L01` instead of `LO1`: this is how UQ formats them in the assessment section. Left as-is to faithfully reflect source data.

**Cross-check against Geoff's code:**
- Geoff's `extract_special_indicators` (line 71-82) captures icon-list indicators with CSS class and text — our summary fix captures the same info from the summary table cells.
- Geoff's `extract_assessment_details` uses `find_next('dt', string='...')` which searches forward globally (not scoped to each item). Our sibling-walking approach is more robust.
- Geoff doesn't extract aims, policies, or staff — these are UQBS-enriched fields unique to our scraper.

**Changes to codebase:**
- `scraper/scrape.py`: Fixed assessment summary titles, staff interleaved role groups, due date separator, aims bare text nodes.
- `PROJECT_LOG.md`: Updated with Runs 6-7 results and Session 3 notes.

---

### Session 2 — 2026-04-13 (evening)

**Focus:** Fix LO off-by-one bug identified in Session 1 testing.

**Root cause analysis:**
- The raw server HTML (what `requests.get()` receives) has a different structure to the browser-rendered DOM (what "Save page as" captures)
- Server HTML (Layout A): `<p><strong>LO1.</strong> Description text here.</p>` — LO number and description in the SAME `<p>` tag
- Browser DOM (Layout B): `<p><strong>LO1.</strong> </p><p>Description text here.</p><p></p>` — separate `<p>` tags
- The original code walked to the next sibling `<p>` first, which in Layout A grabbed the NEXT LO's paragraph (off by one)
- The "fallback" same-`<p>` extraction (which was correct) only ran if the sibling walk found nothing — but it always found the wrong thing

**Fix applied:**
- Reversed priority: check same-`<p>` first (strip LO number prefix), fall back to sibling walk
- Added safety-net regex strip of any leading `LO\d+\.?` from descriptions
- Verified against Geoff's JacSON extraction approach (lines 88-94 of `jacson.py`) — Geoff uses the same same-`<p>` strategy

**Verification:**
- Tested against Layout A (server HTML), Layout B (browser DOM), and actual browser-saved MGTS1601 page — all correct
- GitHub Actions Run 5: LOs now match Geoff's JacSON output exactly
- Assessment details still correct (fix from Session 1 Run 4 holding)

**Changes to codebase:**
- `scraper/scrape.py`: Rewrote `_extract_learning_outcomes()` — reversed same-`<p>` / sibling priority, added safety-net regex
- `PROJECT_LOG.md`: Updated with Runs 1-5 results

---

### Session 1 — 2026-04-13 (afternoon)

**Focus:** Design and build a UQBS-specific enriched course profile scraper. Test via GitHub Actions.

**Outcomes:**
- Explored Geoff's JacSON-Pi v1.0.5 codebase to understand existing scraping architecture
- Inspected live UQ course profile page (MGTS1601) via browser to identify all available data fields
- Identified 15+ fields available on the page that Geoff's scraper doesn't capture
- Built complete Python scraper with enriched field extraction
- Created GitHub Actions workflow — confirmed working (course-profiles.uq.edu.au IS accessible from GH Actions)
- Created local Mac runner script with launchd plist
- Fixed multiple extraction bugs across 5 GitHub Actions test runs (see below)

**GitHub Actions test runs:**
1. **Run 1** — FAIL — exit code 128. Missing `permissions: contents: write` in workflow YAML.
2. **Run 2** — FAIL — 405 from `programs-courses.uq.edu.au`. Replaced discovery mechanism with GitHub Tree API (fetches JacSON repo file listing).
3. **Run 3** — SUCCESS — MGTS1601 scraped and committed. But JSON review revealed: assessment details not scoped (all items got same data), LO descriptions off by one.
4. **Run 4** — SUCCESS — Assessment detail scoping fixed (sibling-walking approach with `el.__copy__()` into temp `Tag`). LO off-by-one still present.
5. **Run 5** — SUCCESS — LO off-by-one fixed (see Session 2). All fields now correct.

**Decisions made:**
- Separate repo from Geoff's JacSON (Sean doesn't have access to Geoff's infrastructure)
- GitHub Actions as primary runner (course-profiles.uq.edu.au accessible; Geoff's IP concern was about programs-courses.uq.edu.au)
- GitHub Tree API for URL discovery (programs-courses.uq.edu.au returns 405 from GH Actions)
- Use taxonomy JSON as course list source (308 courses already mapped to programs)

**Issues encountered:**
- Cowork sandbox blocks outbound requests to UQ domains (proxy 403) — cannot test from Cowork
- `programs-courses.uq.edu.au` returns 405 from GitHub Actions — replaced with GitHub Tree API
- Assessment section has 3 tables (1 summary + 2 in details) — fixed to skip nested tables
- Assessment detail `<h3>` tags share one parent `<section>` — fixed with sibling-walking scoping
- LO off-by-one due to server HTML vs browser DOM structure difference — fixed in Session 2

**Changes to codebase:**
- `scraper/scrape.py`: Main scraper — all extraction functions, multiple bug fixes
- `scraper/requirements.txt`: beautifulsoup4, requests
- `.github/workflows/scrape.yml`: GitHub Actions workflow (weekly + manual dispatch)
- `run_scrape.sh`: Local runner script with git push option
- `com.uqbs.course-scraper.plist`: macOS launchd schedule config
- `taxonomy/uqbs-programs.json`: Copied from existing project
- `README.md`: Setup and usage documentation
- `PROJECT_LOG.md`: This file

**Landmines / Watch out for:**
- UQ course profile page structure may vary between courses — parser handles two known LO layouts but untested broadly
- Some courses may not have current-semester profiles available (only archived)
- Rate limiting is set to 1 second between requests — 308 courses × ~2 requests each ≈ 10-15 minutes for a full scrape

---

## Decision Log

| Date | Decision | Rationale | Alternatives Considered | Status |
|------|----------|-----------|------------------------|--------|
| 2026-04-13 | Separate GitHub repo | Sean doesn't have access to Geoff's Pi or repo write access; keeps UQBS data cleanly separated | Fork JacSON, supplementary layer on top | Active |
| 2026-04-13 | GitHub Actions as primary runner | Confirmed working — course-profiles.uq.edu.au accessible from GH Actions runners | Local Mac only, own Raspberry Pi | Active |
| 2026-04-13 | GitHub Tree API for URL discovery | programs-courses.uq.edu.au returns 405 from GH Actions; Tree API gives full file listing from Geoff's JacSON repo in one call | Scrape programs-courses.uq.edu.au, hardcoded URL list | Active |
| 2026-04-13 | Taxonomy JSON as course list | Already maintained, has program mappings, 308 courses ready to go | CSV file, Google Sheets integration | Active |
| 2026-04-13 | Same-`<p>` first for LO extraction | Server HTML puts LO number + description in same `<p>` tag; matches Geoff's approach in jacson.py | Sibling walk first (caused off-by-one), regex on full text | Active |

---

## Known Issues & Gotchas

- **`programs-courses.uq.edu.au` blocks cloud IPs** — Returns 405 from GitHub Actions runners and Cowork sandbox. Geoff reported this as a general UQ IP block, but it only applies to this domain. `course-profiles.uq.edu.au` is fully accessible from GitHub Actions.
- **Server HTML vs browser DOM differ** — The raw HTML served by `course-profiles.uq.edu.au` (what `requests.get()` receives) has a different structure to the browser-rendered DOM (after JavaScript execution). Known differences: LO number + description in the same `<p>` (server) vs separate `<p>` tags (browser); aims text as bare text nodes (server) vs wrapped in `<p>` (browser, sometimes). The scraper handles all known layout variants.
- **Page content varies between courses** — Some courses lack certain sections entirely (e.g. ACCT1102 has no `course-contact` section, only `course-staff`; some courses have no aims text). The scraper handles missing sections gracefully — fields are simply omitted from the JSON.
- **Hidden sections** — Several sections on course profile pages have `class="hidden"` (aims-and-outcomes, assessment, learning-resources, learning-activities, policies-and-guidelines). The HTML content is still in the DOM and parseable by BeautifulSoup — the `hidden` class is CSS-only.

---

## Dependencies & Environment

| Dependency | Version | Purpose | Notes |
|-----------|---------|---------|-------|
| Python | 3.10+ | Runtime | macOS ships with Python 3 via Xcode CLT |
| beautifulsoup4 | >=4.12 | HTML parsing | Core scraping engine |
| requests | >=2.31 | HTTP client | With 1s delay rate limiting |

---

## File Map

```
uqbs-course-profiles/
├── .github/workflows/
│   └── scrape.yml                ← GitHub Actions workflow (weekly Sun 9pm AEST + manual)
├── scraper/
│   ├── scrape.py                 ← Main scraper (all extraction logic + normalise_ws stopword joins)
│   ├── build_manifest.py         ← Generates docs/assets/manifest.json (lean index)
│   ├── clean_existing.py         ← One-time cleanup pass over profiles/ (boundary + stopword rules)
│   ├── import_aol.py             ← AoL CSV→JSON overlay importer
│   ├── import_lo_overrides.py    ← LO-override CSV→JSON overlay importer (--scaffold, --validate-only)
│   ├── lo_coverage_report.py     ← Diagnostic: flags missing/partial LO mappings → logs/lo-coverage-report.csv
│   ├── jac_extract.js            ← Browser-console recipe: pull assessment/activity↔LO matrices from Jac API
│   ├── discover_offerings.py     ← Harvests programs-courses offering links (both eras, to ~2009) → data/offerings-index.json (run from Sean's Mac only)
│   ├── fetch_legacy.py           ← Overnight fetcher: caches raw legacy-ECP HTML per profile (resumable; cache git-ignored)
│   ├── parse_legacy.py           ← Legacy ECP parser: data/legacy_html/ → profiles-legacy/ JSONs (offline; --resume, --time-budget)
│   ├── _reparse_chunk.py         ← Session helper: chunked overwrite re-parses from a stems list (deletable)
│   └── requirements.txt          ← Python dependencies
├── data/
│   ├── offerings-index.json      ← Harvest output: every offering of every current UQ course, 2009→now
│   └── legacy_html/              ← Raw legacy-ECP HTML cache, 5,288 profiles × 6 sections (git-ignored)
├── profiles-legacy/              ← Parsed legacy profiles (2009–S1 2024), {year}-{S1|S2|SS}/{COURSE}-{legacy_id}.json — local-only (#43)
├── docs/                         ← GitHub Pages static viewer
│   ├── index.html                ← Course browser (search, filter, sort, bulk downloads)
│   ├── course.html               ← Per-course detail (JSON / MD / printable HTML downloads)
│   ├── program.html              ← Program index + per-program core/majors
│   ├── assets/
│   │   ├── app.js                ← Fetch + render + theme + colour-mode + downloads + per-course timeline
│   │   ├── styles.css            ← Classic/Fun themes, auto + manual dark mode, print stylesheet, timeline
│   │   ├── manifest.json         ← Generated — lean index of UQBS profiles (live viewer)
│   │   ├── manifest-all.json     ← Generated — all-of-UQ index (ATLAS)
│   │   └── manifest-legacy.json  ← Generated — legacy index 2009–S1 2024, keyed by {year}-{period}
│   └── serve_local.sh            ← Local dev: regenerate manifest + symlinks + :8000
├── profiles/                     ← Scraped JSON output (per semester)
│   └── {semester_code}/
│       └── {COURSE-CLASS-SEM}.json
├── taxonomy/
│   ├── uqbs-programs.json        ← UQBS program/course taxonomy
│   ├── aol-template.csv          ← AoL source CSV (team-maintained)
│   ├── aol-status.json           ← Generated AoL overlay
│   ├── lo-overrides.csv          ← LO-override source CSV (135 rows, filled from Jac, Sem 1 2026)
│   ├── lo-overrides.json         ← Generated LO-override overlay (also in docs/taxonomy/)
│   ├── teaching-periods.json     ← Semester-code registry incl. MBA/summer/medical special periods
│   └── sources/                  ← Provenance + faculty program structures from Jac
│       ├── lo-overrides-source-jac-7620.json
│       ├── activity-lo-mapping-jac-7620.json
│       ├── bel-programs-jac-202601.json
│       ├── hmbs-programs-jac-202601.json
│       ├── hass-programs-jac-202601.json
│       ├── eait-programs-jac-202601.json
│       ├── sci-programs-jac-202601.json
│       └── lo-overrides-source-jac-backlog-2024-2025.json
├── logs/                         ← Scrape run logs
├── run_scrape.sh                 ← Local runner script
├── com.uqbs.course-scraper.plist ← macOS launchd config
├── README.md                     ← Setup and usage docs
├── PROJECT_LOG.md                ← This file
└── .gitignore
```

---

## Changelog

- **2026-09-16**: FEATURE. **The AoL feed updates itself.** A daily Power Automate flow runs the Office Script `automation/aol-register-feed.ts` against the SharePoint register and sends course, GA, assessment, status, First implemented and rubric file as a `repository_dispatch` event (standard Excel Online and GitHub connectors; no premium licence, no Azure app, no Microsoft credentials in GitHub). New `.github/workflows/aol-register.yml` runs `export_aol_register.py --payload`, commits only when `aol-template.csv` changes (retrying on a push race with the scrape), dispatches pages.yml, and raises an issue on failure. Exporter gains `--payload`, `--emit-payload`, `--evidence` / `--write-evidence` (sweep terms saved in `data/aol-semester-evidence.csv`, 76 rubric files, so the automatic run gives the same semesters), `--default-semester auto`, a shrink guard (`--min-keep 0.8`, `--allow-shrink`) and a validate-before-replace step. Verified: workbook and payload modes both reproduce the committed 203-row CSV byte for byte; the Office Script, type-checked and run against the register's values and formulas, returns the same payload as `--emit-payload`; the workflow's commit loop tested for no change, change, and a rejected push. Setup and troubleshooting in `automation/README.md`. Hardened after a hostile review the same day: openpyxl only needed for `--workbook`; register columns found by heading in both the script and the exporter; the Office Script uses arrow callbacks only (an Office Scripts rule tsc does not check) and caps the payload at 58 KB measured in its larger string form; payload mode refuses a missing evidence file and a FileBase off uq.sharepoint.com; rubric paths with dot segments are dropped; the shrink guard also counts rubric links (a paste-values over the Rubric column); dry runs validate too; `--write-evidence` merges instead of replacing; the workflow wraps register text in stop-commands and retries the Pages dispatch. `scrape.yml` no longer rebuilds `aol-status.json` (it only changed the timestamp and could collide with the feed commit) and rebases and retries a refused push. ATLAS stays on uploads: it reads LD names, coordinators, notes, placements and coverage sections that the public feed leaves out.
- **2026-09-15** — CHANGE — **One viewer, one data host.** The viewer had drifted into three copies (docs/ here, build/uqbs/, and courses/uqbsld/profiles/ which is what teach.business serves). The courses copy is now the only viewer and reads every JSON, aol-status.json included, from this repo's Pages site; docs/ here keeps only the data and a redirect index.html; build_editions.py and DEPLOY-UQBS-edition.md retired. Same day: AoL register wired in (export_aol_register.py, import_aol.py with the register's nine statuses, 203 rows), taxonomy gains TIMS7334, MGTS7527, MKTG7505, MGTS2301.
- **2026-09-14** — CHANGE — **Repo prepared for transfer to the UQ-Business-School org.** Every reference to the personal account and Pages URL repointed to `UQ-Business-School/uqbs-course-profiles` and `uq-business-school.github.io/uqbs-course-profiles` (site-config, app.js export footers, build_editions defaults, build_manifest docstring, DEPLOY doc). Contact and report-an-error address changed to learningdesign@business.uq.edu.au (site-config, build_editions, scraper user-agents). README gains an explicit "not an official UQ source" notice and every viewer page footer says unofficial, not endorsed by UQ, source of truth is course-profiles.uq.edu.au. Confirmed the scraper holds no Jac credentials: the only secret is GitHub's own automatic `GITHUB_TOKEN`, used to read the public JacSON index. Consumers repointed in the same pass: teach.business viewer (`courses/uqbsld/profiles`), Paku Paku `platform/lib/course-profiles.js`, ATLAS `app/js/data.js`, AoL register `build_final.py`. GitHub Pages does NOT redirect after a transfer, so the cutover order is: transfer, enable Pages (source: GitHub Actions), dispatch pages.yml, confirm the new URL serves `assets/manifest.json`, then push and deploy the consumers. The planned `uqbs-course-profiles-all` split (#47 to #49) is superseded: the Saturday all-of-UQ scrape lives in this repo, so `build_editions.py` now defaults `--all-data-base` to this repo's Pages URL.

- **2026-06-06** — MILESTONE — **Legacy data integrated into the viewer (#43 closed): the per-course timeline.** Separate `manifest-legacy.json` (5,288 profiles, kept apart from UQBS/all manifests — live viewer unaffected, still 873); Pages + serve_local plumbing; `initCourseDetail` merges current+legacy offerings; `buildCourseTimeline` renders a chronological strip (cross-era sort, summer-before-S1, current marked, legacy era tags, title-change events); legacy provenance badge on the header. Verified in a Node sandbox against real app.js + manifests (ACCT1101, 42 legacy + 4 current → 47-offering timeline 2009→2026) and a local-serve smoke test (200s, parses). Local-only — push is #46.
- **2026-06-06** — DOC — **Documentation completed for the session (protocol session-end).** `HANDOVER.md` rewritten for the post-Session-16 state (legacy arc complete + live; queue reset to genuinely-new work: #37 recurring patch, #14 GA mapping, #40-tail deleted-courses harvest, #42 program time series, #24 cron). `README.md` refreshed (#8 closed): legacy parser, `profiles-legacy/` output, third manifest, timeline + diff features, deploy staging. `PROJECT_LOG.md` Current State + Open Items reconciled. Nothing local-only or unpushed remains as of this entry (note: README/HANDOVER edits here ride the next routine push).
- **2026-06-06** — FEATURE — **Timeline diff view (#45 closed).** Compare control under the timeline diffs any two offerings: `computeOfferingDiff` (older→newer, title-matched assessment add/drop/change incl. weight + LO-set shifts, LO-count + title deltas) → `renderOfferingDiff`. Fetches the picked offering via `loadCourseJson`. Node-verified on real ACCT1101 across 2009/2024/2026 (full turnover 2009→2024; matched-item weight+LO change 2024→2026; orientation-robust; self-vs-self identical). Local-only — push is #46.
- **2026-06-06** — DECISION (Sean) — Timeline keyed on course code but **surfaces title changes as visible events** (a repurposed/renamed code is signal for the LD team, not noise). Drives `buildCourseTimeline`'s title-change comparison against the next-older offering.
- **2026-06-06** — MILESTONE — **Sessions 12–15 backlog PUSHED (#39 closed).** Two commits, range 02b1f575..31b58be9: (1) code/taxonomy/data — six faculty structures, teaching-periods registry, offerings index, deleted-offerings subset, discover_offerings.py, fetch_legacy.py, parse_legacy.py, program codes, project log; (2) `profiles-legacy/` — all 5,288 parsed legacy profiles (31b58be9). Pack compressed to 40.7 MiB (better than the ~70 MB estimate). Raw HTML cache stayed git-ignored as intended. Remaining for the legacy arc: viewer/manifest integration (#43).
- **2026-06-06** — DECISION+RESOLUTION — **profiles-legacy minified for push (Sean's call: minify, lose nothing).** All 5,288 JSONs re-written compact with per-file round-trip verification (parsed-object equality) + 5-file fresh-reparse spot-check, all exact. Disk 262→252 MB (indent=1 was already lean — content is the weight, not whitespace); git pack will compress to roughly 70 MB (measured ~3.5:1 gzip on sample dirs). Downstream visualiser test in a Node sandbox against the real `docs/assets/app.js`: minified legacy profiles parse and run clean through `loDisplayCode` (bare "1"→LO1), `buildAssessmentLoMap` (legacy LO strings → correct chips), `semesterLabel` (falls back to study_period, "S1 2009"), `getLoOverrideMap` (null semester/class codes — no crash, no spurious overrides), and `completeCourseJson`. `parse_legacy.py` now writes compact by default. `scraper/_minify_chunk.py` is a deletable session helper.
- **2026-06-06** — MILESTONE — **Legacy ECP parser shipped & batch-run (#34 closed).** `scraper/parse_legacy.py` parses the 6-section legacy cache into `profiles-legacy/{year}-{period}/` JSONs (full schema parity + additive legacy fields incl. GA-to-LO matrices). 5,288/5,288 parsed, 0 errors; 470-profile independent cross-check 0 mismatches; LO-to-assessment mappings native and verified (16,975 rows; 22 source-blank). Local-only — push strategy is #43.
- **2026-06-06** — DECISION (Sean) — Legacy output keyed by `{year}-{period}` (S1/S2/SS) in a separate `profiles-legacy/` tree — no invented pre-7450 semester codes; viewer/manifest integration deferred (#43). Full field parity in one pass rather than core-fields-first.
- **2026-06-06** — RESOLUTION — Two legacy-parser bugs caught by the post-batch QA sweep and fixed, with re-parses: (1) multiple 5.1 summary tables per page (70 profiles; per-stream/dual-table pattern; exact duplicates deduped, distinct per-stream rows kept); (2) 4.1 activities "list" layout variant with a malformed `<body>`-for-`<tbody>` tag (2,915 profiles; variant carries native activity-to-LO refs). Lesson: the independent verifier shared assumption (1) — correlated extractors can agree and both be wrong; structural-consistency audits (summary-vs-detail counts) are the catch.
- **2026-06-06** — FINDING — **Drupal-bug date-bracket receipts at full scale:** legacy era (2009–S1 2024, 5,288 profiles) renders LO-to-assessment mappings on 99.87% of assessment rows (the rest are source-blank); current system runs ~65–68% OK (Session 12). The regression shipped with the S2 2024 cutover — now evidenced on both sides of the boundary.
- **2026-06-06** — FINDING — Legacy bonus data layers now on disk: GA-to-LO matrices (96.3% of profiles — feeds Phase 3A), per-activity LO mappings (75,894 activities), course grading cutoffs, contact hours. All faithful to the published pages.
- **2026-06-05** — MILESTONE — **Overnight legacy fetch COMPLETE; cache in both folders. 5,288 profiles, 0 failures.** All UQBS legacy profiles back to 2009 cached as raw HTML in `data/legacy_html/` — including a 54-profile bonus: the cleanup pass ran after the index merge, so deleted-course legacy offerings (in-taxonomy ones) were fetched too. Cleanup verified everything on disk and healed the 2 overnight network-blip failures. Counter quirk noted: in sections mode `skipped` stays 0 by design (per-section skips are silent; verified-complete profiles count as saved). Cache is git-ignored. **Next session's headline: the legacy parser (#34)** — parse the cache into profile JSONs, including correct pre-cutover LO mappings, and date-bracket the bug with receipts.
- **2026-06-05** — FINDING+ISSUE+RESOLUTION — **Deleted-courses residue check done; index-clobber incident recovered.** Findings: of the 59 since-deleted UQBS courses, **48 still have live programs-courses pages with archives — 596 offerings, 2009–2024, all legacy-system** (so their history is scrapeable AND their LO mappings render correctly); only **11 are page-gone** (ADVT3510, BISM2201/2204/2205/3204/3209/3210/4201/4204, IBUS7330/7331) — for those we hold Jac class numbers, so direct archive-URL construction is the remaining play; true unrecoverable residue may be zero. Subset saved as `data/deleted-offerings-index.json`. INCIDENT: the `--codes-file` run **overwrote** the full offerings index (script only merged under `--resume`); recovered cleanly because the full index had just been committed (02b1f575) — `git checkout` + merge → 3,349 courses, verified. FIX: `discover_offerings.py` now ALWAYS merges into an existing index; targeted runs can no longer clobber. Lesson for terminal blocks: zsh chokes on `#` comments in interactive paste — keep Sean's blocks comment-free.
- **2026-06-05** — CHANGE — **Teaching-period registry wired into the viewer (#41) + 9 program codes added to the taxonomy (#13).** `semesterLabel()` now resolves semester codes from `taxonomy/teaching-periods.json` (loaded at all 5 page inits, graceful fallback to the old hardcoded map) — fixes 7480's label ('Sum 2025'→'Sum 24/25') and adds the 7490/7590 medical-period labels. 7/7 sandbox tests. `uqbs-programs.json`: program_code added for the 9 programs that lacked one (source: Jac program-rules), with `program_code_source` provenance field; reverse map intact (323 entries). Local-only — rides the #39 push.
- **2026-06-05** — MILESTONE — **Deleted-courses Jac org-pull done (#40, UQBS).** Pulled all 3,450 Business School class instances (org 29) via `get-resources {organisationId:29}` paged — read-only, one pass, ~25s. Item fields: course code = `owningCourseCrseCode`, total = `totalNumber`. Diffed 355 distinct Jac course codes against the offerings harvest: 289 still listed on programs-courses; **59 discontinued** (mostly a 2021–22 restructure cluster: ADVT, REDE, EVNT, TOUR families; BLSI pair ran to 2024), **5 newborn** S2-2026 codes not yet published (ADVT7513, IBUS7314, MGTS7527, TIMS7334, MGTS7822 — not deleted!), 2 indeterminate (IBUS7327, TIMS7333 — no fromYYYYSS). Deliverables: `taxonomy/sources/uqbs-deleted-courses-jac.json` (classified) + `logs/deleted-codes.txt` (the 59, for `discover_offerings.py --codes-file`). Remaining: Sean runs the codes-file harvest on his Mac to see which still have live archive pages. Export recipe upgrade: **per-chunk checksums now standard** (page logs SUMS line; workspace verifies before decompress).
- **2026-06-05** — FINDING — **Program-rules time series (#38) probed: version records exist as hoped, but the pre-~2024 rule schema doesn't embed course codes.** GCBus (5248) confirms the version model: Published windows 202101–202307, 202401–202507, 202601–open (plus a duplicate concurrent record for the first window — dedupe by (from,to), keep latest id). BUT the 2021-era record's components contain ZERO course codes: rule tree sections are present (`topRule.subRules`, type `SelectionList`) yet hold only UUIDs — the selection-list contents live behind a separate endpoint the UI resolves at render time. The 2026-era records embed `selectionListItems` inline (which is why the Session-12 extraction worked). **Recipe for next session:** open a historical program-rules record in the Jac UI, capture the network call that populates a SelectionList (likely keyed by uuid or ruleLogicGuid), then batch as usual. Side win: BEL file supplies the program codes the taxonomy lacked (BBusMan=2171, BCom=2336, BTHEM=2473, MCom=5584, MBus=5583, MBA=5770, MEI=5690, MBusAn=5188, MTHEM=5585) — feeds item #13.
- **2026-06-05** — RESOLUTION — **Science faculty file landed (closes #35).** Retrieved the Session-12 stash from browser `localStorage['sci_export_b64']` (9,008-char gzip-b64): 62 programs, 1,244 courses (compact reverse map), empty_programs ['5013','5036','5566'] (known cross-ref pattern) → `taxonomy/sources/sci-programs-jac-202601.json`. Transfer lesson reinforced: first reassembly failed gzip (one transcribed character wrong); per-chunk hash comparison (page-side vs workspace-side) located the bad chunk instantly — add per-chunk checksums to the standard transfer recipe. All six UQ faculties' program-structure files are now on disk; none pushed yet (#39). The localStorage stash can be cleared whenever — no longer needed.
- **2026-06-05** — MILESTONE — **Sessions 14 work deployed** (commit 48f8b604, pushed by Sean): overlay live with 472 overrides / class_scoped_entries 5, verified on the published Pages URL; Sean visually confirmed MGTS7812's two Sem 1 2025 deliveries show different mappings.
- **2026-06-05** — MILESTONE — **Broken-era UQBS LO backlog plugged (item #36, UQBS portion): 340 mappings across 5 semesters (7460/7480/7520/7560/7580), 108 flagged offerings, 112 class instances — all extracted from Jac, verified, filled, 13/13 resolver tests pass.** Coverage now reports 108/108 flagged offerings carrying an override. Method: coverage diagnostic → worklist with SI-NET class numbers → in-page API batch through Sean's logged-in session (read-only throughout) → gzip/console export → class-aware fill → import. Independent DOM cross-checks (Jac's own rendered grids) on 5 instances, all exact. 12 assessments are empty in Jac itself (admin items like thesis supervisor agreements) — correctly left blank. NOT yet pushed.
- **2026-06-05** — FEATURE — **Class-scoped overrides (`class_number` column).** Sean's call: parallel deliveries are both valid and must both be kept (MBA intensive vs standard will recur). Schema: blank = all classes (old behaviour); value = that SI-NET class only; class-scoped rows must carry a semester. Precedence in `getLoOverrideMap(course, semester, class)`: exact-class > exact-semester > blank. Implemented in import (validation incl. class-exists and title-in-class checks; per-class scraped index), viewer resolver + all 5 call sites (profiles carry `class_code`), overlay metadata (semantics string + class_scoped_entries count — **consumers without class-matching, e.g. ATLAS, should apply class_number entries only where they can match the class; steer to pass on**). 5 class-scoped rows live: MGTS7812 7520 'A1: Stakeholder Simulation' (intensive 22459 vs in-person 22500), ENVM7524 7560 'Quiz 1' (in-person vs external), ENVM7524 7460 'Practical Assessments' (external only — in-person is unmapped in Jac, stays blank).
- **2026-06-05** — WARNING+RESOLUTION — **Stale-matrix trap in Jac extraction discovered & neutralised.** A class instance's mapping-matrix component can retain LO columns from an OLD draft of the course's LO list (headings carry old text/count; Jac's own view page reconciles against the course's current LO table and renders fewer columns). Positional decode of the raw matrix is then WRONG. Found via PSYC3052-21227-7520 (matrix 8 old-text headings vs 5 published/current LOs; validator caught out-of-range LO6–8). **Defence now standard: headings audit** — compare matrix heading texts/count against the published profile's LO list (AU/US spelling neutralised) for every extracted instance; mismatches get resolved from Jac's RENDERED grid (DOM read), which is authoritative. Audit results: backlog 112 instances → only PSYC3052 stale (corrected from rendered grid); MGTS7309 false alarm (US/AU spelling); **all 44 Session-11 (7620) instances audited clean — the live data is sound**. Heading snapshots: `logs/jac-backlog-headings.json`, `logs/jac-7620-headings.json`.
- **2026-06-05** — FINDING — **Two further publishing-fault facets.** (1) TOUR7051-60338-7460: the published profile drops the ENTIRE LO list (learning_outcomes: None), not just the mapping — mapping restored from Jac; restoring the LO list itself from Jac headings is a possible future layer. (2) Title drift confirmed in the wild: the Session-12 re-scrape of 7620 changed two assessment titles ('Ri PPLE'→'RiPPLE', 'Power Point'→'PowerPoint'), silently unhooking those two Session-11 overrides; --validate-only caught both; CSV titles updated. Worth re-running --validate-only after every scrape.
- **2026-06-05** — NOTE — RBUS7999-80193-7480 'Report': published page asserts LO3,LO4 but Jac (API + rendered grid, both verified) says LO2,LO4,LO5,LO6 — the one case where the published page asserts an LO Jac doesn't. Jac wins per the Jac-is-official framing; the import's clobber warning documents it (the 1 expected warning on import).
- **2026-06-05** — NOTE — **Conversation crash & recovery.** The Session 12/13 chat hit repeated API 529 errors exactly when Sean requested the end-of-conversation tidy-up; this log update and the refreshed `HANDOVER.md` were written in a recovery session from Sean's saved transcript. The overnight legacy fetch was still running at recovery time (Sean estimates a few hours to go).
- **2026-06-05** — PLAN — **LO gap scope confirmed (items #36/#37).** Plugged so far: S1 2026 UQBS only (43 courses, 135 mappings, live). Remaining: UQBS broken-era backlog ≈106 course-semesters (7460/7480/7520/7560/7580) via the Session 11 Jac recipe with class-number matching; the S2 2026+ running tap (recurring per-semester routine, ~20 min each, while UQ's Drupal bug lives); all-of-UQ ≈3,000 course-semesters as a later scope decision. Pre-S2-2024 needs no patching — legacy pages render mappings correctly, so the historical record comes from scraping the archive, not Jac.
- **2026-06-05** — PLAN — **Program structure over time (item #38).** Current faculty extractions = currently-effective versions only. Jac stores every program-rule version with explicit fromYYYYSS/toYYYYSS back to ~2021 (e.g. GCBus has versions effective 2021/2024/2026), so a time series = same extraction without the current-version filter + diff of consecutive versions → course movements (core↔major) with effective dates, university-wide. Pre-2021 structure pre-dates Jac and isn't recoverable this way; Sean confirmed pre-2021 is low priority.
- **2026-06-04** — DELIVERABLE — **`scraper/fetch_legacy.py` built; overnight fetch launched (still running).** Caches raw legacy-ECP HTML to a git-ignored local cache for later parsing. Scope chosen: UQBS back to 2009 = 5,234 profiles. Print endpoint (`student_section_loader/print/{id}`) tested unavailable at runtime → fell back to 7 section-requests/profile (~16 h ETA, falling). Resumable (re-run skips on-disk, retries failures); oldest-first so the most at-risk history banks first; survived a mid-run network outage (2 failures of 3,075 at that point). Run with `caffeinate -i` to keep the Mac awake. Follow-up when done: cleanup re-run + rsync `data/` to the Cowork folder (#33), then build the legacy parser against the local cache (#34).
- **2026-06-04** — MILESTONE — **Offerings harvest complete & analysed: the historical menu exists.** 3,290 courses, 51,294 offerings, 0 failures, back to 2009 (`data/offerings-index.json`, rsynced). Year-by-year: legacy era runs 2009–S1 2024 (~41k profiles); Sean's target **UQBS back to 2020 = 2,614 legacy profiles** (all-UQ same span = 20,576). 2024 splits at the cutover exactly as predicted (S1 legacy 1,865 / S2 current 2,105). Legacy print endpoint found (`student_section_loader/print/{id}`, POST with print_section_1..7) — would make scraping 1 fetch/profile (UQBS-to-2020 ≈ 45 min); programmatic verification pending (fetch hangs — may need real form semantics; worst case 6 fetches/profile ≈ 4.5h UQBS). Next builds: legacy parser + scrape-from-index plumbing (tasks #10 done, #12 pending).
- **2026-06-04** — MILESTONE — **Science extracted (final faculty): all six UQ faculties now mapped.** SCI org 65: 62 programs, 265 lists (largest belt), 1,261 courses, 0 errors; 3 cross-ref Grad Certs (5013/5036/5566). File transfer pending (export stashed in browser localStorage key 'sci_export_b64', 8.8KB gzip-b64, survives reloads — land it with small split writes next session). Faculty files in taxonomy/sources/: bel, hmbs, hass, eait (+sci pending). None of the program-structure files are pushed yet.
- **2026-06-04** — MILESTONE — **EAIT extracted & filed** (org 36): 50 programs, 110 lists, 806 unique courses, 0 errors → `taxonomy/sources/eait-programs-jac-202601.json` (compact form, transferred clean first try with the new recipe). 10 PG cert/dip programs use cross-references without embedded courses (codes listed in file's empty_programs) — same known pattern as GCBusAn/GCTHEM. **Science in flight** (org 65): 1,925 records, 415 current — the largest satellite belt yet (265 majors/minors/fields, the BSc machine); 62 programs decoded, lists resolving in background. Sequential per Sean (no multitasking). Science completes all six UQ faculties.
- **2026-06-04** — MILESTONE — **HMBS + HASS program structures extracted from Jac (read-only), concurrently with the Mac harvest.** HMBS (org 141): 63 programs, 49 lists, 779 courses, 0 errors → `taxonomy/sources/hmbs-programs-jac-202601.json` (full role-level). HASS (org 52, biggest faculty): 45 programs, 211 lists, 1,043 courses, 0 errors → `taxonomy/sources/hass-programs-jac-202601.json`. Three faculties now mapped (UQBS/BEL, HMBS, HASS). Confirms concurrency: Jac-via-browser and programs-courses-via-Mac-terminal are fully independent. Org IDs: BEL 28 (Business 29), HMBS 141, HASS 52.
- **2026-06-04** — NOTE — **Browser→workspace transfer limit found & worked around.** Large gzip+base64 payloads (>~10KB) truncate when written in one tool call. Reliable recipe: keep the deliverable small (compact form: course→[program codes] + program_names index ≈7KB for a big faculty), gzip, log in 600-char console chunks, read, write once, verify by gunzip+json.load (gzip integrity catches any transcription error). HASS persisted this way; its full role-level data remains re-extractable on demand. Use compact form for remaining faculties.
- **2026-06-04** — DELIVERABLE — `taxonomy/teaching-periods.json` created (task #9): semester-code registry (7450–7660) with labels, types, Jac fromYYYYSS equivalents, system (current/legacy), confidence flags. Documents MBA/intensive (extra class instances, match by SI-NET class number) and summer/medical special periods. Wiring into app.js semesterLabel()/import scripts still pending.
- **2026-06-04** — FINDING — **Drupal LO-mapping bug onset dated: the S2 2024 system cutover.** Legacy ECP page (archive.course-profiles.uq.edu.au, ABTS1000 S1 2024, id 132418, section_5) renders LO mappings correctly in BOTH the assessment summary table (dedicated 'Learning Objectives' column) and per-item detail ('Learning Objectives Assessed:'). Combined with the audit (bug fully mature in the new system's first semester, ~1/3 of courses affected from day one), conclusion: the fault shipped with the new publishing system. Implications: (a) legacy-era restoration (≤S1 2024) needs NO Jac — the published legacy pages carry correct mappings; Jac patching only needed for S2 2024+. (b) Legacy pages are cleanly parseable (numbered sections, labelled fields) — legacy parser for scraping 2020–S1 2024 is tractable. Caveat: single-course evidence; confirm on a handful more legacy pages once the harvest index lands.
- **2026-06-04** — MILESTONE+FINDING — **Backfill done; bug timeline built; UQ's profile-system cutover discovered.** (1) Backfill landed S2 2024→S2 2026: 7460=1944, 7480=161, 7520=1941, 7560=1895, 7580=158, 7620=1906, 7660=15 (S2 2026 mostly unpublished yet). UQBS manifest 835→873. (2) LO-coverage audit: UQBS fully-missing grows 14→26→30→35 (S2 24→S1 26), OK% 90→78. All-of-UQ: ~470–520 affected courses EVERY semester (65–68% OK). Bug already mature at S2 2024 — onset earlier. (3) **System cutover explains 7450=0:** current course-profiles.uq.edu.au only serves S2 2024 onwards; everything older lives on `archive.course-profiles.uq.edu.au/student_section_loader/section_N/{id}` (legacy ECP, opaque ids, different HTML — needs its own parser to scrape). (4) `discover_offerings.py` parser rewritten on real page markup (tr#course-offering rows, classed cells): captures BOTH eras, archived flag, year/period from row label. Validated on real ABTS1000 page: 24 offerings, 22 legacy, **back to 2009**. (5) 7490/7590 saved nothing because scraper's course-code regex rejects 'S'-suffix codes (IMED1242S) — minor fix, parked. Remaining for full harvest: Sean re-runs MGTS7610 test then full ~1hr run.
- **2026-06-04** — MILESTONE — **BEL program structures extracted from Jac (read-only) and calibrated.** Enumerated all BEL records via organisationId=28 (+children: BUSINESS 29, ECONOMICS, LAWSCHOOL): 1,126 records, 226 current Published. Extracted 40 unique single programs (deduped multi-version codes by latest fromYYYYSS; 49 duals excluded by design) + 66 referenced major/field/minor lists (depth-2 recursion, cached), 642 unique courses mapped, 0 errors. Calibration vs hand-audited UQBS taxonomy: **8 exact matches incl. all majors (BAB 8/8, BAFE 2/2, BBusMan 7/7); zero contradictions**; Jac fills taxonomy gaps (GCBusAdmin/GCEI cores). Known gaps: GCBusAn (5726) & GCTHEM (5547) use cross-references without embedded course objects (not auto-decoded); wildcard rules not captured. Deliverable: `taxonomy/sources/bel-programs-jac-202601.json` (programs + lists + course_programs reverse map, ATLAS-style). Engineering notes: program records can have multiple concurrently-'current' Published versions — dedupe by latest fromYYYYSS; course-list container keys vary (selectionListItems/curriculumList/curriculums) — match on `.curriculum.code` leaf. Not yet committed/pushed.
- **2026-06-04** — VALIDATED — **Program-structure extraction from Jac works; UQBS calibration exact (3/3).** Decode recipe: (1) `POST program-rules/get-resources` {searchParam: code} → pick record where stateName=Published & fromYYYYSS≤target≤toYYYYSS. (2) `GET curriculums/v2/{id}/components` (fast, ~1–1.5s even for big programs — earlier 'timeouts' were a wedged tab, NOT size; use a fresh tab + AbortController guard). (3) Find the rule item via changeTracking[last].value.topRule. (4) Walk the tree: nearest ancestor `title` = section name (e.g. 'BBusMan Core Courses'/'Majors'/'Program Elective Courses'); course codes = any array whose objects have `.curriculum.code` (container key varies: selectionListItems / curriculumList / curriculums — match on the leaf, not the container). (5) Recursion: major/field/specialisation members appear as list-record refs (codes like MARKEC2171, X5583) carrying `curriculum.currentlyReferencedCurriculumVersionId` — fetch that cvid's components and repeat to get the major's own course list. Calibration vs hand-audited taxonomy: GCBus foundational+core EXACT; BBusMan core (8) EXACT, majors (7) EXACT incl. name mapping (MARKEC2171→Marketing etc.); Marketing major course list (8) EXACT. Jac is also MORE complete than the taxonomy where the taxonomy left elective pools blank. Read-only throughout. Next: batch all 23 UQBS programs → diff vs taxonomy as full calibration → then BEL-wide.
- **2026-06-04** — NOTE — Program Rules probe addendum: full-record `curriculums/v2/{id}/components` for PROGRAM records is very heavy (>60s for BBusMan id 143601; destabilised the tab — abandoned politely). Extraction (task #14) must use the lighter per-component endpoint observed in UI traffic (`/api/v1/components/curriculums/{cvid}/components/{itemId}`) to fetch just the rule component. topRule tree shape still to be decoded (course codes confirmed present; grouping structure unknown). All access read-only throughout.
- **2026-06-04** — FINDING — **Jac Program Rules API probed (read-only): all-of-UQ program structure is extractable.** `POST /api/v1/program-rules/get-resources` works with Sean's token: 8,914 records — UG/PG Programs, Dual Programs, Majors, Fields of Study, Specialisations — with code, name, state (Published/Draft/Withdrawn) and effective dates (fromYYYYSS/toYYYYSS). Plan codes embed the parent program code (SUSAGC2461 → program 2461). Detail via the same read-only `curriculums/v2/{id}/components` viewer: BBusMan (program 2171, id 143601) component 7 holds a structured `topRule` tree containing its 80 course codes (known core confirmed). Remaining work: decode topRule into flat membership → publish uq-programs.json for ATLAS. **Constraint from Sean: strictly read-only in Jac — no modify/workflow/state endpoints, ever.** All probing to date was search/view only.
- **2026-06-03** — PLAN — **Missing/deleted-course discovery, UQBS-first to 2020 (Sean):** layered approach. (1) Harvest covers all currently-listed courses (archives to ~2016). (2) Jac org-pull: page get-resources with organisationId=29 (BUSINESS, +child orgs) through Sean's session → every UQBS course instance Jac has ever held (reaches ≥2021), incl. since-deleted courses, with class numbers/years/periods. (3) Diff vs harvest → deleted set → feed codes back into discover_offerings.py via new --codes-file flag (added); construct URLs from Jac metadata where pages are gone. Residue = deleted + page-gone + pre-Jac (quantify, don't guess). Scrape order: UQBS to 2020 first, all-of-UQ depth decided later. Note: scrape.py will need an --offerings-index input for pre-7450 semesters (build after harvest confirms URL formats).
- **2026-06-03** — FINDING/FEATURE — **Historical discovery solved without JacSON dependency.** Sean confirmed (MGTS7610 screenshot) that programs-courses.uq.edu.au course pages list ALL offerings back to ~2016 under 'Archived offerings', each with a live course-profile link containing the course-class-semester triplet. Built `scraper/discover_offerings.py`: harvests every course page (must run from non-cloud IP — Sean's Mac; programs-courses 405s cloud ranges), writes `data/offerings-index.json`, saves a sample HTML for parser QA, prints per-semester-code profile counts. Parser unit-tested. Caveats: courses discontinued pre-2024 absent from course list (A–Z catalogue would be needed); pre-~2019 profiles may use a legacy template — check parseability before scraping. Run order: after the 2024–26 backfill finishes.
- **2026-06-03** — PLAN — **Historical expansion phase agreed (Sean):** backfill all-of-UQ profiles for all 9 remaining JacSON semesters (7450–7660; 7620 done) — runs on Sean's Mac via terminal (no GitHub Actions, no tokens; sandbox can't reach UQ domains anyway). Then audit 2024–2025 LO coverage to date the Drupal bug; decide restoration scope AFTER seeing numbers. Weekly Actions cron decision deferred. Limit: JacSON index starts at 7450 (S1 2024), so 2023 isn't discoverable.
- **2026-06-03** — FINDING — Mystery semester codes identified: **7490 and 7590 are tiny medical-school special teaching periods** (IMED1242S, ANAT7900S — note the 'S' suffix course codes), NOT MBA terms. **MBA weekend/intensive offerings are published as extra class instances inside standard semester folders** (e.g. MGTS7812's two classes in 7620). Summer semesters have their own codes (7480, 7580). Odd-delivery handling therefore = backfill every folder + a teaching-period registry (taxonomy/teaching-periods.json, replaces hardcoded codeMap in app.js) + class-number matching for multi-instance courses (already in jac_extract.js).
- **2026-06-03** — DECISION (Sean) — **Framing flipped: Jac is the official source of truth.** Jac is the curriculum document the academic authored and published; the public course profile is a lossy rendering of it. The platform therefore presents the COMPLETE record (matching Jac), with provenance acknowledged where data was restored. Supersedes the 'profiles are the benchmark, overrides are a patch' framing.
- **2026-06-03** — CHANGE — Reframed all user-facing surfaces: amber ✎ 'manually corrected' replaced with a neutral 'Jac' provenance badge (tooltip: 'From Jac, the authored curriculum record — omitted from the published profile by a publishing fault'). Legend, assessment-detail line, Markdown export and printable export reworded to match. Overlay _metadata description likewise ('completes the record').
- **2026-06-03** — CHANGE — JSON downloads (per-course + bulk ZIP) now serve the COMPLETE record via new `completeCourseJson()` in app.js: restored mappings written into `learning_outcomes_assessed` with `learning_outcomes_assessed_source: "jac"` and a `_lo_mapping_provenance` block. Scope per Sean: all user-facing surfaces complete; `profiles/` stays raw ingestion (evidence of what UQ publishes). Verified: render shows no old language, Jac badge present, completed JSON validated. **Needs push:** app.js, styles.css, import_lo_overrides.py, taxonomy/lo-overrides.json, PROJECT_LOG.md.
- **2026-06-03** — DEPLOYED — Sessions 10–11 pushed to GitHub (commit 5839218) and verified live: overlay JSON serving on Pages with all 135 overrides. UQBS viewer now shows corrected mappings with ✎ marker.
- **2026-06-03** — DECISION — ATLAS integration via Option A: ATLAS fetches the published overlay (taxonomy/lo-overrides.json) and merges client-side with identical semantics (course+semester+title, exact semester over blank, replace). Raw profiles remain a faithful record of UQ's published pages — corrections are overlay-only, by design. Note: raw-JSON consumers do NOT see corrections unless they merge the overlay.
- **2026-06-03** — DECISION — Provenance display differs by audience: UQBS viewer shows explicit ✎ 'manually corrected' (LD team needs patched-vs-scraped distinction); ATLAS shows a quiet provenance note ('LO mapping sourced from the curriculum system (Jac)') rather than 'manually corrected', to explain mismatches with published ECPs without inviting doubt. ATLAS retains an internal marker either way.
- **2026-06-03** — DATA — Recovered all 43 courses' authoritative assessment→LO mappings from Jac (curriculum.uq.edu.au) via its REST API (`get-resources` → `curriculums/v2/{cvid}/components` → matrix parse). Filled `lo-overrides.csv` (135/135 rows, 0 warnings); all renders verified. Reusable recipe in `scraper/jac_extract.js`. MGTS7812 dual-offering handled; ECON3430 verified correct (no override). Not yet committed/pushed.
- **2026-06-03** — FEATURE — LO-to-assessment override overlay (item #26). Replace-per-assessment semantics handles both full and *partial* Drupal LO-mapping drops. New: `taxonomy/lo-overrides.csv` (135 blank scaffold rows / 43 offerings), `scraper/import_lo_overrides.py`, `scraper/lo_coverage_report.py`, viewer merge + amber override chips/legend, workflow rebuild step. Resolver 7/7 sandbox tests + end-to-end render pass.
- **2026-06-03** — FINDING — Coverage diagnostic surfaced 9 partial-drop courses the Session 9 audit missed (8 MISSING_SOME + ECON3430 UNREFERENCED) — they render *some* LOs so looked fine. Logged as open item #29 for team review.
- **2026-04-14** — FEATURE — Added manual Auto/Light/Dark colour-mode toggle in header nav (alongside existing Classic/Fun theme toggle); persisted in `localStorage["uqbs-color-mode"]`; CSS now responds to `[data-color-mode]` attribute in addition to `prefers-color-scheme`
- **2026-04-14** — FEATURE — Classic/Fun theme toggle with `data-theme` attribute; magazine/editorial styling for Fun (gradient header, serif display, faculty-prefix colour-coded codes, pull-quote assessment details); FOUC-prevention inline script on all three pages
- **2026-04-14** — FEATURE — Bulk downloads on course browser (CSV / ZIP Markdown / ZIP JSON, filtered) via JSZip; per-course downloads on course detail (JSON / Markdown / printable HTML with A4 print stylesheet)
- **2026-04-14** — RESOLUTION — Policy-text stopword joins fixed in historical data (`scraper/clean_existing.py`) and future scrapes (`scraper/scrape.py` → `normalise_ws`); closed-vocabulary rules prevent false positives; URLs/emails shielded during regex pass; 0 remaining artefacts across 838 profiles
- **2026-04-14** — RESOLUTION — Assessment summary LOs column now populated from `assessment_details.learning_outcomes_assessed`; `parseLoRefs()` tolerates `LO1`, `L01` (zero-typo), `L.O. 1`, and bare-number variants; column hidden when no assessment has any linked LOs
- **2026-04-14** — RESOLUTION — LO code rendering fixed (`loDisplayCode()` helper) — handles `lo.number` as `"LO1."`, `"L01"`, `1`, or `"1"` without doubling the `LO` prefix
- **2026-04-14** — PHASE 2 — Built static-site viewer (`docs/`): course browser, per-course detail, program/major pages; deploys via GitHub Pages workflow; manifest generator added to scraper
- **2026-04-14** — MILESTONE — Run 9 (full semester, 308 courses) completed: 202 profiles, 0 failures, 100% coverage on critical fields; scraper declared production-ready
- **2026-04-13 22:00** — RESOLUTION — Fixed staff interleaved role groups (MGTS7619); changed dedup to `(name, role)` to allow same person under different roles
- **2026-04-13 21:45** — TEST (Run 7) — GitHub Actions: 4/5 MGTS courses scraped. MGTS7619 staff roles wrong, assessment LOs genuinely absent.
- **2026-04-13 21:30** — RESOLUTION — Fixed aims extraction for bare text nodes (ACCT1101); browser-verified via JS on live page
- **2026-04-13 21:15** — RESOLUTION — Fixed assessment summary titles (separated indicators into `conditions` field), staff roles/dedup, due date separators
- **2026-04-13 21:00** — TEST (Run 6) — GitHub Actions: 3/5 ACCT courses scraped (2 not offered in Sem 1). LOs correct across all. Identified summary title and staff issues.
- **2026-04-13 20:30** — RESOLUTION — Fixed LO off-by-one bug; reversed same-`<p>` / sibling priority in `_extract_learning_outcomes()`
- **2026-04-13 20:15** — ANALYSIS — Identified root cause: server HTML puts LO number + desc in same `<p>`; confirmed by comparing with Geoff's jacson.py approach
- **2026-04-13 20:00** — NOTE — Sean provided manual page download (browser "Save As") and course profile viewer extension for HTML structure analysis
- **2026-04-13 19:00** — TEST (Run 5) — GitHub Actions: LOs correct, assessment details correct. All extraction verified against Geoff's JacSON output.
- **2026-04-13 18:30** — TEST (Run 4) — GitHub Actions: Assessment detail scoping fixed. LO off-by-one still present.
- **2026-04-13 18:00** — RESOLUTION — Fixed assessment detail scoping (sibling-walking with `el.__copy__()` into temp Tag)
- **2026-04-13 17:30** — TEST (Run 3) — GitHub Actions: First successful scrape of MGTS1601. JSON review found assessment detail scoping bug and LO off-by-one.
- **2026-04-13 17:15** — RESOLUTION — Replaced `programs-courses.uq.edu.au` discovery with GitHub Tree API
- **2026-04-13 17:00** — TEST (Run 2) — GitHub Actions: 405 from programs-courses.uq.edu.au
- **2026-04-13 16:45** — RESOLUTION — Added `permissions: contents: write` and `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` to workflow
- **2026-04-13 16:40** — TEST (Run 1) — GitHub Actions: exit code 128 (missing permissions)
- **2026-04-13 16:30** — CHANGE — Initial scraper build complete, all files created. Repo pushed via GitHub Desktop.
- **2026-04-13 16:25** — RESOLUTION — Fixed LO extraction for single-wrapper page layout
- **2026-04-13 16:25** — RESOLUTION — Fixed assessment summary to exclude nested detail tables
- **2026-04-13 16:20** — ISSUE — Cowork sandbox blocks UQ servers (proxy 403)
- **2026-04-13 16:15** — DECISION — GitHub Actions as primary runner (confirmed course-profiles.uq.edu.au accessible)
- **2026-04-13 16:10** — DECISION — Separate repo, GitHub Actions + local, taxonomy for course list
- **2026-04-13 15:45** — NOTE — Inspected live MGTS1601 profile page, identified all extractable fields
- **2026-04-13 15:30** — NOTE — Explored Geoff's JacSON-Pi v1.0.5 codebase
