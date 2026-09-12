#!/usr/bin/env python3
"""
Build the assessment security feed for the UQBS AoL register.

Reads the scraped profiles and writes two CSVs into docs/assets/:

  security-items.csv    one row per assessment item, for each UQBS course's
                        latest offering. This is what the register's
                        Security Feed sheet loads, so its column order is
                        a contract: add new columns at the END only.
  security-courses.csv  one row per course, the mechanical roll-up. Handy for
                        ATLAS and anything else that wants the numbers
                        without the register's LD overrides.

Definitions follow ATLAS (app/server.js) so the two never disagree:
  Secure     "Secure" in the item's conditions, the S2 2026 "Assessment
             security: Secure assessment" field, or Identity Verified.
  Grey zone  In-person, but none of the above.
  Open       everything else.

Latest offering: the most recent of the two newest semester periods that
have UQBS profiles. Within a semester, the St Lucia in-person class wins.
Other classes in that window are compared, and a difference is reported in
other_offerings so nobody mistakes one class for the whole course.

The method and AI stance columns are a first guess from the profile text.
They exist to be checked and overridden by a learning designer, not trusted.

Usage:  python scraper/build_security.py [--out docs/assets]
"""

import argparse
import csv
import glob
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Column order is the contract with the register's Security Feed sheet.
ITEM_COLUMNS = [
    "item_key", "course_code", "course_title", "offering", "semester_code",
    "class_code", "location", "attendance_mode", "profile_url", "item_no",
    "title", "category", "mode", "weight", "weight_text", "due",
    "security_class", "secure_tag", "security_field", "identity_verified",
    "in_person", "online", "hurdle", "team", "time_limited", "ai_required",
    "invigilation", "exam_platform", "method", "method_basis", "ai_stance",
    "ai_evidence", "flags", "other_offerings", "scraped_at", "built_at",
]

COURSE_COLUMNS = [
    "course_code", "course_title", "offering", "profile_url", "items",
    "total_weight", "secure_pct", "grey_pct", "open_pct",
    "largest_secure_hurdle_pct", "meets_current_rule", "meets_new_rule",
    "new_rule_pathway", "secure_methods", "secure_with_ai", "other_offerings",
]


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def low(s):
    return (s or "").lower()


def parse_weight(text):
    m = re.search(r"\d+(?:\.\d+)?", text or "")
    return float(m.group()) if m else 0.0


def norm_title(t):
    return re.sub(r"[^a-z0-9]+", " ", low(t)).strip()[:60]


def first_sentence_matching(text, pattern):
    for s in re.split(r"(?<=[.!?])\s+", text or ""):
        if re.search(pattern, s, re.I):
            s = re.sub(r"\s+", " ", s).strip()
            s = re.sub(r"^(Read full task description\s*)?(Hide full task description\s*)?", "", s)
            return s[:220]
    return ""


def short_due(due):
    due = re.sub(r"\s+", " ", due or "").strip()
    if "End of Semester Exam Period" in due:
        return "End of semester exam period"
    return due[:80]


# --------------------------------------------------------------------------
# classification
# --------------------------------------------------------------------------

def security_field(a):
    """The S2 2026 'Assessment security' field, once the scraper captures it."""
    v = a.get("assessment_security") or ""
    if re.match(r"\s*secure", v, re.I):
        return "Secure"
    if re.match(r"\s*open", v, re.I):
        return "Open"
    return ""


def indicators(a):
    return set(a.get("special_indicators") or [])


def conditions_text(a):
    return a.get("other_conditions") or ""


def classify_security(a):
    ind = indicators(a)
    field = security_field(a)
    tag = field == "Secure" or bool(re.search(r"\bSecure\b", conditions_text(a)))
    firm = tag or "Identity Verified" in ind
    if firm:
        return "Secure", tag, field
    if "In-person" in ind:
        return "Grey zone", tag, field
    return "Open", tag, field


WRITTEN_CATS = ("Reflection", "Essay", "Paper/ Report", "Portfolio",
                "Notebook", "Project", "Computer Code", "Thesis",
                "Creative", "Product/ Design", "Translation")


