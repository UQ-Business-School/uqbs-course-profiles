#!/usr/bin/env python3
"""
export_aol_register.py: read the UQBS AoL register workbook and write
taxonomy/aol-template.csv, then build the overlay with import_aol.py.

Runs on a machine that can see the register (SharePoint is not reachable from
GitHub Actions). The workbook is opened read-only and never written.

What goes to the feed (decision of 14 September 2026): course, GA, assessment,
status and rubric link. Learning designer names, coordinators, notes and folder
links stay in the workbook.

Semester per row (decision of 15 September 2026): the offering the rubric was
seen in. In order of preference:
  1. the term of the Blackboard pull that holds the linked file (--pulls dirs;
     file names are AoLPULL__CODE__GAn__S1__original name); seen in both, the
     later term wins
  2. for gradebook-note rows, the term named in the note itself (read from the
     register folder beside the workbook), else the term of the shell whose
     native rubric carries AoL-tagged rows (--native-rubrics JSON from the wide
     sweep), else the only shell the sweep saw for that course
  3. the register's own "First implemented" column
  4. --default-semester (the current semester)
Rows with nothing in the shell (Identified, TBD, N/A) fall through to 3 and 4.
Every row's source is written to logs/aol-export-report.csv.

Usage:
  python scraper/export_aol_register.py --workbook "/path/UQBS-AoL-Register.xlsx" \
      --pulls "/path/AoL_sweep_pulls" --pulls "/path/AoL_wide_pulls" \
      --native-rubrics "/path/AoL_wide_pulls/AoLPULL__wide_native_rubrics.json"
  python scraper/export_aol_register.py --workbook ... --dry-run   # report only
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

try:
    import openpyxl
except ImportError:
    sys.exit("openpyxl is required: pip install openpyxl")

REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_OUT = REPO_ROOT / "taxonomy" / "aol-template.csv"
REPORT_OUT = REPO_ROOT / "logs" / "aol-export-report.csv"
PERIODS = REPO_ROOT / "taxonomy" / "teaching-periods.json"
IMPORTER = REPO_ROOT / "scraper" / "import_aol.py"

SHEET = "AoL Register"
FIRST_ROW = 6
# 0-based column positions on the AoL Register sheet
COL_CODE, COL_GA, COL_ASSESSMENT, COL_STATUS, COL_FIRST_IMPL, COL_RUBRIC = 0, 3, 5, 6, 9, 11

HYPERLINK_RE = re.compile(r'HYPERLINK\(\s*FileBase\s*&\s*"([^"]+)"', re.I)
PULL_RE = re.compile(r"^AoLPULL__([A-Z]{4}\d{4}[A-Z]?)__GA\d__(S\d)__(.+)$")
AOL_TAG_RE = re.compile(r"\*|\bAoL\b|Assurance of Learning|AACSB", re.I)
NOTE_TERM_RE = re.compile(r"\b(?:S([12])\s*(?:20)?(\d\d)|Semester\s*([12]),?\s*20(\d\d))\b")


def note_term(register_folder, rel):
    """(term, year) named in a gradebook note, e.g. ("S2", "2026"), or None."""
    if not register_folder:
        return None
    path = register_folder / rel.replace("%20", " ")
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    m = NOTE_TERM_RE.search(text)
    if not m:
        return None
    sem = m.group(1) or m.group(3)
    yy = m.group(2) or m.group(4)
    return f"S{sem}", f"20{yy}"


def load_periods():
    with open(PERIODS, encoding="utf-8") as f:
        periods = json.load(f)["periods"]
    short_to_code = {p["short"]: code for code, p in periods.items() if p.get("short")}
    return periods, short_to_code


def read_register(path):
    """Rows of the AoL Register sheet, plus the FileBase URL."""
    wb = openpyxl.load_workbook(path, read_only=False, data_only=False)
    if SHEET not in wb.sheetnames:
        sys.exit(f"No sheet called {SHEET!r} in {path}")
    ws = wb[SHEET]

    file_base = None
    dn = wb.defined_names.get("FileBase") if hasattr(wb.defined_names, "get") else wb.defined_names["FileBase"]
    if dn is not None:
        sheet_name, ref = next(dn.destinations)
        file_base = wb[sheet_name][ref.replace("$", "")].value
    if not file_base:
        sys.exit("Could not read the FileBase named range from the Folders sheet")

    rows = []
    for r in ws.iter_rows(min_row=FIRST_ROW, values_only=True):
        code = (r[COL_CODE] or "").strip() if isinstance(r[COL_CODE], str) else r[COL_CODE]
        if not code:
            continue
        rows.append({
            "code": str(code).strip().upper(),
            "ga": (str(r[COL_GA]).strip().upper() if r[COL_GA] else ""),
            "assessment": (str(r[COL_ASSESSMENT]).strip() if r[COL_ASSESSMENT] else ""),
            "status": (str(r[COL_STATUS]).strip() if r[COL_STATUS] else ""),
            "first_impl": (str(r[COL_FIRST_IMPL]).strip() if r[COL_FIRST_IMPL] else ""),
            "rubric_cell": (str(r[COL_RUBRIC]).strip() if r[COL_RUBRIC] else ""),
        })
    return rows, file_base.rstrip("/") + "/"


def rubric_url(cell, file_base):
    """(url, relative path) from the register's HYPERLINK formula, or (None, None)."""
    m = HYPERLINK_RE.search(cell or "")
    if not m:
        return None, None
    rel = m.group(1)
    # The register stores spaces as %20 already; encode anything else that is
    # unsafe and leave existing escapes alone.
    return file_base + quote(rel, safe="/%()'&+,;=!@:-._~"), rel


