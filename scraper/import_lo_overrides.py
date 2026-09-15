#!/usr/bin/env python3
"""
import_lo_overrides.py — Import manual LO-to-assessment overrides from CSV
into taxonomy/lo-overrides.json (overlay loaded by the viewer at runtime).

Why this exists
---------------
UQ's Drupal-published ECP has a rendering bug: the learning-outcome-to-
assessment mapping is sometimes dropped from the HTML entirely, and sometimes
*partially* dropped (only some of the assessed LOs render). The underlying
data exists in curriculum documents but never reaches the scraped HTML, so the
scraper cannot recover it. This overlay lets the LD team hand-enter the correct
mapping for affected assessments.

Merge semantics (REPLACE per assessment)
----------------------------------------
An override row is the *authoritative full LO list* for one course + assessment.
If an override row exists for an assessment, it wins entirely; otherwise the
scraped data stands. This single rule handles both failure modes:
  - mapping missing entirely  -> override supplies the full list
  - mapping partially dropped -> override replaces the incomplete list
A correctly-rendered assessment simply gets no override row.

Safety net: because "replace" means a half-filled override could clobber LOs
that Drupal *did* render correctly, the script warns loudly if an override
omits an LO that was present in the scraped data ("override drops scraped LOx").

CSV columns (default: taxonomy/lo-overrides.csv)
  semester_code     optional — blank = applies to all semesters of the course;
                    a value = that semester only (exact-semester wins over blank)
  class_number      optional — blank = applies to all classes of the offering;
                    a value = that SI-NET class only (exact-class wins over
                    exact-semester). Needed when parallel deliveries (e.g. MBA
                    intensive vs standard, in-person vs external) share an
                    assessment title but map different LOs. A class-scoped row
                    MUST also carry a semester_code.
  course_code       e.g. BISM2207
  assessment_title  must match a scraped assessment title for that course
  learning_outcomes the authoritative LO list, e.g. "LO1, LO2, LO4"
                    (tolerant: "1,2,4", "L01,L02,L04", "LO1 LO2" all accepted)
  notes             optional free text

Usage
  python scraper/import_lo_overrides.py                 # build overlay
  python scraper/import_lo_overrides.py --validate-only # check, don't write
  python scraper/import_lo_overrides.py --scaffold      # (re)generate template
                                                        # rows from the coverage
                                                        # report's missing list
"""

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# --- paths -------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = REPO_ROOT / "taxonomy" / "lo-overrides.csv"
# Rows carry_forward_lo.py generated from the previous offering (2026-09-07). Read
# after the manual/Jac CSV; a manual row for the same assessment always wins.
CARRIED_CSV = REPO_ROOT / "taxonomy" / "lo-carried.csv"
DEFAULT_TAXONOMY = REPO_ROOT / "taxonomy" / "uqbs-programs.json"
DEFAULT_OUTPUT = REPO_ROOT / "taxonomy" / "lo-overrides.json"
DOCS_OUTPUT = REPO_ROOT / "docs" / "taxonomy" / "lo-overrides.json"
PROFILES_DIR = REPO_ROOT / "profiles"

REQUIRED_COLUMNS = {"course_code", "assessment_title", "learning_outcomes"}


# --- LO parsing (mirrors parseLoRefs in the viewer's app.js, courses repo) ------------------

_RE_LO = re.compile(r"L\.?[O0]\.?\s*(\d+)", re.IGNORECASE)
_RE_BARE = re.compile(r"(?:^|[,;\s])(\d+)(?=[,;\s]|$)")


def parse_lo_refs(s):
    """Parse a free-text LO list into an ordered list like ['LO1','LO2'].

    Tolerates 'LO1', 'L01' (zero-typo), 'L.O. 1', 'LO 1' and bare '1, 2, 3'.
    Order is first-seen; duplicates removed.
    """
    if not s:
        return []
    text = str(s)
    seen = []
    for m in _RE_LO.finditer(text):
        n = m.group(1)
        if n not in seen:
            seen.append(n)
    if not seen:
        for m in _RE_BARE.finditer(text):
            n = m.group(1)
            if n not in seen:
                seen.append(n)
    return [f"LO{n}" for n in seen]


