#!/usr/bin/env python3
"""
fetch_legacy.py — Overnight fetcher: download legacy ECP pages as raw HTML.

Downloads (does NOT parse) every legacy-system course profile listed in
data/offerings-index.json from archive.course-profiles.uq.edu.au, saving raw
HTML to data/legacy_html/. Parsing happens later, offline, against the cache —
so this only ever needs to run once per scope.

STRATEGY (decided automatically at startup):
  1. Try the print endpoint on a test profile — POST
     /student_section_loader/print/{id} with print_section_1..7 — which serves
     the ENTIRE profile in one response. If it works: 1 request per profile.
  2. If print fails/hangs: fall back to fetching sections 1–7 individually
     (7 requests per profile).

USAGE (on the Mac, from the repo root):
  python3 scraper/fetch_legacy.py --dry-run                 # counts only, no network
  python3 scraper/fetch_legacy.py                           # UQBS, 2020 onwards (default)
  python3 scraper/fetch_legacy.py --since-year 2009         # UQBS, everything
  python3 scraper/fetch_legacy.py --scope all --since-year 2020   # all of UQ
  caffeinate -i python3 scraper/fetch_legacy.py             # << OVERNIGHT: stops Mac sleeping

Resumable: already-downloaded profiles are skipped, so re-running continues
where it left off. Progress logs every 25 profiles. Raw HTML is git-ignored
(data/legacy_html/) — do not commit it.

Rough timings at 0.5s delay: UQBS-2020 (≈2,600 profiles) ≈ 45–60 min via print,
≈ 4–5 h via sections. All-UQ-2020 (≈20,600) ≈ 6–7 h via print only — the
script warns if you pick a scope/strategy combination that won't finish overnight.
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent.parent
INDEX = REPO / "data" / "offerings-index.json"
OUT = REPO / "data" / "legacy_html"
TAXONOMY = REPO / "taxonomy" / "uqbs-programs.json"
BASE = "https://archive.course-profiles.uq.edu.au/student_section_loader"
HEADERS = {"User-Agent": "UQBS-LD-team legacy profile archiver (contact: learningdesign@business.uq.edu.au)"}
PRINT_BODY = {f"print_section_{i}": "1" for i in range(1, 8)}


def uqbs_courses():
    tax = json.load(open(TAXONOMY, encoding="utf-8"))
    out = set()
    for prog in tax.get("programs", {}).values():
        for f in ["core", "flexible_core", "flexible_core_a", "flexible_core_b",
                  "program_electives", "foundational_courses", "capstone",
                  "pathway_prerequisites", "research_courses", "advanced_courses",
                  "general_pathway_courses"]:
            out.update(prog.get(f, []))
        for codes in prog.get("majors", {}).values():
            out.update(codes)
    return out


def build_worklist(scope, since_year):
    idx = json.load(open(INDEX, encoding="utf-8"))["courses"]
    uqbs = uqbs_courses() if scope == "uqbs" else None
    work = []
    for code, offs in idx.items():
        if uqbs is not None and code not in uqbs:
            continue
        for o in offs:
            if o.get("system") != "legacy":
                continue
            y = o.get("year") or 0
            if y < since_year:
                continue
            work.append({"course": code, "year": y,
                         "period": (o.get("period") or "").replace(" ", ""),
                         "id": o["legacy_id"]})
    # stable order: by year then course (oldest first — most at risk of disappearing)
    work.sort(key=lambda w: (w["year"], w["course"]))
    return work


def fname(w, kind, section=None):
    sec = f"_s{section}" if section else ""
    return OUT / f"{w['course']}_{w['year']}_{w['period'] or 'X'}_{w['id']}_{kind}{sec}.html"


def looks_complete(html):
    """A print page should contain at least course info + assessment markers."""
    return (len(html) > 15000
            and re.search(r"Assessment", html, re.I)
            and re.search(r"Course\s+(Information|Description)", html, re.I))


def test_print(session, wid):
    try:
        r = session.post(f"{BASE}/print/{wid}", data=PRINT_BODY,
                         headers=HEADERS, timeout=90)
        if r.status_code == 200 and looks_complete(r.text):
            return True
    except requests.RequestException:
        pass
    return False


def main():
    p = argparse.ArgumentParser(description="Overnight legacy ECP HTML fetcher")
    p.add_argument("--scope", choices=["uqbs", "all"], default="uqbs")
    p.add_argument("--since-year", type=int, default=2020)
    p.add_argument("--delay", type=float, default=0.5)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force-sections", action="store_true",
                   help="Skip the print attempt, always fetch sections 1-7")
    args = p.parse_args()
    delay = max(args.delay, 0.3)

    work = build_worklist(args.scope, args.since_year)
    per_year = {}
    for w in work:
        per_year[w["year"]] = per_year.get(w["year"], 0) + 1
    print(f"Scope: {args.scope}, since {args.since_year} -> {len(work)} legacy profiles")
    for y in sorted(per_year):
        print(f"  {y}: {per_year[y]}")
    if args.dry_run:
        est_print = len(work) * (delay + 0.8) / 3600
        est_sec = len(work) * 7 * (delay + 0.6) / 3600
        print(f"\nEstimated: ~{est_print:.1f} h via print, ~{est_sec:.1f} h via sections")
        return

    OUT.mkdir(parents=True, exist_ok=True)
    session = requests.Session()

    # Decide strategy on the first not-yet-downloaded profile
    use_print = False
    if not args.force_sections and work:
        print("Testing print endpoint...", flush=True)
        use_print = test_print(session, work[0]["id"])
        print(f"  print endpoint {'WORKS — 1 request/profile' if use_print else 'unavailable — falling back to 7 section requests/profile'}")
    if not use_print and args.scope == "all":
        est = len(work) * 7 * (delay + 0.6) / 3600
        print(f"  WARNING: all-of-UQ via sections ≈ {est:.0f} h. Consider --scope uqbs tonight.")

    done = skipped = failed = 0
    t0 = time.time()
    for i, w in enumerate(work, 1):
        try:
            if use_print:
                f = fname(w, "print")
                if f.exists():
                    skipped += 1
                else:
                    r = session.post(f"{BASE}/print/{w['id']}", data=PRINT_BODY,
                                     headers=HEADERS, timeout=90)
                    if r.status_code == 200 and looks_complete(r.text):
                        f.write_text(r.text, encoding="utf-8")
                        done += 1
                    else:
                        failed += 1
                    time.sleep(delay)
            else:
                got_any = False
                for sec in range(1, 8):
                    f = fname(w, "section", sec)
                    if f.exists():
                        got_any = True
                        continue
                    r = session.get(f"{BASE}/section_{sec}/{w['id']}",
                                    headers=HEADERS, timeout=60)
                    if r.status_code == 200 and len(r.text) > 3000:
                        f.write_text(r.text, encoding="utf-8")
                        got_any = True
                    time.sleep(delay)
                if got_any:
                    done += 1
                else:
                    failed += 1
        except requests.RequestException:
            failed += 1
            time.sleep(2)  # brief backoff, keep going
        if i % 25 == 0 or i == len(work):
            rate = i / max(time.time() - t0, 1)
            eta = (len(work) - i) / max(rate, 0.01) / 3600
            print(f"[{i}/{len(work)}] saved {done}, skipped {skipped}, failed {failed} "
                  f"| ETA {eta:.1f} h", flush=True)

    print(f"\nDONE. saved {done}, skipped (already had) {skipped}, failed {failed}")
    print(f"Cache: {OUT}")
    if failed:
        print("Failures are usually transient — re-run the same command; it resumes.")


if __name__ == "__main__":
    main()
