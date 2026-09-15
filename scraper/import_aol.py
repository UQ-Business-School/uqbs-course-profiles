#!/usr/bin/env python3
"""
import_aol.py: build the AoL status overlay (taxonomy/aol-status.json) from
taxonomy/aol-template.csv.

The CSV is written by scraper/export_aol_register.py from the UQBS AoL
register workbook (UQBS-AoL-Register.xlsx on SharePoint). It can also be
edited by hand. Columns:

  semester_code, course_code, ga, assessment_title, status, rubric_url, notes

Statuses mirror the register's Lists tab exactly. The register is the master;
this file and docs/assets/app.js (AOL_STATUS) carry the same nine. Change the
register first, then both of these.

Semester labels come from taxonomy/teaching-periods.json, the single source
of truth for period codes (7620 is S1 2026, 7660 is S2 2026; the spacing is
not uniform, so never compute a code).

Usage:
  python scraper/import_aol.py                        # defaults
  python scraper/import_aol.py --csv path/to/aol.csv
  python scraper/import_aol.py --validate-only
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

# --- constants ---------------------------------------------------------------

# slug -> (register label, meaning). Order is the ladder used by the viewer.
STATUSES = {
    "na":                         ("N/A",
                                   "Not ours to map. Another school's course, or otherwise out of scope."),
    "tbd":                        ("TBD",
                                   "The AoL instrument for this GA has not been settled yet."),
    "identified":                 ("Identified",
                                   "Course and assessment agreed. Rubric work not started."),
    "rubric_in_dev":              ("Rubric in development",
                                   "Rubric being built or revised to carry all three GA criteria."),
    "partial_mapping":            ("Partial mapping",
                                   "Rubric is live and marked as AoL, but carries fewer than three GA criteria."),
    "built_awaiting_coordinator": ("Built, awaiting coordinator",
                                   "Rubric carries all three criteria and has been sent. Coordinator sign-off outstanding."),
    "approved_not_installed":     ("Approved, not installed",
                                   "Coordinator has approved the rubric. Not yet applied in a live offering."),
    "awaiting_ld_check":          ("Awaiting LD check",
                                   "A rubric with all three criteria was found live in the course. The learning designer has not confirmed it yet."),
    "active":                     ("Active",
                                   "Rubric carries all three criteria and is in use in a live offering."),
}
VALID_STATUSES = list(STATUSES)
LABEL_TO_SLUG = {label.lower(): slug for slug, (label, _) in STATUSES.items()}

VALID_GAS = ["GA1", "GA2", "GA3", "GA4", "GA5", "GA6"]
GA_NAMES = {
    "GA1": "Accomplished Scholars",
    "GA2": "Courageous Thinkers",
    "GA3": "Connected Citizens",
    "GA4": "Culturally Capable",
    "GA5": "Influential Communicators",
    "GA6": "Respectful Leaders",
}

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = REPO_ROOT / "taxonomy" / "aol-template.csv"
DEFAULT_TAXONOMY = REPO_ROOT / "taxonomy" / "uqbs-programs.json"
DEFAULT_PERIODS = REPO_ROOT / "taxonomy" / "teaching-periods.json"
DEFAULT_OUTPUT = REPO_ROOT / "taxonomy" / "aol-status.json"
# docs/taxonomy is a symlink to taxonomy/ in the source tree; the Pages build
# copies taxonomy/ in. Writing here as well keeps a non-symlinked checkout right.
DOCS_OUTPUT = REPO_ROOT / "docs" / "taxonomy" / "aol-status.json"

TAXONOMY_LIST_FIELDS = [
    "core", "flexible_core", "flexible_core_a", "flexible_core_b",
    "program_electives", "foundational_courses", "capstone",
    "pathway_prerequisites", "research_courses", "advanced_courses",
    "general_pathway_courses",
]


# --- helpers -----------------------------------------------------------------

def normalise_status(raw):
    """Accept either the slug or the register's label. Returns slug or None."""
    s = (raw or "").strip()
    if not s:
        return None
    low = s.lower()
    if low in STATUSES:
        return low
    if low in LABEL_TO_SLUG:
        return LABEL_TO_SLUG[low]
    # tolerate slug-ish variants: spaces, hyphens, dropped punctuation
    key = low.replace(",", "").replace("-", " ").replace("_", " ")
    for slug, (label, _) in STATUSES.items():
        if key == label.lower().replace(",", "") or key == slug.replace("_", " "):
            return slug
    return None