def classify_method(a):
    """Return (method, basis). First matching rule wins; order matters."""
    title = low(a.get("title"))
    desc = low(a.get("task_description"))[:900]
    cat = a.get("category") or ""
    mode = a.get("mode") or ""
    exam = a.get("exam_details") or ""
    due = a.get("due_date") or ""
    ind = indicators(a)
    both = title + " " + desc
    in_class = re.search(r"in[- ]class|in[- ]seminar|in[- ]tutorial|in[- ]lecture|in[- ]workshop|"
                         r"during (the )?(tutorial|seminar|workshop|lecture|class)", both)

    if "Placement" in cat or re.search(r"\binternship\b|\bplacement\b", title):
        return "Placement or internship", "category or title"

    if re.search(r"interactive oral|\bioa\b|\bviva\b|oral exam|oral interview|\binterview\b|"
                 r"defen[cs]e|oral q&a|live interactive", title):
        return "Interactive oral, viva or interview", "title"

    if "Examination" in cat:
        if "Not invigilated" in exam or ("Online" in ind and "In-person" not in ind):
            return "Online exam", "category Examination, online or not invigilated"
        if "End of Semester Exam Period" in due or "Central" in due:
            return "End-of-semester invigilated exam", "category Examination, exam period"
        return "In-semester exam", "category Examination, due in semester"

    if "Quiz" in cat or re.search(r"\bquiz|\btest\b", title):
        if in_class or "In-person" in ind:
            return "In-class quiz or test", "quiz, in class or in person"
        return "Online quiz", "quiz, not in person"

    if re.search(r"check-?ins?\b|with supervisor|progress meeting", title):
        return "Supervisor check-ins", "title"

    if re.search(r"debate|panel|roundtable|round table|forum|board discussion", title):
        return "Debate, panel or roundtable", "title"

    if "Role play" in cat or re.search(r"role ?play|simulation|stakeholder meeting|boardroom|"
                                       r"consultation|consultant briefing", title):
        return "Role play or simulation", "category or title"

    if re.search(r"hackathon|demonstration|facilitation|practical", title) or \
            (cat.startswith("Practical") and "Presentation" not in cat):
        return "Observed practical or demonstration", "category or title"

    if re.search(r"\bposter\b", title):
        return "Poster presentation", "title"

    if re.search(r"\bvideo\b|recorded", title):
        return "Recorded presentation", "title"

    if "Presentation" not in cat and not re.search(r"pitch|presentation", title) and "Oral" in mode \
            and any(w in cat for w in WRITTEN_CATS):
        return "Written task with oral component", "written category, mode includes Oral"

    if "Presentation" in cat or "Oral" in mode or re.search(r"pitch|presentation", title):
        if re.search(r"q ?& ?a|question time|questions from|followed by questions|discussion|"
                     r"respond to questions|answer questions", both):
            return "Live presentation with Q&A", "presentation, Q&A in title or description"
        if "pitch" in title:
            return "Pitch", "title"
        return "Live presentation", "category Presentation or mode Oral"

    if in_class or re.search(r"hand-?ins?|worksheet|tutorial assessment|in seminar|workshop", title):
        return "In-class task", "in class in title or description"

    if "Participation" in cat:
        return "Observed participation", "category Participation"

    if any(w in cat for w in WRITTEN_CATS) or "Tutorial/ Problem Set" in cat:
        return "Take-home written or project work", "written category"

    return "Other", "no rule matched"


AI_REQUIRED = r"\bAI Required\b|required to use (generative )?(ai|artificial)|must use (generative )?(ai|artificial)"
AI_PROHIBITED = (r"will not be permitted|not permitted|strictly prohibited|prohibited|must not use|"
                 r"not allowed|without the aid of (generative )?(ai|artificial)|no (generative )?ai (tools )?(is|are) (permitted|allowed)")
AI_PERMITTED = (r"may appropriately use|may use (generative )?(ai|artificial)|whilst students may use|"
                r"may support students|permitted to use|can use .{0,60}\bai\b|including ai|"
                r"encouraged to use (generative )?(ai|artificial)|if you (decide|choose) to use (any )?ai")


