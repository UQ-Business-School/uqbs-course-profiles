#!/usr/bin/env python3
"""
discover_offerings.py — Harvest every published course-profile link (current +
archived) from programs-courses.uq.edu.au, per course.

WHY: course profile URLs need a course+class+semester triplet
(e.g. MGTS7610-20353-7620). Geoff's JacSON index only covers semesters from
7450 (Semester 1 2024). But each course's programs-courses page lists ALL its
offerings — archived ones back to ~2016 — each with a direct profile link that
contains the triplet. Harvesting those pages builds a historical URL index
without depending on anyone else's repo.

MUST RUN FROM A NON-CLOUD IP (e.g. Sean's Mac). programs-courses.uq.edu.au
returns 405 to GitHub Actions / cloud ranges.

USAGE (from the repo root on the Mac):
  python3 scraper/discover_offerings.py --max 5          # smoke test
  python3 scraper/discover_offerings.py                  # full run (~1 hr at 1s delay)
  python3 scraper/discover_offerings.py --uqbs-only      # Business School courses only
  python3 scraper/discover_offerings.py --delay 0.5      # faster (be polite)

OUTPUT:
  data/offerings-index.json    course -> [ {semester, dates, location, mode,
                               profile_url, class_code, semester_code, archived} ]
  logs/discover_sample.html    raw HTML of the first page fetched (for parser QA)
  Prints a per-semester-code summary at the end so you can see how far back
  the archive reaches and how many profiles each old semester would add.

NOTES:
- Harvest only: nothing is scraped from course-profiles.uq.edu.au here.
  Feed the index to scrape.py afterwards (next step once we see the shape).
- Older profiles (pre ~2019) may use a legacy page template; the harvest
  records their URLs regardless, and we check parseability separately before
  committing to scrape them.
- Courses discontinued before 2024 aren't in the JacSON-derived course list,
  so their archives won't be found this way. Completeness for dead courses
  would need the programs-courses A–Z catalogue as a second source (future).
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "offerings-index.json"
SAMPLE_PATH = REPO_ROOT / "logs" / "discover_sample.html"
TAXONOMY = REPO_ROOT / "taxonomy" / "uqbs-programs.json"
PROFILES_DIR = REPO_ROOT / "profiles"

COURSE_PAGE = "https://programs-courses.uq.edu.au/course.html?course_code={code}"
JACSON_TREE = "https://api.github.com/repos/uq-course-profiles/jacson/git/trees/main?recursive=1"
HEADERS = {"User-Agent": "UQBS-LD-team course profile indexer (contact: learningdesign@business.uq.edu.au)"}

# Matches .../course-profiles/MGTS7610-20353-7620 (current system, S2 2024 onwards)
RE_TRIPLET = re.compile(r"/course-profiles/([A-Z]{4}\d{4}[A-Z]?)-(\d{3,6})-(\d{4})")
# Matches archive.course-profiles.uq.edu.au/student_section_loader/section_1/132418
# (legacy ECP system, pre S2 2024 — opaque numeric profile id; semester/year only
# in the row label text)
RE_LEGACY = re.compile(r"archive\.course-profiles\.uq\.edu\.au/student_section_loader/section_\d+/(\d+)")
RE_LABEL = re.compile(r"(Semester\s+\d|Summer Semester|Trimester\s+\d)[^\d]*(\d{4})", re.I)


def load_course_codes(uqbs_only: bool) -> list[str]:
    """Course universe: UQBS taxonomy, or all courses known to the JacSON index."""
    codes: set[str] = set()
    if uqbs_only:
        tax = json.load(open(TAXONOMY, encoding="utf-8"))
        for prog in tax.get("programs", {}).values():
            for field in ["core", "flexible_core", "flexible_core_a", "flexible_core_b",
                          "program_electives", "foundational_courses", "capstone",
                          "pathway_prerequisites", "research_courses", "advanced_courses",
                          "general_pathway_courses"]:
                codes.update(prog.get(field, []))
            for major_codes in prog.get("majors", {}).values():
                codes.update(major_codes)
    else:
        # All-of-UQ: every course that appears in Geoff's index (2024+ universe)
        r = requests.get(JACSON_TREE, headers=HEADERS, timeout=60)
        r.raise_for_status()
        for node in r.json().get("tree", []):
            m = re.match(r"profiles/\d{4}/([A-Z]{4}\d{4}[A-Z]?)-", node.get("path", ""))
            if m:
                codes.add(m.group(1))
        # Plus anything we've already scraped (belt and braces)
        if PROFILES_DIR.exists():
            for f in PROFILES_DIR.glob("*/*.json"):
                m = re.match(r"([A-Z]{4}\d{4}[A-Z]?)-", f.name)
                if m:
                    codes.add(m.group(1))
    return sorted(codes)


def parse_course_page(html: str) -> list[dict]:
    """Pull every offering row (current + legacy systems) from a course page.

    Rows are <tr id='course-offering-N'> with classed cells:
    .course-offering-year / -location / -mode / -profile. Profile links come in
    two eras: the current course-profiles.uq.edu.au triplet URLs (S2 2024 on),
    and legacy archive.course-profiles.uq.edu.au section_loader ids (to ~2009).
    """
    soup = BeautifulSoup(html, "html.parser")
    offerings = []
    for tr in soup.find_all("tr", id=re.compile(r"^course-offering")):
        def cell(cls):
            return tr.find("td", class_=cls)
        sem_cell = cell("course-offering-year") or tr.find("td")
        label = sem_cell.get_text(" ", strip=True) if sem_cell else ""
        loc_c, mode_c, prof_c = cell("course-offering-location"), cell("course-offering-mode"), cell("course-offering-profile")
        location = loc_c.get_text(" ", strip=True) if loc_c else ""
        mode = mode_c.get_text(" ", strip=True) if mode_c else ""
        a = prof_c.find("a", href=True) if prof_c else None
        if not a:
            continue
        href = a["href"]
        h = tr.find_previous(re.compile(r"^h[1-4]$"))
        archived = bool(h and "archiv" in h.get_text(strip=True).lower())
        m = RE_LABEL.search(label)
        rec = {
            "semester": label, "location": location, "mode": mode, "archived": archived,
            "year": int(m.group(2)) if m else None,
            "period": m.group(1).title() if m else None,
        }
        mn = RE_TRIPLET.search(href)
        ml = RE_LEGACY.search(href)
        if mn:
            rec.update(system="current", course_code=mn.group(1), class_code=mn.group(2),
                       semester_code=mn.group(3),
                       profile_url=href if href.startswith("http")
                                    else "https://course-profiles.uq.edu.au" + href)
        elif ml:
            rec.update(system="legacy", legacy_id=ml.group(1), profile_url=href)
        else:
            continue
        offerings.append(rec)
    # Dedup by profile URL
    seen, out = set(), []
    for o in offerings:
        if o["profile_url"] in seen:
            continue
        seen.add(o["profile_url"])
        out.append(o)
    return out


def main():
    p = argparse.ArgumentParser(description="Harvest course profile URLs from programs-courses")
    p.add_argument("--max", type=int, default=None, help="Limit number of courses (testing)")
    p.add_argument("--delay", type=float, default=1.0, help="Seconds between requests (min 0.3)")
    p.add_argument("--uqbs-only", action="store_true")
    p.add_argument("--resume", action="store_true",
                   help="Skip courses already present in the output index")
    p.add_argument("--codes-file", type=Path, default=None,
                   help="File of extra course codes (one per line) to include — "
                        "e.g. since-deleted courses discovered via Jac")
    p.add_argument("--codes-only", action="store_true",
                   help="Use ONLY the codes from --codes-file (targeted testing)")
    args = p.parse_args()
    delay = max(args.delay, 0.3)

    print("Building course list...")
    codes = [] if args.codes_only else load_course_codes(args.uqbs_only)
    if args.codes_file and args.codes_file.exists():
        extra = [l.strip().upper() for l in args.codes_file.read_text().splitlines()
                 if re.match(r"^[A-Z]{4}\d{4}[A-Z]?$", l.strip().upper())]
        before = len(codes)
        codes = sorted(set(codes) | set(extra))
        print(f"  +{len(codes) - before} extra codes from {args.codes_file}")
    print(f"  {len(codes)} courses" + (" (UQBS only)" if args.uqbs_only else " (all of UQ)"))
    if args.max:
        codes = codes[:args.max]
        print(f"  limited to first {args.max}")

    # ALWAYS merge into an existing index — a targeted run (--codes-file /
    # --codes-only / --max) must never clobber the full harvest. New results
    # for a course replace that course's entry; everything else is preserved.
    index: dict = {}
    if OUT_PATH.exists():
        index = json.load(open(OUT_PATH, encoding="utf-8")).get("courses", {})
        print(f"  merging into existing index ({len(index)} courses already on file)")
    if args.resume:
        codes = [c for c in codes if c not in index]
        print(f"  resume: {len(codes)} remaining")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)

    failures = []
    for i, code in enumerate(codes, 1):
        url = COURSE_PAGE.format(code=code)
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code != 200:
                failures.append(f"{code}: HTTP {r.status_code}")
                continue
            if i == 1 and not SAMPLE_PATH.exists():
                SAMPLE_PATH.write_text(r.text, encoding="utf-8")
            offs = parse_course_page(r.text)
            index[code] = offs
            print(f"[{i}/{len(codes)}] {code}: {len(offs)} offerings "
                  f"({sum(1 for o in offs if o['archived'])} archived)")
        except requests.RequestException as e:
            failures.append(f"{code}: {e}")
        # periodic save so long runs are resumable
        if i % 100 == 0:
            json.dump({"_meta": {"updated": datetime.now().isoformat()}, "courses": index},
                      open(OUT_PATH, "w", encoding="utf-8"), indent=1)
        time.sleep(delay)

    json.dump({"_meta": {"updated": datetime.now().isoformat(),
                         "course_count": len(index),
                         "failures": failures},
               "courses": index},
              open(OUT_PATH, "w", encoding="utf-8"), indent=1)

    # Summary: offerings per year, split current/legacy systems, oldest first
    per_year: dict = {}
    for offs in index.values():
        for o in offs:
            y = o.get("year") or 0
            d = per_year.setdefault(y, {"current": 0, "legacy": 0})
            d[o.get("system", "current")] += 1
    print("\n========== OFFERINGS PER YEAR ==========")
    print(f"  {'year':<8}{'current-system':>16}{'legacy-system':>15}")
    for y in sorted(per_year):
        d = per_year[y]
        print(f"  {y or '????':<8}{d['current']:>16}{d['legacy']:>15}")
    print(f"\nCourses indexed: {len(index)}  |  failures: {len(failures)}")
    for f in failures[:10]:
        print("  !", f)
    print(f"\nIndex written to {OUT_PATH}")


if __name__ == "__main__":
    main()