def load_periods(path):
    """semester_code -> label, from teaching-periods.json."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {code: p.get("label", code) for code, p in data.get("periods", {}).items()}


def load_taxonomy(path):
    """Known course codes from the programme taxonomy."""
    with open(path, "r", encoding="utf-8") as f:
        tax = json.load(f)
    known = set(tax.get("course_programs", {}).keys())
    for prog in tax.get("programs", {}).values():
        for field_name in TAXONOMY_LIST_FIELDS:
            known.update(prog.get(field_name, []))
        for codes in prog.get("majors", {}).values():
            known.update(codes)
    return known


def parse_csv(csv_path, period_labels):
    """Parse and validate. Returns (entries, errors, warnings)."""
    entries, errors, warnings = [], [], []

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"semester_code", "course_code", "ga", "assessment_title", "status"}
        have = set(reader.fieldnames or [])
        if not required.issubset(have):
            errors.append(f"CSV missing required columns: {', '.join(sorted(required - have))}")
            return entries, errors, warnings

        for i, row in enumerate(reader, start=2):
            sem = (row.get("semester_code") or "").strip()
            course = (row.get("course_code") or "").strip().upper()
            ga = (row.get("ga") or "").strip().upper()
            assessment = (row.get("assessment_title") or "").strip()
            status_raw = (row.get("status") or "").strip()
            rubric_url = (row.get("rubric_url") or "").strip()
            notes = (row.get("notes") or "").strip()

            if not any([sem, course, ga, assessment, status_raw]):
                continue

            line_errors = []
            if not sem:
                line_errors.append("missing semester_code")
            elif sem not in period_labels:
                warnings.append(f"Row {i}: semester_code '{sem}' not in teaching-periods.json (used as-is)")
            if not course:
                line_errors.append("missing course_code")
            status = normalise_status(status_raw)
            if not status_raw:
                line_errors.append("missing status")
            elif status is None:
                line_errors.append(f"invalid status '{status_raw}' (valid: {', '.join(VALID_STATUSES)})")

            # N/A and TBD rows in the register are a code and a status, nothing else.
            # Anything further along the ladder names a GA; a missing assessment is
            # worth a warning but not worth dropping the row.
            if not ga:
                if status not in ("na", "tbd"):
                    line_errors.append("missing ga")
            elif ga not in VALID_GAS:
                line_errors.append(f"invalid ga '{ga}'")
            if not assessment and status not in ("na", "tbd", None):
                warnings.append(f"Row {i} ({course}): no assessment_title")

            if line_errors:
                errors.append(f"Row {i} ({course or '???'}): {'; '.join(line_errors)}")
                continue

            entries.append({
                "semester_code": sem,
                "course_code": course,
                "ga": ga or None,
                "assessment_title": assessment,
                "status": status,
                "rubric_url": rubric_url or None,
                "notes": notes or None,
            })

    return entries, errors, warnings


def check_duplicates(entries):
    seen, warnings = set(), []
    for e in entries:
        key = (e["semester_code"], e["course_code"], e["ga"], e["assessment_title"])
        if key in seen:
            warnings.append(f"Duplicate: {e['course_code']} / {e['ga']} / '{e['assessment_title']}' in {e['semester_code']}")
        seen.add(key)
    return warnings


def build_json(entries, period_labels, source_note):
    semesters = {}
    for e in entries:
        sem = e["semester_code"]
        semesters.setdefault(sem, {"label": period_labels.get(sem, f"Semester {sem}"), "entries": []})
        entry = {
            "course_code": e["course_code"],
            "ga": e["ga"] or "",
            "assessment_title": e["assessment_title"],
            "status": e["status"],
        }
        if e["rubric_url"]:
            entry["rubric_url"] = e["rubric_url"]
        if e["notes"]:
            entry["notes"] = e["notes"]
        semesters[sem]["entries"].append(entry)

    for sem_data in semesters.values():
        sem_data["entries"].sort(key=lambda x: (x["course_code"], x["ga"] or "", x["assessment_title"]))

    return {
        "_metadata": {
            "description": "UQBS Assurance of Learning status overlay, mirrored from the AoL register",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "generated_from": source_note,
            "status_order": VALID_STATUSES,
            "statuses": {slug: meaning for slug, (_, meaning) in STATUSES.items()},
            "status_labels": {slug: label for slug, (label, _) in STATUSES.items()},
            "graduate_attributes": GA_NAMES,
        },
        "semesters": dict(sorted(semesters.items())),
    }


# --- main --------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Build the AoL overlay JSON from the CSV")
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    ap.add_argument("--periods", type=Path, default=DEFAULT_PERIODS)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--validate-only", action="store_true")
    args = ap.parse_args()

    period_labels = load_periods(args.periods)
    if not period_labels:
        print(f"  warning: no teaching periods at {args.periods}; semester labels will be bare codes")

    print(f"Reading CSV: {args.csv}")
    entries, errors, warnings = parse_csv(args.csv, period_labels)
    if errors:
        print(f"\nERRORS ({len(errors)}), nothing written:")
        for e in errors:
            print(f"  x {e}")
        sys.exit(1)
    print(f"  {len(entries)} entries parsed")

    if args.taxonomy.exists():
        known = load_taxonomy(args.taxonomy)
        for code in sorted({e["course_code"] for e in entries} - known):
            warnings.append(f"Course {code} not in taxonomy: it will not appear in programme views")
    else:
        print(f"  warning: taxonomy not found at {args.taxonomy}, skipping cross-check")

    warnings.extend(check_duplicates(entries))
    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            print(f"  ! {w}")

    if args.validate_only:
        print(f"\nValidation complete. {len(entries)} entries, {len(warnings)} warnings.")
        return

    try:
        source_note = str(args.csv.resolve().relative_to(REPO_ROOT))
    except ValueError:
        source_note = args.csv.name
    aol_json = build_json(entries, period_labels, source_note)

    targets = [args.output]
    if DOCS_OUTPUT.resolve() != args.output.resolve():
        targets.append(DOCS_OUTPUT)
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(aol_json, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"Written: {target}")

    counts = {}
    for e in entries:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    print("\nSummary:")
    print(f"  Semesters: {len(aol_json['semesters'])}")
    print(f"  Entries: {len(entries)}")
    print(f"  Courses: {len({e['course_code'] for e in entries})}")
    for slug in VALID_STATUSES:
        if counts.get(slug):
            print(f"  {STATUSES[slug][0]}: {counts[slug]}")


if __name__ == "__main__":
    main()