def classify_ai(a):
    """Return (stance, evidence)."""
    if re.search(r"\bAI Required\b", conditions_text(a)):
        return "Required", "AI Required condition"
    text = " ".join([a.get("ai_statement") or "", a.get("task_description") or "",
                     a.get("assessment_security") or ""])
    ai_bits = " ".join(s for s in re.split(r"(?<=[.!?])\s+", text)
                       if re.search(r"\b(AI|MT)\b|artificial intelligence|machine translation|generative", s, re.I))
    if not ai_bits:
        return "Not stated", ""
    if re.search(AI_REQUIRED, ai_bits, re.I):
        return "Required", first_sentence_matching(ai_bits, AI_REQUIRED)
    if re.search(AI_PROHIBITED, ai_bits, re.I):
        return "Prohibited", first_sentence_matching(ai_bits, AI_PROHIBITED)
    if re.search(AI_PERMITTED, ai_bits, re.I):
        return "Permitted", first_sentence_matching(ai_bits, AI_PERMITTED)
    return "Not stated", first_sentence_matching(ai_bits, r"\b(AI|MT)\b|artificial|generative")[:160]


def review_flags(a, sec_class, method):
    ind = indicators(a)
    flags = []
    if sec_class == "Secure":
        if method == "Take-home written or project work":
            flags.append("Tagged secure but reads as take-home work")
        if method == "Recorded presentation":
            flags.append("Tagged secure but recorded, not live")
        if "Online" in ind and "Identity Verified" not in ind and "In-person" not in ind:
            flags.append("Online without identity verification")
        if "Team or group-based" in ind:
            flags.append("Team task: check individual verification")
    if security_field(a) == "Open" and re.search(r"\bSecure\b", conditions_text(a)):
        flags.append("Conditions say Secure but security field says Open")
    if sec_class == "Grey zone":
        flags.append("In person but not tagged secure")
    if not re.search(r"\d", a.get("weight") or ""):
        flags.append("Weight not numeric")
    return "; ".join(flags)


# --------------------------------------------------------------------------
# offering selection
# --------------------------------------------------------------------------

def load_periods():
    with open(os.path.join(ROOT, "taxonomy", "teaching-periods.json"), encoding="utf-8") as f:
        t = json.load(f)
    t = t.get("periods", t)
    return {k: v for k, v in t.items() if not k.startswith("_")}


def is_uqbs(p):
    return "Business" in (p.get("coordinating_unit") or "")


def class_rank(p):
    """Lower is preferred: St Lucia in person first."""
    loc = low(p.get("location"))
    mode = low(p.get("attendance_mode"))
    return (0 if "st lucia" in loc else 1, 0 if "in person" in mode else 1, p.get("class_code") or "")