# --- taxonomy ----------------------------------------------------------------

def load_known_courses(path):
    """Return the set of course codes referenced anywhere in the taxonomy."""
    with open(path, "r", encoding="utf-8") as f:
        tax = json.load(f)
    known = set()
    for prog in tax.get("programs", {}).values():
        for field in ["core", "flexible_core", "flexible_core_a", "flexible_core_b",
                      "program_electives", "foundational_courses", "capstone",
                      "pathway_prerequisites", "research_courses", "advanced_courses",
                      "general_pathway_courses"]:
            for code in prog.get(field, []):
                known.add(code)
        for codes in prog.get("majors", {}).values():
            for code in codes:
                known.add(code)
    return known


# --- scraped profiles --------------------------------------------------------

def _norm_title(t):
    """Loose title key for matching (case/space-insensitive)."""
    return re.sub(r"\s+", " ", str(t or "").strip()).lower()


def load_scraped_index():
    """Scan profiles/ and build a lookup of scraped assessment data.

    Returns dict:
      scraped[(course_code, semester_code)] = {
        "lo_count": int,
        "assessments": { norm_title: {"title": original, "los": [LO..]} },
        "classes": { class_code: { norm_title, ... } },
      }
    'los' is the LO list the scraper *did* capture for that assessment
    (may be empty — that is exactly the bug we're patching).
    'classes' records which SI-NET classes were scraped and which assessment
    titles each class's profile carries (for validating class-scoped rows).
    """
    index = {}
    if not PROFILES_DIR.exists():
        return index
    for sem_dir in sorted(PROFILES_DIR.iterdir()):
        if not sem_dir.is_dir():
            continue
        sem = sem_dir.name
        for jf in sorted(sem_dir.glob("*.json")):
            try:
                d = json.load(open(jf, "r", encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            course = (d.get("course_code") or "").strip().upper()
            if not course:
                continue
            key = (course, sem)
            rec = index.setdefault(key, {"lo_count": 0, "assessments": {},
                                         "classes": {}})
            rec["lo_count"] = max(rec["lo_count"], len(d.get("learning_outcomes", [])))
            cls = (d.get("class_code") or "").strip()
            cls_titles = rec["classes"].setdefault(cls, set()) if cls else None

            # LO refs the scraper captured, keyed by assessment title.
            detail_los = {}
            for it in d.get("assessment_details", []) or []:
                t = _norm_title(it.get("title"))
                if not t:
                    continue
                detail_los[t] = parse_lo_refs(it.get("learning_outcomes_assessed")
                                              or it.get("learning_outcomes"))
            for a in d.get("assessment_summary", []) or []:
                t = _norm_title(a.get("title"))
                if not t:
                    continue
                if cls_titles is not None:
                    cls_titles.add(t)
                rec["assessments"].setdefault(t, {
                    "title": (a.get("title") or "").strip(),
                    "los": detail_los.get(t, []),
                })
                # Prefer a non-empty scraped LO list if one was found in details.
                if not rec["assessments"][t]["los"] and detail_los.get(t):
                    rec["assessments"][t]["los"] = detail_los[t]
    return index


def course_semester_keys(index, course):
    """All semesters for which we have a scraped profile of this course."""
    return sorted(sem for (c, sem) in index if c == course)


# --- CSV parsing & validation ------------------------------------------------

def parse_csv(csv_path, source="jac"):
    """Parse the overrides CSV. Returns (entries, errors)."""
    entries, errors = [], []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        cols = set(reader.fieldnames or [])
        if not REQUIRED_COLUMNS.issubset(cols):
            missing = REQUIRED_COLUMNS - cols
            errors.append(f"CSV missing required columns: {', '.join(sorted(missing))}")
            return entries, errors

        for i, row in enumerate(reader, start=2):
            sem = (row.get("semester_code") or "").strip()
            cls = (row.get("class_number") or "").strip()
            course = (row.get("course_code") or "").strip().upper()
            title = (row.get("assessment_title") or "").strip()
            lo_raw = (row.get("learning_outcomes") or "").strip()
            notes = (row.get("notes") or "").strip()

            # Skip entirely blank rows.
            if not any([sem, cls, course, title, lo_raw, notes]):
                continue

            line_errors = []
            if not course:
                line_errors.append("missing course_code")
            if not title:
                line_errors.append("missing assessment_title")
            if cls and not sem:
                line_errors.append("class-scoped row must also carry a semester_code")

            los = parse_lo_refs(lo_raw)
            # A scaffold row with a blank LO column is not an error — it just
            # hasn't been filled in yet. Skip it silently (nothing to override).
            if not los:
                if line_errors:
                    errors.append(f"Row {i} ({course or '???'}): {'; '.join(line_errors)}")
                continue

            if line_errors:
                errors.append(f"Row {i} ({course or '???'}): {'; '.join(line_errors)}")
                continue

            entries.append({
                "row": i,
                "semester_code": sem,        # "" = all semesters
                "class_number": cls,         # "" = all classes
                "course_code": course,
                "assessment_title": title,
                "learning_outcomes": los,
                "notes": notes or None,
                "source": source,
            })
    return entries, errors


def merge_carried(manual, carried):
    """Carried rows fill in only where no manual/Jac row answers for that
    assessment (exact class, exact semester, or the course-wide blank row)."""
    answered = set()
    for e in manual:
        answered.add((e["course_code"], e["semester_code"], e["class_number"], _norm_title(e["assessment_title"])))
    out = list(manual)
    for e in carried:
        c, sem, cls, t = e["course_code"], e["semester_code"], e["class_number"], _norm_title(e["assessment_title"])
        if (c, sem, cls, t) in answered or (c, sem, "", t) in answered or (c, "", "", t) in answered:
            continue
        out.append(e)
    return out


def validate(entries, known_courses, scraped):
    """Cross-check entries against taxonomy and scraped data. Returns warnings."""
    warnings = []
    seen = set()
    for e in entries:
        course, sem, title = e["course_code"], e["semester_code"], e["assessment_title"]
        cls = e["class_number"]

        # Duplicate (same course+semester+class+assessment)
        dkey = (course, sem, cls, _norm_title(title))
        if dkey in seen:
            warnings.append(f"Row {e['row']}: duplicate override for "
                            f"{course} / '{title}' (semester '{sem or 'all'}', "
                            f"class '{cls or 'all'}')")
        seen.add(dkey)

        # Class-scoped row: does that class exist in the scraped profiles,
        # and does its profile carry this assessment title?
        if cls and sem:
            rec = scraped.get((course, sem))
            if rec:
                if cls not in rec.get("classes", {}):
                    warnings.append(f"Row {e['row']}: no scraped profile for "
                                    f"{course} class {cls} in semester {sem} "
                                    f"(classes on file: "
                                    f"{', '.join(sorted(rec.get('classes', {})) ) or 'none'})")
                elif _norm_title(title) not in rec["classes"][cls]:
                    warnings.append(f"Row {e['row']}: assessment '{title}' not in "
                                    f"{course} class {cls}'s scraped profile "
                                    f"({sem}) — class-scoped override would never fire")

        # Course in taxonomy?
        if known_courses is not None and course not in known_courses:
            warnings.append(f"Row {e['row']}: course '{course}' not in taxonomy "
                            f"(override still applied, but it won't show in programme views)")

        # Which scraped semesters to check against
        if sem:
            sems_to_check = [sem]
            if (course, sem) not in scraped:
                warnings.append(f"Row {e['row']}: no scraped profile for {course} "
                                f"in semester {sem} — cannot verify assessment title")
        else:
            sems_to_check = course_semester_keys(scraped, course)
            if not sems_to_check:
                warnings.append(f"Row {e['row']}: no scraped profile for {course} "
                                f"in any semester — cannot verify assessment title")

        ntitle = _norm_title(title)
        for s in sems_to_check:
            rec = scraped.get((course, s))
            if not rec:
                continue
            # Title match?
            if ntitle not in rec["assessments"]:
                cand = ", ".join(sorted(a["title"] for a in rec["assessments"].values()))
                warnings.append(f"Row {e['row']}: assessment '{title}' not found in "
                                f"{course} {s}. Scraped titles: [{cand}]")
                continue
            # LO range?
            n_lo = rec["lo_count"]
            over = [lo for lo in e["learning_outcomes"]
                    if int(lo[2:]) > n_lo and n_lo > 0]
            if over:
                warnings.append(f"Row {e['row']}: {course} {s} has {n_lo} LOs but "
                                f"override references {', '.join(over)} (out of range?)")
            # Replace-clobber safety net: override drops a scraped LO?
            scraped_los = rec["assessments"][ntitle]["los"]
            dropped = [lo for lo in scraped_los if lo not in e["learning_outcomes"]]
            if dropped:
                warnings.append(f"Row {e['row']}: override for {course} '{title}' "
                                f"OMITS {', '.join(dropped)} which the scraper DID "
                                f"capture — intended? (replace semantics will drop them)")
    return warnings


# --- build overlay -----------------------------------------------------------

def build_json(entries, source_name):
    overrides = []
    for e in entries:
        rec = {
            "course_code": e["course_code"],
            "semester_code": e["semester_code"],   # "" = all semesters
            "assessment_title": e["assessment_title"],
            "learning_outcomes": e["learning_outcomes"],
        }
        if e["class_number"]:
            rec["class_number"] = e["class_number"]  # scoped to one SI-NET class
        if e["notes"]:
            rec["notes"] = e["notes"]
        # "jac" (or manual) rows are the authored record; "carried" rows were
        # inferred from the previous offering by carry_forward_lo.py.
        rec["source"] = e.get("source") or "jac"
        overrides.append(rec)

    overrides.sort(key=lambda r: (r["course_code"], r["semester_code"],
                                  r.get("class_number", ""), r["assessment_title"]))
    n_class_scoped = sum(1 for r in overrides if r.get("class_number"))
    return {
        "_metadata": {
            "description": "LO-to-assessment mappings restored from Jac "
                           "(curriculum.uq.edu.au), the authored curriculum record. "
                           "UQ's published course profiles omit these mappings "
                           "(fully or partially) due to a publishing fault; this "
                           "overlay completes the record. Replace semantics: an "
                           "entry is the authoritative full LO list for its assessment.",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "generated_from": source_name,
            "semantics": "replace_per_assessment; exact class_number wins over "
                         "exact semester_code, which wins over blank. Entries "
                         "with class_number apply ONLY to that SI-NET class "
                         "(parallel deliveries can map differently). Consumers "
                         "that do not distinguish classes should ignore "
                         "class_number entries for offerings they cannot match.",
            "class_scoped_entries": n_class_scoped,
            "carried_entries": sum(1 for r in overrides if r.get("source") == "carried"),
        },
        "overrides": overrides,
    }


def write_json(obj):
    for out in (DEFAULT_OUTPUT, DOCS_OUTPUT):
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
        print(f"✓ Written: {out}")


# --- scaffold ----------------------------------------------------------------

def scaffold(csv_path, scraped, semester, known_courses=None):
    """(Re)generate template rows for courses with missing/partial LO mappings
    in the given semester. Preserves any already-filled rows in the CSV.

    If known_courses is provided, only those courses are scaffolded (keeps the
    worklist focused on UQBS-owned courses).
    """
    # Read existing filled rows to preserve them.
    existing = {}
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                key = ((row.get("semester_code") or "").strip(),
                       (row.get("course_code") or "").strip().upper(),
                       _norm_title(row.get("assessment_title")))
                existing[key] = row

    rows = []
    for (course, sem), rec in sorted(scraped.items()):
        if semester and sem != semester:
            continue
        if known_courses is not None and course not in known_courses:
            continue
        # Flag courses where at least one assessment has no scraped LOs.
        if not any(not a["los"] for a in rec["assessments"].values()):
            continue
        for a in sorted(rec["assessments"].values(), key=lambda x: x["title"]):
            key = (sem, course, _norm_title(a["title"]))
            prev = existing.get(key)
            rows.append({
                "semester_code": sem,
                "class_number": (prev or {}).get("class_number", "").strip(),
                "course_code": course,
                "assessment_title": a["title"],
                "learning_outcomes": (prev or {}).get("learning_outcomes", "").strip(),
                "notes": (prev or {}).get("notes", "").strip(),
            })

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["semester_code", "class_number",
                                          "course_code",
                                          "assessment_title", "learning_outcomes",
                                          "notes"])
        w.writeheader()
        w.writerows(rows)
    n_courses = len({(r["course_code"], r["semester_code"]) for r in rows})
    print(f"✓ Scaffolded {len(rows)} rows across {n_courses} course offerings "
          f"-> {csv_path}")


# --- main --------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Import LO-to-assessment overrides")
    p.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    p.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    p.add_argument("--validate-only", action="store_true")
    p.add_argument("--scaffold", action="store_true",
                   help="Regenerate template rows for courses missing LO mappings")
    p.add_argument("--semester", default="7620",
                   help="Semester filter for --scaffold (default 7620)")
    p.add_argument("--uqbs-only", action="store_true",
                   help="When scaffolding, restrict to courses in the taxonomy")
    args = p.parse_args()

    print("Indexing scraped profiles...")
    scraped = load_scraped_index()
    print(f"  → {len(scraped)} course-semester profiles indexed")

    if args.scaffold:
        known = load_known_courses(args.taxonomy) if args.taxonomy.exists() else None
        scaffold(args.csv, scraped, args.semester,
                 known if args.uqbs_only else None)
        return

    print(f"Reading CSV: {args.csv}")
    if not args.csv.exists():
        print(f"  ⚠ {args.csv} does not exist. Run with --scaffold to create it.")
        sys.exit(1)

    entries, errors = parse_csv(args.csv)
    if CARRIED_CSV.exists():
        carried, cerrors = parse_csv(CARRIED_CSV, source="carried")
        errors += cerrors
        before = len(entries)
        entries = merge_carried(entries, carried)
        print(f"  → {len(entries) - before} carried rows from {CARRIED_CSV.name} "
              f"({len(carried) - (len(entries) - before)} superseded by a manual or Jac row)")
    if errors:
        print(f"\n{'='*60}\nERRORS ({len(errors)}) — must fix before import:")
        for e in errors:
            print(f"  ✗ {e}")
        print('='*60)
        sys.exit(1)
    print(f"  → {len(entries)} filled override rows")

    known = load_known_courses(args.taxonomy) if args.taxonomy.exists() else None
    if known is None:
        print(f"  ⚠ Taxonomy not found at {args.taxonomy} — skipping course cross-check")

    warnings = validate(entries, known, scraped)
    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            print(f"  ⚠ {w}")

    if args.validate_only:
        print(f"\n✓ Validation complete. {len(entries)} overrides, "
              f"{len(warnings)} warnings.")
        return

    obj = build_json(entries, args.csv.name)
    write_json(obj)

    print("\nSummary:")
    print(f"  Overrides: {len(entries)}")
    print(f"  Courses:   {len(set(e['course_code'] for e in entries))}")
    sem_specific = sum(1 for e in entries if e["semester_code"])
    cls_specific = sum(1 for e in entries if e["class_number"])
    print(f"  Semester-specific: {sem_specific}; all-semesters: {len(entries)-sem_specific}")
    print(f"  Class-scoped: {cls_specific}")


if __name__ == "__main__":
    main()
