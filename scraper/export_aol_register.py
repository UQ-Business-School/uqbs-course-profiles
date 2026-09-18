#!/usr/bin/env python3
"""
export_aol_register.py: read the UQBS AoL register workbook and write
taxonomy/aol-template.csv, then build the overlay with import_aol.py.

Two ways in:
  --workbook  a machine that can see the register (the synced SharePoint folder)
              opens it read-only and never writes it.
  --payload   the daily automatic run. A Power Automate flow runs the Office
              Script in automation/aol-register-feed.ts against the live
              register and sends the rows to GitHub as a repository_dispatch
              event; .github/workflows/aol-register.yml saves the event's
              client_payload to a file and passes it here. SharePoint is never
              reached from GitHub. --emit-payload writes the same file from a
              workbook, for testing and for a manual run of that workflow.

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
  3. data/aol-semester-evidence.csv, the terms steps 1 and 2 found for each
     course and rubric file, saved so the automatic run (which cannot see the
     pull folders or the notes) gives the same answer
  4. the register's own "First implemented" column
  5. --default-semester (the current semester; "auto" works it out from
     today's date in Brisbane: January to June is S1, July to December S2)
Rows with nothing in the shell (Identified, TBD, N/A) fall through to 4 and 5.
Every row's source is written to logs/aol-export-report.csv.

Safety: the CSV is not replaced when the new export has fewer than 80% of the
rows already in it (--min-keep), unless --allow-shrink is given. That stops a
half-saved or misread register from emptying the site overnight.

Usage:
  python scraper/export_aol_register.py --workbook "/path/UQBS-AoL-Register.xlsx" \
      --pulls "/path/AoL_sweep_pulls" --pulls "/path/AoL_wide_pulls" \
      --native-rubrics "/path/AoL_wide_pulls/AoLPULL__wide_native_rubrics.json"
  python scraper/export_aol_register.py --workbook ... --dry-run   # report only
  python scraper/export_aol_register.py --payload payload.json --default-semester auto
  python scraper/export_aol_register.py --workbook ... --emit-payload payload.json --dry-run
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_OUT = REPO_ROOT / "taxonomy" / "aol-template.csv"
REPORT_OUT = REPO_ROOT / "logs" / "aol-export-report.csv"
PERIODS = REPO_ROOT / "taxonomy" / "teaching-periods.json"
IMPORTER = REPO_ROOT / "scraper" / "import_aol.py"
EVIDENCE = REPO_ROOT / "data" / "aol-semester-evidence.csv"
EVIDENCE_FIELDS = ["course_code", "rubric_file", "semester_code", "source"]

# The shape the Office Script sends. Bump PAYLOAD_SCHEMA in both places together.
PAYLOAD_SCHEMA = 1
PAYLOAD_COLUMNS = ["course_code", "ga", "assessment", "status", "first_implemented", "rubric_file"]

SHEET = "AoL Register"
FIRST_ROW = 6
# Columns are found by their heading in row 5, the same way the Office Script
# finds them, so a column added to the register does not shift anything.
HEADINGS = {"code": "Course code", "ga": "Graduate attribute", "assessment": "Assessment",
            "status": "Status", "first_impl": "First implemented", "rubric": "Rubric"}
# Rubric links must stay on UQ's SharePoint.
FILE_BASE_PREFIX = "https://uq.sharepoint.com/"

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
    try:
        import openpyxl
    except ImportError:
        sys.exit("openpyxl is required for --workbook: pip install openpyxl")
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

    header = ["" if c.value is None else str(c.value).strip() for c in ws[FIRST_ROW - 1]]
    col = {}
    for key, name in HEADINGS.items():
        if name not in header:
            sys.exit(f"The {SHEET} sheet has no {name!r} heading in row {FIRST_ROW - 1}")
        col[key] = header.index(name)

    def cell(r, key):
        v = r[col[key]] if col[key] < len(r) else None
        return "" if v is None else str(v).strip()

    rows = []
    for r in ws.iter_rows(min_row=FIRST_ROW, values_only=True):
        code = cell(r, "code")
        if not code:
            continue
        rows.append({
            "code": code.upper(),
            "ga": cell(r, "ga").upper(),
            "assessment": cell(r, "assessment"),
            "status": cell(r, "status"),
            "first_impl": cell(r, "first_impl"),
            "rubric_rel": rubric_rel(cell(r, "rubric")),
        })
    return rows, file_base.rstrip("/") + "/"


def read_payload(path):
    """Rows and FileBase from the Office Script's payload (see module docstring)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        sys.exit(f"{path}: payload is not a JSON object")
    if data.get("schema") != PAYLOAD_SCHEMA:
        sys.exit(f"{path}: payload schema {data.get('schema')!r}, expected {PAYLOAD_SCHEMA}")
    if data.get("columns") != PAYLOAD_COLUMNS:
        sys.exit(f"{path}: payload columns {data.get('columns')!r}, expected {PAYLOAD_COLUMNS}")
    raw = data.get("rows")
    if not isinstance(raw, list):
        sys.exit(f"{path}: payload has no rows list")
    if data.get("row_count") != len(raw):
        sys.exit(f"{path}: payload says {data.get('row_count')} rows but carries {len(raw)}; refusing a truncated register")
    file_base = str(data.get("file_base") or "").strip()
    if not file_base.lower().startswith(FILE_BASE_PREFIX):
        sys.exit(f"{path}: payload file_base {file_base!r} is not on {FILE_BASE_PREFIX} (check FileBase on the register's Folders sheet)")

    rows = []
    for i, r in enumerate(raw, start=1):
        if not isinstance(r, list) or len(r) != len(PAYLOAD_COLUMNS):
            sys.exit(f"{path}: payload row {i} does not have {len(PAYLOAD_COLUMNS)} values")
        v = dict(zip(PAYLOAD_COLUMNS, ["" if x is None else str(x).strip() for x in r]))
        if not v["course_code"]:
            continue
        rows.append({
            "code": v["course_code"].upper(),
            "ga": v["ga"].upper(),
            "assessment": v["assessment"],
            "status": v["status"],
            "first_impl": v["first_implemented"],
            "rubric_rel": v["rubric_file"] or None,
        })
    return rows, file_base.rstrip("/") + "/", str(data.get("source") or path.name)