def secure_pct(p):
    tot = sec = 0.0
    for a in p.get("assessment_details") or []:
        w = parse_weight(a.get("weight"))
        tot += w
        if classify_security(a)[0] == "Secure":
            sec += w
    return round(sec / tot * 100) if tot else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "assets"))
    ap.add_argument("--profiles", default=os.path.join(ROOT, "profiles"))
    args = ap.parse_args()

    periods = load_periods()
    by_course = defaultdict(list)
    sem_counts = defaultdict(int)
    for sem_dir in sorted(glob.glob(os.path.join(args.profiles, "*"))):
        sem = os.path.basename(sem_dir)
        if periods.get(sem, {}).get("type") != "semester":
            continue
        for f in glob.glob(os.path.join(sem_dir, "*.json")):
            with open(f, encoding="utf-8") as fh:
                p = json.load(fh)
            if not is_uqbs(p):
                continue
            by_course[p["course_code"]].append(p)
            sem_counts[sem] += 1

    # The two newest semester periods with a real UQBS publish.
    window = sorted([s for s, n in sem_counts.items() if n >= 50], key=int)[-2:]
    built_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    items_out, courses_out = [], []
    for code in sorted(by_course):
        offers = [p for p in by_course[code] if p["semester_code"] in window]
        if not offers:
            continue
        latest_sem = max(offers, key=lambda p: int(p["semester_code"]))["semester_code"]
        chosen = sorted([p for p in offers if p["semester_code"] == latest_sem], key=class_rank)[0]
        label = periods[latest_sem]["short"]

        mine = secure_pct(chosen)
        others = []
        for p in sorted(offers, key=lambda p: (int(p["semester_code"]), class_rank(p))):
            if p is chosen:
                continue
            pct = secure_pct(p)
            if pct != mine:
                others.append(f"{periods[p['semester_code']]['short']} {p.get('location') or ''} "
                              f"{p.get('attendance_mode') or ''}: {pct}% secure".replace("  ", " "))
        other_note = "; ".join(others)

        seen = defaultdict(int)
        c_tot = c_sec = c_grey = 0.0
        hurdle_max = 0.0
        methods = []
        swa = False
        for i, a in enumerate(chosen.get("assessment_details") or [], start=1):
            sec_class, tag, field = classify_security(a)
            method, basis = classify_method(a)
            ai, ai_ev = classify_ai(a)
            ind = indicators(a)
            w = parse_weight(a.get("weight"))
            nt = norm_title(a.get("title"))
            seen[nt] += 1
            key = f"{code}|{nt}" + (f"|{seen[nt]}" if seen[nt] > 1 else "")
            exam = a.get("exam_details") or ""
            inv = re.search(r"Invigilation (.+?)(?= Exam platform| Open/closed| Planning|$)", exam)
            plat = re.search(r"Exam platform (.+?)(?= Invigilation| Open/closed| Planning|$)", exam)
            items_out.append({
                "item_key": key, "course_code": code, "course_title": chosen.get("course_title"),
                "offering": label, "semester_code": latest_sem, "class_code": chosen.get("class_code"),
                "location": chosen.get("location"), "attendance_mode": chosen.get("attendance_mode"),
                "profile_url": chosen.get("url"), "item_no": i, "title": a.get("title"),
                "category": a.get("category"), "mode": a.get("mode"), "weight": w,
                "weight_text": a.get("weight"), "due": short_due(a.get("due_date")),
                "security_class": sec_class, "secure_tag": "Yes" if tag else "No",
                "security_field": field,
                "identity_verified": "Yes" if "Identity Verified" in ind else "No",
                "in_person": "Yes" if "In-person" in ind else "No",
                "online": "Yes" if "Online" in ind else "No",
                "hurdle": "Yes" if "Hurdle" in ind else "No",
                "team": "Yes" if "Team or group-based" in ind else "No",
                "time_limited": "Yes" if "Time limited" in conditions_text(a) else "No",
                "ai_required": "Yes" if "AI Required" in conditions_text(a) else "No",
                "invigilation": inv.group(1).strip() if inv else "",
                "exam_platform": plat.group(1).strip() if plat else "",
                "method": method, "method_basis": basis, "ai_stance": ai, "ai_evidence": ai_ev,
                "flags": review_flags(a, sec_class, method), "other_offerings": other_note,
                "scraped_at": (chosen.get("scraped_at") or "")[:10], "built_at": built_at,
            })
            c_tot += w
            if sec_class == "Secure":
                c_sec += w
                methods.append(f"{method} {w:g}%")
                if "Hurdle" in ind:
                    hurdle_max = max(hurdle_max, w)
                if ai in ("Permitted", "Required"):
                    swa = True
            elif sec_class == "Grey zone":
                c_grey += w

        pct = lambda x: round(x / c_tot * 100, 1) if c_tot else 0
        s = pct(c_sec)
        any_hurdle = any("Hurdle" in indicators(a) for a in chosen.get("assessment_details") or [])
        new_path = "60% secure" if s >= 60 else ("Secure hurdle (needs approval)" if hurdle_max >= 30 else "")
        courses_out.append({
            "course_code": code, "course_title": chosen.get("course_title"), "offering": label,
            "profile_url": chosen.get("url"), "items": len(chosen.get("assessment_details") or []),
            "total_weight": c_tot, "secure_pct": s, "grey_pct": pct(c_grey),
            "open_pct": round(100 - s - pct(c_grey), 1) if c_tot else 0,
            "largest_secure_hurdle_pct": hurdle_max,
            "meets_current_rule": "Yes" if (s >= 30 or any_hurdle) else "No",
            "meets_new_rule": "Yes" if new_path else "No", "new_rule_pathway": new_path,
            "secure_methods": ", ".join(methods), "secure_with_ai": "Yes" if swa else "No",
            "other_offerings": other_note,
        })

    os.makedirs(args.out, exist_ok=True)
    for name, cols, rows in (("security-items.csv", ITEM_COLUMNS, items_out),
                             ("security-courses.csv", COURSE_COLUMNS, courses_out)):
        path = os.path.join(args.out, name)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"Wrote {len(rows)} rows to {path}")
    print("Window:", ", ".join(periods[s]["short"] for s in window))


if __name__ == "__main__":
    main()