def index_pulls(pull_dirs):
    """(code, lower-case original file name) -> set of terms seen."""
    idx = defaultdict(set)
    for d in pull_dirs:
        for root, _dirs, files in os.walk(d):
            for name in files:
                m = PULL_RE.match(name)
                if m:
                    idx[(m.group(1), m.group(3).lower())].add(m.group(2))
    return idx


def index_native_rubrics(path):
    """code -> (terms whose native gradebook rubrics carry AoL-tagged rows, all terms seen)."""
    tagged, seen = defaultdict(set), defaultdict(set)
    if not path:
        return tagged, seen
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for c in data.get("courses", []):
        seen[c["course"]].add(c["term"])
        for rub in c.get("rubrics", []):
            text = " ".join([rub.get("title", "")] + [row.get("header", "") for row in rub.get("rows", [])])
            if AOL_TAG_RE.search(text):
                tagged[c["course"]].add(c["term"])
                break
    return tagged, seen


def latest(terms):
    return sorted(terms)[-1]  # S1 < S2


def main():
    ap = argparse.ArgumentParser(description="Export the AoL register to taxonomy/aol-template.csv")
    ap.add_argument("--workbook", required=True, type=Path, help="UQBS-AoL-Register.xlsx (read only)")
    ap.add_argument("--pulls", action="append", default=[], type=Path,
                    help="Blackboard pull folder (AoLPULL__ files); repeatable")
    ap.add_argument("--native-rubrics", type=Path, default=None,
                    help="AoLPULL__wide_native_rubrics.json from the wide sweep")
    ap.add_argument("--register-folder", type=Path, default=None,
                    help="Folder holding the course subfolders and gradebook notes (default: beside the workbook)")
    ap.add_argument("--sweep-year", default="2026", help="Year the S1/S2 pull terms belong to")
    ap.add_argument("--default-semester", default="7660", help="Code for rows with no evidence of a term")
    ap.add_argument("--csv", type=Path, default=CSV_OUT)
    ap.add_argument("--report", type=Path, default=REPORT_OUT)
    ap.add_argument("--dry-run", action="store_true", help="Report only; write nothing, run nothing")
    ap.add_argument("--no-import", action="store_true", help="Write the CSV but do not run import_aol.py")
    args = ap.parse_args()

    periods, short_to_code = load_periods()
    if args.default_semester not in periods:
        sys.exit(f"--default-semester {args.default_semester} is not in teaching-periods.json")

    def term_code(term):  # "S2" -> "7660"
        return short_to_code.get(f"{term} {args.sweep_year}")

    rows, file_base = read_register(args.workbook)
    pulls = index_pulls(args.pulls)
    native, native_seen = index_native_rubrics(args.native_rubrics)
    register_folder = args.register_folder or args.workbook.parent
    print(f"Register: {len(rows)} rows from {args.workbook.name}")
    print(f"FileBase: {file_base}")
    if pulls:
        print(f"Pulls indexed: {len(pulls)} files across {len({k[0] for k in pulls})} courses")
    if native:
        print(f"Native gradebook rubrics with AoL tags: {len(native)} courses")

    out, report, problems = [], [], []
    for row in rows:
        url, rel = rubric_url(row["rubric_cell"], file_base)
        semester, source = None, None

        if rel:
            fname = rel.split("/", 1)[1] if "/" in rel else rel
            terms = pulls.get((row["code"], fname.replace("%20", " ").lower()))
            if terms:
                semester, source = term_code(latest(terms)), f"pull:{'+'.join(sorted(terms))}"
            elif "gradebook_rubric_note" in fname.lower():
                nt = note_term(register_folder, rel)
                if nt:
                    semester, source = short_to_code.get(f"{nt[0]} {nt[1]}"), f"note:{nt[0]} {nt[1]}"
                elif native.get(row["code"]):
                    semester, source = term_code(latest(native[row["code"]])), f"gradebook-tagged:{'+'.join(sorted(native[row['code']]))}"
                elif len(native_seen.get(row["code"], ())) == 1:
                    semester, source = term_code(latest(native_seen[row["code"]])), "gradebook-only-shell"
        if not semester and row["first_impl"]:
            code = short_to_code.get(row["first_impl"])
            if code:
                semester, source = code, "first_implemented"
            else:
                problems.append(f"{row['code']} {row['ga']}: First implemented '{row['first_impl']}' is not a known period; using default")
        if not semester:
            semester, source = args.default_semester, "default"

        if not row["status"]:
            problems.append(f"{row['code']} {row['ga']}: no status; row skipped")
            continue

        out.append({
            "semester_code": semester,
            "course_code": row["code"],
            "ga": row["ga"],
            "assessment_title": row["assessment"],
            "status": row["status"],
            "rubric_url": url or "",
            "notes": "",
        })
        report.append({**out[-1], "semester_source": source, "rubric_file": rel or "",
                       "first_implemented": row["first_impl"]})

    print(f"\nRows exported: {len(out)}")
    for status, n in sorted(Counter(r["status"] for r in out).items(), key=lambda x: -x[1]):
        print(f"  {status}: {n}")
    print("Semester source:")
    for src, n in sorted(Counter(r["semester_source"] for r in report).items(), key=lambda x: -x[1]):
        print(f"  {src}: {n}")
    print("Semester:")
    for sem, n in sorted(Counter(r["semester_code"] for r in out).items()):
        print(f"  {sem} {periods[sem]['short']}: {n}")
    if problems:
        print(f"\nProblems ({len(problems)}):")
        for p in problems:
            print(f"  ! {p}")

    if args.dry_run:
        print("\nDry run: nothing written.")
        return

    fields = ["semester_code", "course_code", "ga", "assessment_title", "status", "rubric_url", "notes"]
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with open(args.csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    print(f"\nWritten: {args.csv}")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with open(args.report, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields + ["semester_source", "rubric_file", "first_implemented"], lineterminator="\n")
        w.writeheader()
        w.writerows(report)
    print(f"Written: {args.report}")

    if not args.no_import:
        print(f"\nRunning {IMPORTER.name}")
        rc = subprocess.call([sys.executable, str(IMPORTER), "--csv", str(args.csv)])
        sys.exit(rc)


if __name__ == "__main__":
    main()