def payload_from_rows(rows, file_base, source):
    """The payload the Office Script would send for these rows (for --emit-payload)."""
    out = [[r["code"], r["ga"], r["assessment"], r["status"], r["first_impl"], r["rubric_rel"] or ""] for r in rows]
    return {"schema": PAYLOAD_SCHEMA, "source": source, "file_base": file_base.rstrip("/"),
            "columns": PAYLOAD_COLUMNS, "rows": out, "row_count": len(out)}


def rubric_rel(cell):
    """The relative file path inside the register's HYPERLINK formula, or None."""
    m = HYPERLINK_RE.search(cell or "")
    return m.group(1) if m else None


def rubric_url(rel, file_base):
    """Full SharePoint address for a relative rubric path, or None."""
    if not rel:
        return None
    # The register stores spaces as %20 already; encode anything else that is
    # unsafe and leave existing escapes alone.
    return file_base + quote(rel, safe="/%()'&+,;=!@:-._~")


def load_evidence(path):
    """(course code, lower-case rubric file) -> (semester code, source)."""
    idx = {}
    if not path or not Path(path).is_file():
        return idx
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            idx[(r["course_code"].strip().upper(), r["rubric_file"].strip().lower())] = (r["semester_code"].strip(), r["source"].strip())
    return idx


def current_semester(short_to_code, today=None):
    """Code for the semester running today in Brisbane (Jan-Jun S1, Jul-Dec S2)."""
    if today is None:
        try:
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("Australia/Brisbane")).date()
        except Exception:
            today = datetime.utcnow().date()
    short = f"{'S1' if today.month <= 6 else 'S2'} {today.year}"
    code = short_to_code.get(short)
    if not code:
        sys.exit(f"--default-semester auto: {short} is not in teaching-periods.json; add it there")
    return code


