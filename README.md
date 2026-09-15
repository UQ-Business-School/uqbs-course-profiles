# UQ Course Profile Scraper + Viewer

Enriched course profile scraper and static-site viewer, originally built for UQ Business School and now supporting all of UQ. Captures a comprehensive data set from published UQ course profiles for use in learning design, Graduate Attribute mapping, and Assurance of Learning reporting.

> **Not an official UQ source.** This is a working tool maintained by the UQ Business School learning design team. It is not endorsed by, or an official publication of, The University of Queensland. The data is scraped from the publicly published course profiles at course-profiles.uq.edu.au and can lag, drop or misread what is published there. The published course profile is always the source of truth; check it before relying on anything here. Questions and corrections: learningdesign@business.uq.edu.au.

Built on the [JacSON](https://github.com/uq-course-profiles/jacson) architecture by Geoff, extended with enriched fields and a UQBS-specific intelligence layer.

**Components:**

- `scraper/` — Python scraper that produces enriched JSON per course (UQBS or all-of-UQ)
- `docs/` — Static-site viewer (vanilla HTML + JS, no build step) served via GitHub Pages
- `taxonomy/` — UQBS program/course taxonomy, AoL overlay data, and other internal data layers

**Runs automatically:** The scrape workflow runs weekly on GitHub Actions (UQBS by default). All-of-UQ scrapes available via manual dispatch or local runs.

## What it captures

The scraper pulls data from two UQ domains:

**From course-profiles.uq.edu.au** (the full profile page):

- Course title, code, semester, study period
- Study level (UG/PG), units, coordinating unit, administrative campus
- Course description (full overview text)
- Course aims statement
- Course requirements (prerequisites, incompatible courses, companions)
- Learning outcomes (number + description)
- Assessment summary (category, title, weight, due date)
- Assessment details per item:
  - Task description, submission guidelines
  - Learning outcomes assessed (assessment-to-LO mapping)
  - Mode, category, conditions (time-limited, secure, etc.)
  - Exam details
  - AI/academic integrity statements
  - Deferral/extension and late submission policies
  - Special indicators
- Learning activities (week, type, topic, LO mapping)
- Learning resources
- Course contacts and staff
- Timetable information
- Policies and procedures

**From programs-courses.uq.edu.au** (the course catalogue):

- Faculty, school
- Class hours (e.g. "Seminar 2 Hours/Week")
- Duration
- Study abroad eligibility
- Course description (short version)

## Course list

**UQBS mode (default):** Uses `taxonomy/uqbs-programs.json` as its source of truth — 323 courses across 23 programmes (7 UG + 15 PG), verified against my.UQ structured data.

**All-of-UQ mode (`--all-uq`):** Uses the JacSON GitHub repo index to discover all UQ courses — approximately 1,750 courses per semester across all faculties.

## Quick start

```bash
# Install dependencies
pip3 install -r scraper/requirements.txt

# Test with a single course
python3 scraper/scrape.py --courses MGTS1601

# Scrape a specific semester (UQBS only)
python3 scraper/scrape.py --semester 7620

# Scrape first 10 courses (for testing)
python3 scraper/scrape.py --max 10

# Full UQBS scrape (all 323 courses)
python3 scraper/scrape.py

# All-of-UQ scrape for a specific semester
python3 scraper/scrape.py --all-uq --semester 7620

# All-of-UQ with faster delay (for historical/static semesters)
python3 scraper/scrape.py --all-uq --semester 7520 --delay 0.5

# Using the runner script (with optional git push)
./run_scrape.sh --courses MGTS1601 ACCT1101
./run_scrape.sh --push   # scrape all + commit and push
```

## Output

Scraped profiles are saved as JSON files under `profiles/{semester_code}/`:

```
profiles/
├── 7620/
│   ├── MGTS1601-20353-7620.json
│   ├── ACCT1101-20001-7620.json
│   └── ...
└── 7660/
    └── ...
```

## Scheduling

**Primary: GitHub Actions** — `.github/workflows/scrape.yml` runs weekly (Sundays 9pm AEST) and supports manual dispatch with semester/course filters. `course-profiles.uq.edu.au` is accessible from GitHub Actions runners, so the full scrape runs cleanly in the cloud. The workflow commits new profiles back to the repo, which automatically triggers a viewer redeploy.

**Optional: macOS launchd** — For a local backup runner, edit the path in `com.uqbs.course-scraper.plist` and install it with `launchctl load ~/Library/LaunchAgents/com.uqbs.course-scraper.plist`. Manual run: `./run_scrape.sh --push`.

## Viewer and data host

The viewer is not in this repo. It lives in `UQ-Business-School/courses` under `uqbsld/profiles/` and is served at `teach.business.uq.edu.au/ld/uqbsld/profiles/` (the school server mirrors that repo with about a 15 minute delay). Edit the viewer there; there is no other copy.

This repo is the data host. `.github/workflows/pages.yml` publishes `docs/` to GitHub Pages whenever `profiles/`, `taxonomy/` or `docs/` change: it rebuilds the manifests, builds the assessment security feed, copies `profiles/`, `profiles-legacy/` and `taxonomy/` in, and deploys. The viewer fetches everything it reads (manifests, profile JSON, taxonomies, LO overrides, teaching periods, the AoL feed) from that Pages site, set as `dataBase` in the viewer's `assets/site-config.js`. `docs/index.html` is a redirect to the viewer for anyone who lands on the Pages site directly.

The manifest generator can be run on its own:

```bash
python3 scraper/build_manifest.py   # writes docs/assets/manifest.json, manifest-all.json and manifest-legacy.json
```

## AoL feed

The viewer's Assurance of Learning layer (the AoL column, the course-page card and `aol.html`) reads `taxonomy/aol-status.json` from this repo's Pages site. That file is built from `taxonomy/aol-template.csv`, which is exported from the UQBS AoL register workbook (`UQBS-AoL-Register.xlsx` in the team's SharePoint AoL folder). The register is the master: statuses in the CSV, in `scraper/import_aol.py` and in `AOL_STATUS` in the viewer's `assets/app.js` (courses repo) mirror its Lists tab, so a new status is added to the register first and then to both files.

The feed carries course, GA, assessment, status and rubric link only. Learning designer names, coordinators and notes stay in the workbook. Rubric links point into SharePoint and open for signed-in staff.

The semester on each row is the offering the rubric was found in. `scraper/export_aol_register.py` works it out from the Blackboard pull folders and gradebook notes of the September 2026 sweeps, then from the register's "First implemented" column, and otherwise uses the current semester; `logs/aol-export-report.csv` records the source for every row.

To refresh after a register change (SharePoint is not reachable from Actions, so this runs on a machine that can see the workbook):

```bash
python3 scraper/export_aol_register.py \
  --workbook "<SharePoint>/4. AoL (Sean)/UQBS-AoL-Register.xlsx" \
  --pulls "<Curriculum Uplift>/AoL_sweep_pulls" --pulls "<Curriculum Uplift>/AoL_wide_pulls" \
  --native-rubrics "<Curriculum Uplift>/AoL_wide_pulls/AoLPULL__wide_native_rubrics.json"
git add taxonomy/aol-template.csv taxonomy/aol-status.json logs/aol-export-report.csv && git commit -m "AoL feed: register as at <date>" && git push
```

The weekly scrape run rebuilds `aol-status.json` from the committed CSV as well, so committing the CSV alone is enough; committing the JSON too means the viewer shows it after the next Pages build (a few minutes) rather than the next scrape.

## Semester codes

| Code | Semester |
|------|----------|
| 7420 | Semester 1, 2024 |
| 7450 | Summer, 2024 |
| 7460 | Semester 2, 2024 |
| 7480 | Summer, 2024/25 |
| 7490 | Trimester 3, 2024 |
| 7520 | Semester 1, 2025 |
| 7560 | Semester 2, 2025 |
| 7580 | Summer, 2025/26 |
| 7590 | Trimester 3, 2025 |
| 7620 | Semester 1, 2026 |
| 7660 | Semester 2, 2026 |

Pattern: first two digits encode the year (7 = 2020s decade, second digit = year offset), third digit encodes the term (2 = Sem 1, 5/6 = Sem 2, 8 = Summer, 9 = Tri 3), fourth digit is sub-term (usually 0).

## Dependencies

- Python 3.10+
- beautifulsoup4
- requests

