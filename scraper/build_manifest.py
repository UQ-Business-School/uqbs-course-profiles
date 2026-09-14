#!/usr/bin/env python3
"""Build lean manifests of scraped course profiles.

Scans profiles/{semester_code}/*.json and writes:
  docs/assets/manifest.json      — UQBS courses only (filtered by taxonomy)
  docs/assets/manifest-all.json  — all courses (entire profiles/ directory)

The UQBS manifest powers the live viewer at uq-business-school.github.io and is never
affected by all-of-UQ scrapes. The full manifest is consumed by ATLAS and
other downstream tools that need the complete dataset.

Usage:
  python scraper/build_manifest.py

Exit code is non-zero if profiles/ is empty or no semesters found.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILES_DIR = REPO_ROOT / "profiles"
LEGACY_DIR = REPO_ROOT / "profiles-legacy"
DOCS_DIR = REPO_ROOT / "docs"
MANIFEST_PATH = DOCS_DIR / "assets" / "manifest.json"
MANIFEST_ALL_PATH = DOCS_DIR / "assets" / "manifest-all.json"
MANIFEST_LEGACY_PATH = DOCS_DIR / "assets" / "manifest-legacy.json"
TAXONOMY_PATH = REPO_ROOT / "taxonomy" / "uqbs-programs.json"


def _summary_fields(data: dict, relative_path: str) -> dict:
    """Pick the lean summary fields for the browser table."""
    return {
        "course_code": data.get("course_code"),
        "class_code": data.get("class_code"),
        "semester_code": data.get("semester_code"),
        "full_course_code": data.get("full_course_code"),
        "course_title": data.get("course_title"),
        "study_period": data.get("study_period"),
        "study_level": data.get("study_level"),
        "location": data.get("location"),
        "attendance_mode": data.get("attendance_mode"),
        "units": data.get("units"),
        "coordinating_unit": data.get("coordinating_unit"),
        "url": data.get("url"),
        "scraped_at": data.get("scraped_at"),
        "assessment_count": len(data.get("assessment_summary") or []),
        "lo_count": len(data.get("learning_outcomes") or []),
        "file": relative_path,
    }


def _legacy_summary_fields(data: dict, relative_path: str) -> dict:
    """Lean summary fields for a legacy profile (no class/semester code).

    Adds year/period so the per-course timeline can order legacy offerings
    chronologically, and a `system` marker so the viewer can badge them.
    """
    base = _summary_fields(data, relative_path)
    base.update({
        "system": "legacy",
        "legacy_id": data.get("legacy_id"),
        "year": data.get("year"),
        "period": data.get("period"),
    })
    return base


def _period_key(period: str | None) -> str:
    return {"Semester 1": "S1", "Semester 2": "S2", "Summer Semester": "SS"}.get(period or "", "X")


def _scan_legacy_profiles() -> list[tuple[str, dict]]:
    """Scan profiles-legacy/{year}-{period}/ → (relative_path, summary) pairs."""
    if not LEGACY_DIR.exists():
        return []
    entries = []
    for period_dir in sorted(LEGACY_DIR.iterdir()):
        if not period_dir.is_dir():
            continue
        for jf in sorted(period_dir.glob("*.json")):
            try:
                with jf.open() as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                print(f"warn: skipping {jf.name}: {exc}", file=sys.stderr)
                continue
            rel = f"profiles-legacy/{period_dir.name}/{jf.name}"
            entries.append((rel, _legacy_summary_fields(data, rel)))
    return entries


def _build_legacy_manifest(entries: list[tuple[str, dict]]) -> dict:
    """Group legacy entries by '{year}-{period_key}' buckets (no semester codes)."""
    buckets: dict[str, list] = {}
    for _rel, summary in entries:
        key = f"{summary.get('year') or 'unknown'}-{_period_key(summary.get('period'))}"
        buckets.setdefault(key, []).append(summary)
    total = sum(len(v) for v in buckets.values())
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_profiles": total,
        "system": "legacy",
        "periods": dict(sorted(buckets.items())),
    }


def _load_uqbs_course_codes() -> set[str] | None:
    """Load UQBS course codes from taxonomy. Returns None if file missing."""
    if not TAXONOMY_PATH.exists():
        print(
            f"warn: taxonomy not found at {TAXONOMY_PATH}; "
            "UQBS-filtered manifest will include all courses",
            file=sys.stderr,
        )
        return None
    with open(TAXONOMY_PATH, encoding="utf-8") as f:
        taxonomy = json.load(f)
    return set(taxonomy.get("course_programs", {}).keys())


def _scan_all_profiles() -> list[tuple[str, dict]]:
    """Scan profiles/ and return (relative_path, summary_fields) pairs."""
    if not PROFILES_DIR.exists():
        raise SystemExit(f"profiles directory not found: {PROFILES_DIR}")

    all_entries = []
    for semester_dir in sorted(PROFILES_DIR.iterdir()):
        if not semester_dir.is_dir():
            continue
        sem_code = semester_dir.name
        for jf in sorted(semester_dir.glob("*.json")):
            try:
                with jf.open() as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                print(f"warn: skipping {jf.name}: {exc}", file=sys.stderr)
                continue
            rel = f"profiles/{sem_code}/{jf.name}"
            all_entries.append((rel, _summary_fields(data, rel)))
    return all_entries


def _build_manifest(entries: list[tuple[str, dict]]) -> dict:
    """Group entries by semester and build the manifest dict."""
    semesters: dict[str, list] = {}
    for _rel, summary in entries:
        sem = summary.get("semester_code") or "unknown"
        semesters.setdefault(sem, []).append(summary)
    total = sum(len(v) for v in semesters.values())
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_profiles": total,
        "semesters": semesters,
    }


def _write_manifest(manifest: dict, path: Path, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(manifest, f, indent=2)
    print(
        f"Wrote {path.relative_to(REPO_ROOT)} "
        f"({manifest['total_profiles']} {label} profiles across "
        f"{len(manifest['semesters'])} semester(s))"
    )


def main() -> None:
    # Scan all profiles once
    all_entries = _scan_all_profiles()

    # Build and write the full manifest (all-of-UQ)
    full_manifest = _build_manifest(all_entries)
    _write_manifest(full_manifest, MANIFEST_ALL_PATH, "all-of-UQ")

    # Build and write the UQBS-filtered manifest
    uqbs_codes = _load_uqbs_course_codes()
    if uqbs_codes is not None:
        uqbs_entries = [
            (rel, s) for rel, s in all_entries
            if s.get("course_code") in uqbs_codes
        ]
    else:
        uqbs_entries = all_entries  # fallback: include everything

    uqbs_manifest = _build_manifest(uqbs_entries)
    _write_manifest(uqbs_manifest, MANIFEST_PATH, "UQBS")

    # Build and write the legacy manifest (2009–S1 2024), kept entirely
    # separate from the live UQBS/all manifests so the current viewer is
    # unaffected. The viewer loads it opt-in for the per-course timeline.
    legacy_entries = _scan_legacy_profiles()
    if legacy_entries:
        legacy_manifest = _build_legacy_manifest(legacy_entries)
        MANIFEST_LEGACY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with MANIFEST_LEGACY_PATH.open("w") as f:
            json.dump(legacy_manifest, f, indent=2)
        print(
            f"Wrote {MANIFEST_LEGACY_PATH.relative_to(REPO_ROOT)} "
            f"({legacy_manifest['total_profiles']} legacy profiles across "
            f"{len(legacy_manifest['periods'])} period(s))"
        )
    else:
        print("No profiles-legacy/ found — skipping legacy manifest")


if __name__ == "__main__":
    main()