def count_csv(path):
    """(rows, rows with a rubric link) in an existing feed CSV."""
    if not path.is_file():
        return 0, 0
    rows = links = 0
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if (r.get("course_code") or "").strip():
                rows += 1
                links += bool((r.get("rubric_url") or "").strip())
    return rows, links


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
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--workbook", type=Path, help="UQBS-AoL-Register.xlsx (read only)")
    src.add_argument("--payload", type=Path, help="JSON payload from the Office Script (the automatic run)")
    ap.add_argument("--pulls", action="append", default=[], type=Path,
                    help="Blackboard pull folder (AoLPULL__ files); repeatable")
    ap.add_argument("--native-rubrics", type=Path, default=None,
                    help="AoLPULL__wide_native_rubrics.json from the wide sweep")
    ap.add_argument("--register-folder", type=Path, default=None,
                    help="Folder holding the course subfolders and gradebook notes (default: beside the workbook)")
    ap.add_argument("--sweep-year", default="2026", help="Year the S1/S2 pull terms belong to")
    ap.add_argument("--default-semester", default="auto",
                    help="Code for rows with no evidence of a term, or 'auto' for the current semester (default)")
    ap.add_argument("--evidence", type=Path, default=EVIDENCE,
                    help="Saved sweep terms per course and rubric file (default data/aol-semester-evidence.csv)")
    ap.add_argument("--write-evidence", type=Path, default=None,
                    help="Also write the terms this run found from pulls and notes to this CSV")
    ap.add_argument("--emit-payload", type=Path, default=None,
                    help="Write the payload the Office Script would send for this register")
    ap.add_argument("--min-keep", type=float, default=0.8,
                    help="Refuse to write when the export has fewer than this share of the rows already in the CSV")
    ap.add_argument("--allow-shrink", action="store_true", help="Write even when the register has shrunk past --min-keep")
    ap.add_argument("--csv", type=Path, default=CSV_OUT)
    ap.add_argument("--report", type=Path, default=REPORT_OUT)
    ap.add_argument("--dry-run", action="store_true", help="Report only; write nothing, run nothing")
    ap.add_argument("--no-import", action="store_true", help="Write the CSV but do not run import_aol.py")
    args = ap.parse_args()

    periods, short_to_code = load_periods()
    if args.default_semester == "auto":
        args.default_semester = current_semester(short_to_code)
    if args.default_semester not in periods:
        sys.exit(f"--default-semester {args.default_semester} is not in teaching-periods.json")

    def term_code(term):  # "S2" -> "7660"
        return short_to_code.get(f"{term} {args.sweep_year}")

    if args.workbook:
        rows, file_base = read_register(args.workbook)
        source_name = args.workbook.name
        register_folder = args.register_folder or args.workbook.parent
    else:
        rows, file_base, source_name = read_payload(args.payload)
        register_folder = args.register_folder
    pulls = index_pulls(args.pulls)
    native, native_seen = index_native_rubrics(args.native_rubrics)
    evidence = load_evidence(args.evidence)
    if args.payload and not evidence:
        sys.exit(f"No saved sweep evidence at {args.evidence}. The automatic run needs it to put rows in the "
                 "semester their rubric was found in; restore the file from git history.")
    print(f"Register: {len(rows)} rows from {source_name}")
    print(f"FileBase: {file_base}")
    print(f"Default semester: {args.default_semester} {periods[args.default_semester]['short']}")
    if evidence:
        print(f"Saved sweep evidence: {len(evidence)} rubric files")
    if args.emit_payload:
        args.emit_payload.parent.mkdir(parents=True, exist_ok=True)
        with open(args.emit_payload, "w", encoding="utf-8") as f:
            json.dump(payload_from_rows(rows, file_base, source_name), f, ensure_ascii=False, indent=1)
            f.write("\n")
        print(f"Payload written: {args.emit_payload}")
    if pulls:
        print(f"Pulls indexed: {len(pulls)} files across {len({k[0] for k in pulls})} courses")
    if native:
        print(f"Native gradebook rubrics with AoL tags: {len(native)} courses")

    out, report, problems = [], [], []
    for row in rows:
        rel = row["rubric_rel"]
        if rel and any(seg in ("", ".", "..") for seg in rel.replace("%2E", ".").replace("%2e", ".").split("/")):
            problems.append(f"{row['code']} {row['ga']}: rubric path {rel!r} is not a plain folder/file path; link left out")
            rel = None
        url = rubric_url(rel, file_base)
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
        if not semester and rel:
            saved = evidence.get((row["code"], rel.lower()))
            if saved and saved[0] in periods:
                semester, source = saved[0], f"evidence:{saved[1]}"
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

    rows_before, links_before = count_csv(args.csv)
    links_now = sum(1 for r in out if r["rubric_url"])
    shrunk = []
    if rows_before and len(out) < args.min_keep * rows_before:
        shrunk.append(f"the register gave {len(out)} rows and {args.csv.name} has {rows_before}")
    if links_before and links_now < args.min_keep * links_before:
        shrunk.append(f"the register has {links_now} rubric links and {args.csv.name} has {links_before} "
                      "(were the Rubric formulas pasted over?)")
    for msg in shrunk:
        print(f"\n! Below {args.min_keep:.0%} of what is published: {msg}.")

    fields = ["semester_code", "course_code", "ga", "assessment_title", "status", "rubric_url", "notes"]
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    # Write beside the real file and let import_aol.py check it first, so a bad
    # row in the register never replaces a good feed. Dry runs check too.
    staged = args.csv.with_name(args.csv.name + ".new")
    with open(staged, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    try:
        if not args.no_import:
            print(f"\nChecking the export with {IMPORTER.name} --validate-only", flush=True)
            rc = subprocess.call([sys.executable, str(IMPORTER), "--csv", str(staged), "--validate-only"])
            if rc:
                sys.exit(f"The register has rows the feed cannot take (listed above); {args.csv.name} was not replaced.")
        if args.dry_run:
            print("\nDry run: nothing written.")
            return
        if shrunk and not args.allow_shrink:
            sys.exit("Refusing to replace the feed. If the rows or links really were removed, run again with --allow-shrink.")
        os.replace(staged, args.csv)
    finally:
        if staged.exists():
            staged.unlink()
    print(f"\nWritten: {args.csv}")

    if args.write_evidence:
        # Keep what the file already knows; this run adds or updates.
        found = {}
        if args.write_evidence.is_file():
            with open(args.write_evidence, encoding="utf-8", newline="") as f:
                for r in csv.DictReader(f):
                    found[(r["course_code"], r["rubric_file"])] = {k: r[k] for k in EVIDENCE_FIELDS}
        kept = len(found)
        for r in report:
            src_ = r["semester_source"]
            if src_.split(":")[0] in ("pull", "note", "gradebook-tagged", "gradebook-only-shell") and r["rubric_file"]:
                found[(r["course_code"], r["rubric_file"])] = {"course_code": r["course_code"], "rubric_file": r["rubric_file"],
                                                              "semester_code": r["semester_code"], "source": src_}
        args.write_evidence.parent.mkdir(parents=True, exist_ok=True)
        with open(args.write_evidence, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=EVIDENCE_FIELDS, lineterminator="\n")
            w.writeheader()
            w.writerows(sorted(found.values(), key=lambda x: (x["course_code"], x["rubric_file"])))
        print(f"Written: {args.write_evidence} ({len(found)} rubric files, {kept} before this run)")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with open(args.report, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields + ["semester_source", "rubric_file", "first_implemented"], lineterminator="\n")
        w.writeheader()
        w.writerows(report)
    print(f"Written: {args.report}")

    if not args.no_import:
        print(f"\nRunning {IMPORTER.name}", flush=True)
        rc = subprocess.call([sys.executable, str(IMPORTER), "--csv", str(args.csv)])
        sys.exit(rc)


if __name__ == "__main__":
    main()
