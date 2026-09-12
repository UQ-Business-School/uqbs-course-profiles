#!/usr/bin/env python3
"""
UQBS Course Profile Scraper
Enriched scraper for UQ Business School course profiles.
Captures a comprehensive field set from course-profiles.uq.edu.au and
programs-courses.uq.edu.au for use in learning design, GA mapping,
and AoL reporting.

Based on the JacSON architecture by Geoff (uq-course-profiles/jacson).
Extended by Sean Smith, Learning Designer, UQ Business School.
"""

import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup, NavigableString

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT}

COURSE_PROFILES_BASE = "https://course-profiles.uq.edu.au"

# JacSON GitHub repo — used to discover profile URLs (class codes + semesters)
JACSON_REPO_OWNER = "uq-course-profiles"
JACSON_REPO_NAME = "jacson"
GITHUB_TREE_API = "https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"

DEFAULT_REQUEST_DELAY = 1.0  # seconds between requests (be polite to UQ servers)
REQUEST_DELAY = DEFAULT_REQUEST_DELAY
REQUEST_TIMEOUT = 30  # seconds

# Resolve paths relative to this script's location
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
TAXONOMY_PATH = PROJECT_ROOT / "taxonomy" / "uqbs-programs.json"
PROFILES_DIR = PROJECT_ROOT / "profiles"

# Logging
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            LOG_DIR / f"scrape_{datetime.now().strftime('%Y-%m-%d')}.log",
            encoding="utf-8",
        ),
    ],
)
log = logging.getLogger("uqbs-scraper")


# ---------------------------------------------------------------------------
# Course list
# ---------------------------------------------------------------------------

def load_course_list() -> list[str]:
    """Load UQBS course codes from the taxonomy JSON."""
    if not TAXONOMY_PATH.exists():
        log.error(f"Taxonomy file not found: {TAXONOMY_PATH}")
        sys.exit(1)

    with open(TAXONOMY_PATH, encoding="utf-8") as f:
        taxonomy = json.load(f)

    courses = sorted(taxonomy.get("course_programs", {}).keys())
    log.info(f"Loaded {len(courses)} UQBS courses from taxonomy")
    return courses


def load_all_uq_course_list(semester_filter: str | None = None) -> list[str]:
    """Load all UQ course codes from the JacSON GitHub repo index.

    When semester_filter is given, only returns courses that have profiles
    in that semester (avoids scraping courses that don't exist for a given
    semester).
    """
    index = _fetch_repo_index()
    if semester_filter:
        courses = sorted(
            code for code, entries in index.items()
            if any(e["semester"] == semester_filter for e in entries)
        )
        log.info(
            f"Loaded {len(courses)} all-of-UQ courses from JacSON index "
            f"(filtered to semester {semester_filter})"
        )
    else:
        courses = sorted(index.keys())
        log.info(f"Loaded {len(courses)} all-of-UQ courses from JacSON index")
    return courses


# ---------------------------------------------------------------------------
# Discovery: find profile URLs via JacSON GitHub repo
# ---------------------------------------------------------------------------

# Module-level cache for the repo file index (fetched once per run)
_repo_index_cache: dict | None = None

# Hardening (2026-08-25): a failed or truncated index fetch used to be cached
# as an empty index, so the run carried on, found nothing, and exited 0. That
# is now an error unless --allow-empty-index is passed (debugging only).
ALLOW_EMPTY_INDEX = False


class RepoIndexError(RuntimeError):
    """The JacSON repo index could not be fetched completely."""


def _github_headers() -> dict[str, str]:
    """Request headers for api.github.com, with a bearer token if one is set.

    Unauthenticated calls from a shared GitHub Actions runner share a small
    rate limit and fail intermittently. GITHUB_TOKEN (or GH_TOKEN) in the
    environment lifts that; the workflow passes secrets.GITHUB_TOKEN.
    """
    headers = dict(HEADERS)
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch_repo_index() -> dict[str, list[dict]]:
    """
    Fetch the JacSON GitHub repo tree to build an index of available
    course profiles, keyed by course code.

    Returns e.g.:
      {
        "MGTS1601": [
          {"full_code": "MGTS1601-20353-7620", "semester": "7620",
           "path": "profiles/7620/MGTS1601-20353-7620.json"},
          ...
        ],
        ...
      }
    """
    global _repo_index_cache
    if _repo_index_cache is not None:
        return _repo_index_cache

    url = GITHUB_TREE_API.format(
        owner=JACSON_REPO_OWNER, repo=JACSON_REPO_NAME, branch="main"
    )
    headers = _github_headers()
    log.info(
        "Fetching JacSON repo index from GitHub Tree API "
        f"({'authenticated' if 'Authorization' in headers else 'unauthenticated'})..."
    )

    def _fail(msg: str) -> dict[str, list[dict]]:
        global _repo_index_cache
        if ALLOW_EMPTY_INDEX:
            log.error(f"{msg} (--allow-empty-index set; continuing with an empty index)")
            _repo_index_cache = {}
            return _repo_index_cache
        log.error(f"{msg} Nothing can be discovered without the index; stopping.")
        raise RepoIndexError(msg)

    try:
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        return _fail(f"Failed to fetch JacSON repo index: {e}.")

    if data.get("truncated"):
        return _fail(
            "JacSON repo index is truncated: the GitHub Tree API returned "
            "truncated=true, so the listing is incomplete."
        )

    tree = data.get("tree", [])

    index: dict[str, list[dict]] = {}

    # Pattern: profiles/{semester}/{COURSE-CLASS-SEM}.json
    pattern = re.compile(
        r"^profiles/(\d{4})/([A-Z]{4}\d{4})-(\d+)-(\d{4})\.json$"
    )

    for item in tree:
        if item.get("type") != "blob":
            continue
        match = pattern.match(item["path"])
        if not match:
            continue

        semester = match.group(1)
        course_code = match.group(2)
        class_code = match.group(3)
        sem_code = match.group(4)
        full_code = f"{course_code}-{class_code}-{sem_code}"

        if course_code not in index:
            index[course_code] = []
        index[course_code].append({
            "full_code": full_code,
            "semester": semester,
            "class_code": class_code,
            "path": item["path"],
            "url": f"{COURSE_PROFILES_BASE}/course-profiles/{full_code}",
        })

    log.info(
        f"Indexed {sum(len(v) for v in index.values())} profiles "
        f"across {len(index)} courses from JacSON repo"
    )
    _repo_index_cache = index
    return index


def discover_profile_urls(
    course_code: str, semester_filter: str | None = None
) -> list[dict]:
    """
    Look up available profile URLs for a course code from the JacSON
    GitHub repo index.

    Returns list of dicts with: url, full_code, semester, class_code, path
    """
    index = _fetch_repo_index()
    entries = index.get(course_code, [])

    if semester_filter:
        entries = [e for e in entries if e["semester"] == semester_filter]

    return entries


# ---------------------------------------------------------------------------
# Profile scraping: extract everything from a course profile page
# ---------------------------------------------------------------------------

def scrape_profile(url: str) -> dict | None:
    """
    Scrape a single course profile page and return enriched data.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning(f"  Failed to fetch profile {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    profile = {"url": url, "scraped_at": datetime.now(timezone.utc).isoformat()}

    # --- Breadcrumb: extract full course code ---
    _extract_course_codes(soup, profile)

    # --- Course overview section ---
    _extract_overview(soup, profile)

    # --- Course description (the paragraphs after the summary table) ---
    _extract_course_description(soup, profile)

    # --- Course requirements (prerequisites, incompatibles) ---
    _extract_requirements(soup, profile)

    # --- Course contacts ---
    _extract_contacts(soup, profile)

    # --- Course staff ---
    _extract_staff(soup, profile)

    # --- Timetable ---
    _extract_timetable(soup, profile)

    # --- Aims and outcomes ---
    _extract_aims(soup, profile)

    # --- Learning outcomes ---
    _extract_learning_outcomes(soup, profile)

    # --- Assessment (summary table + detailed items) ---
    _extract_assessment(soup, profile)

    # --- Learning resources ---
    _extract_learning_resources(soup, profile)

    # --- Learning activities ---
    _extract_learning_activities(soup, profile)

    # --- Policies and procedures ---
    _extract_policies(soup, profile)

    return profile


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def _extract_course_codes(soup: BeautifulSoup, profile: dict):
    """Extract course code components from breadcrumb."""
    breadcrumb_links = soup.select("a[href*='/course-profiles/']")
    for link in breadcrumb_links:
        href = link.get("href", "")
        match = re.search(r"/course-profiles/([A-Z]{4}\d{4})-(\d+)-(\d{4})", href)
        if match:
            profile["course_code"] = match.group(1)
            profile["class_code"] = match.group(2)
            profile["semester_code"] = match.group(3)
            profile["full_course_code"] = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
            return

    # Fallback: try to extract from URL
    match = re.search(r"/course-profiles/([A-Z]{4}\d{4})-(\d+)-(\d{4})", profile.get("url", ""))
    if match:
        profile["course_code"] = match.group(1)
        profile["class_code"] = match.group(2)
        profile["semester_code"] = match.group(3)
        profile["full_course_code"] = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"


def _extract_overview(soup: BeautifulSoup, profile: dict):
    """Extract the summary table from course overview."""
    overview = soup.find(id="course-overview--section") or soup.find(id="course-overview")
    if not overview:
        return

    # Page heading / course title
    h1 = soup.find("h1")
    if h1:
        title_text = h1.get_text(separator=" ", strip=True)
        # Remove trailing semester info in parentheses if present
        title_text = re.sub(r"\s*\([^)]*\)\s*$", "", title_text)
        profile["course_title"] = title_text

    # Summary table fields
    field_map = {
        "Study period": "study_period",
        "Study level": "study_level",
        "Location": "location",
        "Attendance mode": "attendance_mode",
        "Units": "units",
        "Administrative campus": "administrative_campus",
        "Coordinating unit": "coordinating_unit",
    }

    for dt_tag in overview.find_all("dt"):
        label = dt_tag.get_text(separator=" ", strip=True)
        if label in field_map:
            dd_tag = dt_tag.find_next_sibling("dd")
            if dd_tag:
                profile[field_map[label]] = dd_tag.get_text(separator=" ", strip=True)


def _extract_course_description(soup: BeautifulSoup, profile: dict):
    """Extract the course description paragraphs from the overview section."""
    section = soup.find(id="course-overview--section")
    if not section:
        return

    # Find the summary table, then collect all paragraphs/divs after it
    summary_table = section.find(class_="highlight")
    if not summary_table:
        return

    description_parts = []
    sibling = summary_table.find_next_sibling()
    while sibling:
        if sibling.name in ("p", "div"):
            # Skip if it's a nested section or contains only whitespace
            text = sibling.get_text(separator=" ", strip=True)
            if text and len(text) > 10:
                description_parts.append(text)
        elif sibling.name in ("h2", "section"):
            break
        sibling = sibling.find_next_sibling()

    if description_parts:
        profile["course_description"] = "\n\n".join(description_parts)


def _extract_requirements(soup: BeautifulSoup, profile: dict):
    """Extract prerequisites, incompatibles, companions from Course requirements section."""
    section = soup.find(id="course-requirements")
    if not section:
        return

    requirements = {}
    current_label = None

    for child in section.descendants:
        if isinstance(child, NavigableString):
            continue
        text = child.get_text(separator=" ", strip=True)

        # Look for requirement type labels
        if child.name in ("h3", "h4", "strong"):
            lower = text.lower()
            if "prerequisite" in lower:
                current_label = "prerequisites"
            elif "incompatible" in lower:
                current_label = "incompatible"
            elif "companion" in lower:
                current_label = "companions"
            elif "restriction" in lower:
                current_label = "restrictions"
        elif current_label and child.name in ("p", "dd", "li", "span"):
            if text and text != current_label.title():
                if current_label not in requirements:
                    requirements[current_label] = []
                # Extract course codes
                codes = re.findall(r"[A-Z]{4}\d{4}", text)
                if codes:
                    requirements[current_label].extend(codes)
                elif text not in requirements.get(current_label, []):
                    requirements[current_label].append(text)

    # Deduplicate
    for key in requirements:
        requirements[key] = list(dict.fromkeys(requirements[key]))

    # Also try a simpler extraction as fallback
    if not requirements:
        full_text = section.get_text(separator=" ", strip=True)
        if "Incompatible" in full_text:
            codes = re.findall(r"[A-Z]{4}\d{4}", full_text)
            if codes:
                requirements["incompatible"] = list(dict.fromkeys(codes))

    if requirements:
        profile["requirements"] = requirements


def _extract_contacts(soup: BeautifulSoup, profile: dict):
    """Extract course contacts."""
    section = soup.find(id="course-contact")
    if not section:
        return

    contacts = []
    seen = set()

    for card in section.select(".contact-card, article"):
        contact = {}

        role_el = card.select_one(".contact-card__role-heading, h3")
        if role_el:
            contact["role"] = role_el.get_text(separator=" ", strip=True)

        name_el = card.select_one(".contact-card__name, .contact-card__details")
        if name_el:
            contact["name"] = name_el.get_text(separator=" ", strip=True)

        email_el = card.select_one(".contact-card__email a, a[href^='mailto:']")
        if email_el:
            contact["email"] = email_el.get_text(separator=" ", strip=True)

        phone_el = card.select_one(".contact-card__phone a, a[href^='tel:']")
        if phone_el:
            contact["phone"] = phone_el.get_text(separator=" ", strip=True)

        notes_el = card.select_one(".contact-card__notes")
        if notes_el:
            contact["notes"] = notes_el.get_text(separator=" ", strip=True)

        # Deduplicate
        key = (contact.get("role", ""), contact.get("name", ""), contact.get("email", ""))
        if key not in seen and any(contact.values()):
            seen.add(key)
            contacts.append(contact)

    if contacts:
        profile["course_contacts"] = contacts


def _extract_staff(soup: BeautifulSoup, profile: dict):
    """Extract course staff section (separate from contacts).

    The staff section layout has one or more role groups inside a
    single .staff-cards wrapper:
      <div class="staff-cards">
        <h3 class="staff-cards__role">Lecturer</h3>
        <div class="staff-cards__cards">
          <article class="contact-card">...</article>
        </div>
        <h3 class="staff-cards__role">Course facilitator</h3>
        <div class="staff-cards__cards">
          <article class="contact-card">...</article>
        </div>
      </div>
    Each <h3> applies to the .staff-cards__cards div that follows it.
    """
    section = soup.find(id="course-staff")
    if not section:
        return

    staff = []
    seen = set()

    # Walk each role heading within the staff section.
    # The cards for that role are in the next sibling
    # .staff-cards__cards div.
    for role_heading in section.select("h3.staff-cards__role"):
        role = role_heading.get_text(separator=" ", strip=True)

        # Find the next .staff-cards__cards sibling
        cards_div = role_heading.find_next_sibling(
            "div", class_="staff-cards__cards"
        )
        if not cards_div:
            continue

        for card in cards_div.select("article.contact-card"):
            person = {}
            if role:
                person["role"] = role
            name_el = card.select_one(".contact-card__name")
            if name_el:
                person["name"] = name_el.get_text(separator=" ", strip=True)
            email_el = card.select_one("a[href^='mailto:']")
            if email_el:
                person["email"] = email_el.get_text(separator=" ", strip=True)

            # Deduplicate by name + role (same person can have
            # different roles, e.g. Lecturer AND Course facilitator)
            key = (person.get("name", ""), person.get("role", ""))
            if key not in seen and any(person.values()):
                seen.add(key)
                staff.append(person)

    if staff:
        profile["course_staff"] = staff


def _extract_timetable(soup: BeautifulSoup, profile: dict):
    """Extract timetable information."""
    section = soup.find(id="timetable")
    if not section:
        return

    timetable_text = section.get_text(separator="\n", strip=True)
    # Remove the heading
    timetable_text = re.sub(r"^Timetable\s*", "", timetable_text).strip()

    if timetable_text:
        profile["timetable"] = timetable_text


def _extract_aims(soup: BeautifulSoup, profile: dict):
    """Extract the course aims statement.

    The aims text can appear in two forms:
      - Wrapped in <p> or <div> tags (e.g. MGTS1601)
      - As bare text nodes directly inside the <section> (e.g. ACCT1101
        where the server HTML has: <p></p>Text content here.)
    Both forms appear before the learning outcomes <section>.
    """
    section = soup.find(id="aim-and-outcomes--section")
    if not section:
        # Try just aim-and-outcomes
        section = soup.find(id="aim-and-outcomes")
    if not section:
        return

    # Collect aims text from children before the learning outcomes section.
    aims_parts = []
    for child in section.children:
        if child.name == "section":
            # Hit the learning outcomes sub-section, stop
            break

        # Bare text nodes (NavigableString) — some pages put the aims
        # text directly in the section without wrapping tags.
        if isinstance(child, NavigableString):
            text = child.strip()
            if text and len(text) > 10:
                aims_parts.append(text)
            continue

        # Skip headings
        if child.name in ("h2", "h3"):
            continue

        if child.name in ("p", "div"):
            text = child.get_text(separator=" ", strip=True)
            if text and text.lower() != "aims and outcomes" and len(text) > 10:
                aims_parts.append(text)

    if aims_parts:
        profile["course_aims"] = "\n\n".join(aims_parts)


def _extract_learning_outcomes(soup: BeautifulSoup, profile: dict):
    """Extract learning outcomes with number and description.

    The page structure varies between server-sent HTML and browser-rendered
    DOM.  Two known layouts:

      Layout A (server raw HTML — what requests.get() receives):
        <p><strong>LO1.</strong> Description text here.</p>
        <p><strong>LO2.</strong> Description text here.</p>
        i.e. the LO number and description are in the SAME <p>.

      Layout B (browser-rendered DOM after JS):
        <p><strong>LO1.</strong> </p>
        <p>Description text here.</p>
        <p></p>
        i.e. the LO number and description are in SEPARATE <p> tags.

    Strategy 1 handles both by checking the same <p> first, then falling
    back to sibling walking.
    """
    section = soup.find(id="learning-outcomes")
    if not section:
        return

    outcomes = []

    # Strategy 1: Find all <strong> tags that look like LO numbers.
    lo_strongs = section.find_all(
        "strong", string=re.compile(r"^LO\d+\.?$")
    )

    if lo_strongs:
        for strong in lo_strongs:
            number = strong.get_text(separator=" ", strip=True)
            description = ""
            parent_p = strong.find_parent("p")

            # --- Try same-<p> extraction first (Layout A) ---
            # If the <p> contains both the <strong> and description text,
            # strip the LO number prefix to get the description.
            if parent_p:
                full_text = parent_p.get_text(separator=" ", strip=True)
                same_p_desc = re.sub(r"^LO\d+\.?\s*", "", full_text).strip()
                if same_p_desc:
                    description = same_p_desc

            # --- Fall back to sibling walk (Layout B) ---
            # If the same <p> only contained the LO number, look for
            # the description in the next non-empty sibling <p>.
            if not description and parent_p:
                sibling = parent_p.find_next_sibling()
                while sibling:
                    if sibling.name == "p":
                        text = sibling.get_text(separator=" ", strip=True)
                        # Skip empty paragraphs and LO-number-only paragraphs
                        if text and not re.match(r"^LO\d+\.?\s*$", text):
                            description = text
                            break
                    sibling = sibling.find_next_sibling()

            # Safety: strip any stray leading LO prefix from the description
            # (handles edge cases where text starts with "LO2.Apply...")
            if description:
                description = re.sub(r"^LO\d+\.?\s*", "", description).strip()

            if description:
                outcomes.append({"number": number, "description": description})

    # Strategy 2: Regex fallback on full section text
    if not outcomes:
        text = section.get_text()
        lo_matches = re.findall(
            r"(LO\d+\.?)\s*(.+?)(?=LO\d+\.|$)", text, re.DOTALL
        )
        for num, desc in lo_matches:
            desc_clean = desc.strip()
            if desc_clean:
                outcomes.append({"number": num.strip(), "description": desc_clean})

    if outcomes:
        profile["learning_outcomes"] = outcomes


def _extract_assessment(soup: BeautifulSoup, profile: dict):
    """Extract assessment summary and detailed items."""
    section = soup.find(id="assessment")
    if not section:
        return

    # --- Assessment summary table ---
    # Use only the FIRST direct/top-level table in the assessment section.
    # Detail sections may contain their own nested tables (e.g. marking
    # criteria) which we don't want in the summary.
    summary = []
    summary_table = None
    for tbl in section.find_all("table"):
        # Check it's not nested inside an assessment-detail section
        parent_detail = tbl.find_parent(id=re.compile(r"assessment-detail"))
        if not parent_detail:
            summary_table = tbl
            break

    if summary_table:
        for row in summary_table.select("tbody tr"):
            cells = row.find_all("td")
            if len(cells) >= 4:
                # Title cell may contain an <a> tag followed by an
                # icon-list <ul> with indicators (e.g. "Identity Verified",
                # "In-person", "Team or group-based"). Extract just the
                # link text for the title.
                title_link = cells[1].find("a")
                title = (title_link.get_text(separator=" ", strip=True)
                         if title_link
                         else cells[1].get_text(separator=" ", strip=True))

                # Special indicators from the icon-list
                indicators = []
                icon_list = cells[1].find("ul", class_="icon-list")
                if icon_list:
                    for li in icon_list.find_all("li"):
                        indicators.append(li.get_text(separator=" ", strip=True))

                # Due date cell may have multiple <p> tags
                due_date = cells[3].get_text(separator="; ", strip=True)

                item = {
                    "category": cells[0].get_text(separator=" ", strip=True),
                    "title": title,
                    "weight": cells[2].get_text(separator=" ", strip=True),
                    "due_date": due_date,
                }
                if indicators:
                    item["conditions"] = indicators

                summary.append(item)

    if summary:
        profile["assessment_summary"] = summary

    # --- Detailed assessment items ---
    details = []
    detail_headings = section.select("h3[id^='assessment-detail-']")

    for h3 in detail_headings:
        item = {
            "id": h3.get("id", ""),
            "title": h3.get_text(separator=" ", strip=True),
        }

        # Collect sibling elements between this h3 and the next h3
        # (or end of parent). This scopes extraction to only this item's
        # content, avoiding the bug where all items shared one parent
        # <section> and all got the last item's data.
        scoped_elements = []
        sibling = h3.find_next_sibling()
        while sibling:
            # Stop at the next assessment-detail h3
            if (sibling.name == "h3"
                    and sibling.get("id", "").startswith("assessment-detail")):
                break
            scoped_elements.append(sibling)
            sibling = sibling.find_next_sibling()

        # Build a temporary container soup so the extraction helpers work
        from bs4 import Tag
        temp = Tag(name="div")
        for el in scoped_elements:
            temp.append(el.__copy__())  # copy to avoid mutating the tree
        _extract_assessment_fields(temp, item)

        details.append(item)

    if details:
        profile["assessment_details"] = details


def _extract_assessment_fields(container, item: dict):
    """Extract all fields from an assessment detail container."""
    # DT/DD pairs
    for dt_tag in container.find_all("dt"):
        label = dt_tag.get_text(separator=" ", strip=True)
        dd_tag = dt_tag.find_next_sibling("dd")
        if not dd_tag:
            continue

        value = dd_tag.get_text(separator=" ", strip=True)
        key = _normalise_field_name(label)
        if key:
            item[key] = value

    # Subheadings with content (Task description, Submission guidelines, etc.)
    for h4 in container.find_all("h4"):
        heading_text = h4.get_text(separator=" ", strip=True)
        key = _normalise_field_name(heading_text)
        if not key:
            continue

        # Get the content after this h4
        content_parts = []
        sibling = h4.find_next_sibling()
        while sibling and sibling.name not in ("h3", "h4"):
            text = sibling.get_text(separator=" ", strip=True)
            if text:
                content_parts.append(text)
            sibling = sibling.find_next_sibling()

        if content_parts:
            item[key] = "\n".join(content_parts)

    # H5 subsections (Deferral or extension, Late submission, etc.)
    for h5 in container.find_all("h5"):
        heading_text = h5.get_text(separator=" ", strip=True)
        key = _normalise_field_name(heading_text)
        if not key:
            continue

        sibling = h5.find_next_sibling()
        if sibling and sibling.name in ("p", "div"):
            item[key] = sibling.get_text(separator=" ", strip=True)

    # Check for AI statements within this assessment item
    full_text = container.get_text()
    if re.search(r"artificial intelligence|generative ai|\bAI\b", full_text, re.I):
        ai_parts = []
        for el in container.find_all(["p", "li", "div"]):
            el_text = el.get_text(separator=" ", strip=True)
            if re.search(r"artificial intelligence|generative ai|use of AI|\bAI tools\b|\bAI writing\b", el_text, re.I):
                if len(el_text) > 20 and el_text not in ai_parts:
                    ai_parts.append(el_text)
        if ai_parts:
            item["ai_statement"] = "\n".join(ai_parts)

    # Assessment security (S2 2026 onwards): "Secure assessment: ..." or
    # "Open assessment: ...". Caught above if it is a dt/h4/h5 label; this is the
    # fallback for any other markup, so the Secure/Open flag is never lost.
    if "assessment_security" not in item:
        m = re.search(r"((?:Secure|Open) assessment:[^\n]*?\.)(?:\s|$)", full_text)
        if m:
            item["assessment_security"] = re.sub(r"\s+", " ", m.group(1)).strip()

    # Special indicators (icons)
    for icon_list in container.select(".icon-list"):
        indicators = []
        for li in icon_list.find_all("li"):
            indicators.append(li.get_text(separator=" ", strip=True))
        if indicators:
            item["special_indicators"] = indicators


def _extract_assessment_fields_from_elements(elements: list, item: dict):
    """Extract assessment fields from a list of sibling elements."""
    for el in elements:
        if hasattr(el, "find_all"):
            _extract_assessment_fields(el, item)


def _normalise_field_name(label: str) -> str:
    """Convert a heading/label into a snake_case field name."""
    mappings = {
        "Mode": "mode",
        "Category": "category",
        "Weight": "weight",
        "Due date": "due_date",
        "Learning outcomes": "learning_outcomes_assessed",
        "Other conditions": "other_conditions",
        "Task description": "task_description",
        "Submission guidelines": "submission_guidelines",
        "Exam details": "exam_details",
        "Assessment security": "assessment_security",
        "Deferral or extension": "deferral_or_extension",
        "Late submission": "late_submission",
        "Course grading": "course_grading",
        "Supplementary assessment": "supplementary_assessment",
    }
    return mappings.get(label, "")


def _extract_learning_resources(soup: BeautifulSoup, profile: dict):
    """Extract learning resources section."""
    section = soup.find(id="learning-resources")
    if not section:
        return

    resources = {}

    # Look for required texts, library resources, etc.
    for heading in section.find_all(["h3", "h4"]):
        heading_text = heading.get_text(separator=" ", strip=True).lower()
        content_parts = []
        sibling = heading.find_next_sibling()
        while sibling and sibling.name not in ("h2", "h3"):
            text = sibling.get_text(separator=" ", strip=True)
            if text:
                content_parts.append(text)
            sibling = sibling.find_next_sibling()

        if content_parts:
            key = re.sub(r"[^a-z0-9]+", "_", heading_text).strip("_")
            resources[key] = "\n".join(content_parts)

    # If no headings found, just get all text
    if not resources:
        text = section.get_text(separator=" ", strip=True)
        text = re.sub(r"^Learning resources\s*", "", text).strip()
        if text:
            resources["text"] = text

    if resources:
        profile["learning_resources"] = resources


def _extract_learning_activities(soup: BeautifulSoup, profile: dict):
    """Extract the weekly learning activities table."""
    section = soup.find(id="learning-activities")
    if not section:
        return

    table = section.find("table")
    if not table:
        return

    activities = []
    current_period = ""

    for row in table.select("tbody tr"):
        cells = row.find_all("td")
        if not cells:
            continue

        activity = {}

        if len(cells) >= 3:
            # Three-column row: learning period, activity type, topic
            period_text = cells[0].get_text(separator=" ", strip=True)
            if period_text:
                current_period = period_text
            activity["learning_period"] = current_period
            activity["activity_type"] = cells[1].get_text(separator=" ", strip=True)
            activity["topic"] = cells[2].get_text(separator=" ", strip=True)

            # Try to extract LOs from topic cell
            topic_text = cells[2].get_text()
            lo_match = re.findall(r"LO?\d+", topic_text)
            if lo_match:
                activity["learning_outcomes"] = list(dict.fromkeys(lo_match))

        elif len(cells) == 2:
            # Two-column row: activity type, topic (period continues from previous)
            activity["learning_period"] = current_period
            activity["activity_type"] = cells[0].get_text(separator=" ", strip=True)
            activity["topic"] = cells[1].get_text(separator=" ", strip=True)

            topic_text = cells[1].get_text()
            lo_match = re.findall(r"LO?\d+", topic_text)
            if lo_match:
                activity["learning_outcomes"] = list(dict.fromkeys(lo_match))

        if activity.get("topic"):
            activities.append(activity)

    if activities:
        profile["learning_activities"] = activities


def _extract_policies(soup: BeautifulSoup, profile: dict):
    """Extract policies and procedures section."""
    section = soup.find(id="policies-and-guidelines")
    if not section:
        return

    text = section.get_text(separator=" ", strip=True)
    text = re.sub(r"^Policies and procedures\s*", "", text).strip()

    if text:
        profile["policies_and_procedures"] = text


# ---------------------------------------------------------------------------
# Whitespace normalisation
# ---------------------------------------------------------------------------

# Collapse runs of spaces/tabs/non-breaking spaces to single spaces without
# eating intentional newlines. BeautifulSoup's ``separator=" "`` can double up
# spaces at element boundaries, so we do a post-pass to clean every string.
_WS_RUN = re.compile(r"[ \t\u00A0]+")
_NL_RUN = re.compile(r"\n{3,}")

# Targeted stopword-join rules — mirror of clean_existing._SPECIFIC_JOINS.
# These handle the "Policyand Procedure" / "onmy.UQand" family of artefacts
# that can still slip through even with ``separator=" "`` when the HTML
# source has no inter-element whitespace. Belt-and-braces: applied after
# whitespace normalisation as a final polish step.
_VOCAB_WORDS = (
    r"Policy|Procedure|Procedures|Guide|Guides|Service|Services|"
    r"Report|Reports|Manual|Manuals|Library|Integrity|Assessment|Assessments|"
    r"Examination|Examinations|Adjustment|Adjustments|Code|Codes|Statement|"
    r"Statements|Framework|Frameworks|Regulation|Regulations|Rule|Rules|"
    r"Misconduct|Handbook|Handbooks|Plan|Plans|Policies|Act|Acts|Standard|"
    r"Standards|Charter|Form|Forms"
)
_STOPWORDS = r"and|or|the"
_STOPWORD_JOINS = [
    (re.compile(rf"\b({_VOCAB_WORDS})({_STOPWORDS})\b"), r"\1 \2"),
    (re.compile(rf"\b(UQ)({_STOPWORDS})\b"), r"\1 \2"),
    (re.compile(rf"\b((?:my|Learn)\.UQ)({_STOPWORDS})(?=[a-z])"), r"\1 \2 "),
    (re.compile(rf"\b((?:my|Learn)\.UQ)({_STOPWORDS})\b"), r"\1 \2"),
    (re.compile(r"\b(on|at|in|by|via|about)(my\.UQ)"), r"\1 \2"),
    (re.compile(rf"\b(SI-net)({_STOPWORDS}|to)\b"), r"\1 \2"),
    (re.compile(rf"(^|\s)(the)({_VOCAB_WORDS})\b"), r"\1\2 \3"),
    (re.compile(rf"\b({_VOCAB_WORDS})\.([A-Z][a-z])"), r"\1. \2"),
]


def _apply_stopword_joins(s: str) -> str:
    """Apply targeted stopword-boundary fixes, shielding URLs and emails."""
    placeholders: list[str] = []

    def _stash(match: re.Match) -> str:
        placeholders.append(match.group(0))
        return f"\x00{len(placeholders) - 1}\x00"

    protected = re.sub(r"https?://\S+|\S+@\S+\.\S+", _stash, s)
    # Two passes so multi-join sequences like "Procedureand thePolicy" get
    # fully expanded.
    for _ in range(2):
        for pattern, repl in _STOPWORD_JOINS:
            protected = pattern.sub(repl, protected)

    def _unstash(match: re.Match) -> str:
        return placeholders[int(match.group(1))]

    return re.sub(r"\x00(\d+)\x00", _unstash, protected)


def normalise_ws(value):
    """Recursively collapse whitespace in every string found in ``value``.

    Safe for any JSON-compatible tree (str / list / dict / scalar).
    Preserves single and double newlines (paragraph structure) but collapses
    runs of spaces/tabs/NBSPs into one space, trims line edges and trailing
    whitespace, and reduces 3+ newlines to two. Also applies targeted
    stopword-boundary fixes for known UQ policy-text glue patterns.
    """
    if isinstance(value, str):
        s = value.replace("\u00A0", " ")
        s = _WS_RUN.sub(" ", s)
        # Trim each line so " paragraph " and trailing runs don't linger
        s = "\n".join(line.strip(" \t") for line in s.split("\n"))
        s = _NL_RUN.sub("\n\n", s)
        s = _apply_stopword_joins(s)
        # Re-collapse any accidental double spaces introduced by joins
        s = _WS_RUN.sub(" ", s)
        return s.strip()
    if isinstance(value, list):
        return [normalise_ws(v) for v in value]
    if isinstance(value, dict):
        return {k: normalise_ws(v) for k, v in value.items()}
    return value


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------

def save_profile(profile: dict, base_dir: Path | None = None) -> bool:
    """Save a scraped profile as a JSON file."""
    if base_dir is None:
        base_dir = PROFILES_DIR

    semester_code = profile.get("semester_code", "unknown")
    full_code = profile.get("full_course_code", "unknown")

    output_dir = base_dir / semester_code
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{full_code}.json"

    # Normalise whitespace in every string field before writing
    profile = normalise_ws(profile)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        log.error(f"  Failed to save {output_path}: {e}")
        return False


# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------

def scrape_course(course_code: str, semester_filter: str | None = None) -> dict:
    """
    Scrape all available profiles for a given course code.
    Uses the JacSON GitHub repo index to discover profile URLs,
    then scrapes each profile from course-profiles.uq.edu.au.
    """
    result = {
        "course_code": course_code,
        "profiles_scraped": 0,
        "profiles_failed": 0,
        "errors": [],
    }

    # Step 1: Discover profile URLs from JacSON repo index
    profile_entries = discover_profile_urls(course_code, semester_filter)

    if not profile_entries:
        log.warning(f"  No profiles found in JacSON repo for {course_code}")
        result["errors"].append("No profiles found in JacSON repo index")
        return result

    log.info(f"  Found {len(profile_entries)} profile(s) for {course_code}")

    # Step 2: Scrape each profile page
    for entry in profile_entries:
        url = entry["url"]
        log.info(f"  Scraping: {url}")

        profile = scrape_profile(url)
        time.sleep(REQUEST_DELAY)

        if profile:
            if save_profile(profile):
                result["profiles_scraped"] += 1
                log.info(f"  ✓ Saved {profile.get('full_course_code', 'unknown')}")
            else:
                result["profiles_failed"] += 1
                result["errors"].append(f"Failed to save profile from {url}")
        else:
            result["profiles_failed"] += 1
            result["errors"].append(f"Failed to scrape {url}")

    return result


def main(
    semester_filter: str | None = None,
    course_filter: list[str] | None = None,
    max_courses: int | None = None,
    all_uq: bool = False,
    delay: float | None = None,
    allow_empty_index: bool = False,
):
    """
    Main entry point.

    Args:
        semester_filter: Only scrape profiles for this semester code (e.g. '7620')
        course_filter: Only scrape these specific course codes
        max_courses: Limit the number of courses to scrape (useful for testing)
        allow_empty_index: Debugging only. Carry on with an empty index if the
            JacSON tree fetch fails or is truncated (the pre-2026-08-25 behaviour)
    """
    # Apply custom delay if specified
    global REQUEST_DELAY, ALLOW_EMPTY_INDEX
    if delay is not None:
        REQUEST_DELAY = max(0.2, delay)  # floor at 0.2s to stay polite
    ALLOW_EMPTY_INDEX = bool(allow_empty_index)

    mode_label = "All-of-UQ" if all_uq else "UQBS"
    log.info("=" * 60)
    log.info(f"UQ Course Profile Scraper ({mode_label})")
    log.info(f"Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"Request delay: {REQUEST_DELAY}s")
    log.info("=" * 60)

    # Pre-fetch the JacSON repo index (single GitHub API call) — needed
    # both for URL discovery and for all-of-UQ course list
    _fetch_repo_index()

    # Load course list
    if all_uq:
        all_courses = load_all_uq_course_list(semester_filter)
    else:
        all_courses = load_course_list()

    # Apply filters
    if course_filter:
        courses = [c for c in course_filter if c in all_courses or True]
        log.info(f"Filtering to {len(courses)} specified course(s)")
    else:
        courses = all_courses

    if max_courses:
        courses = courses[:max_courses]
        log.info(f"Limiting to first {max_courses} course(s)")

    if semester_filter:
        log.info(f"Semester filter: {semester_filter}")

    log.info(f"Scraping {len(courses)} course(s)...")
    log.info("-" * 60)

    # Scrape
    results = {
        "total_courses": len(courses),
        "courses_with_profiles": 0,
        "total_profiles_scraped": 0,
        "total_profiles_failed": 0,
        "errors": [],
        "course_results": {},
    }

    for i, course_code in enumerate(courses, 1):
        log.info(f"[{i}/{len(courses)}] {course_code}")
        course_result = scrape_course(course_code, semester_filter)
        results["course_results"][course_code] = course_result

        if course_result["profiles_scraped"] > 0:
            results["courses_with_profiles"] += 1
        results["total_profiles_scraped"] += course_result["profiles_scraped"]
        results["total_profiles_failed"] += course_result["profiles_failed"]
        results["errors"].extend(course_result["errors"])

    # Summary
    log.info("=" * 60)
    log.info("SCRAPE COMPLETE")
    log.info(f"Courses processed: {results['total_courses']}")
    log.info(f"Courses with profiles: {results['courses_with_profiles']}")
    log.info(f"Profiles scraped: {results['total_profiles_scraped']}")
    log.info(f"Profiles failed: {results['total_profiles_failed']}")
    if results["errors"]:
        log.info(f"Errors: {len(results['errors'])}")
    log.info("=" * 60)

    # Save run summary
    summary_path = LOG_DIR / f"summary_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    log.info(f"Summary saved to {summary_path}")

    # A run that targeted a semester or the whole course set and saved nothing
    # is a failure, not a quiet success. Exit 2 so a GitHub Actions job goes red.
    # A run narrowed to named courses (--courses) is exempt: zero can be a true
    # answer there.
    if results["total_profiles_scraped"] == 0 and (semester_filter or not course_filter):
        log.error(
            "ERROR: zero profiles scraped for a run that targeted "
            + (f"semester {semester_filter}" if semester_filter else f"the full {mode_label} course set")
            + ". Nothing was written. Check the JacSON index fetch above "
            "(GITHUB_TOKEN set? truncated?), the semester code, and whether "
            "course-profiles.uq.edu.au is reachable. Exiting with status 2."
        )
        sys.exit(2)

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="UQ Course Profile Scraper")
    parser.add_argument(
        "--semester", "-s",
        help="Only scrape profiles for this semester code (e.g. 7620)",
    )
    parser.add_argument(
        "--courses", "-c",
        nargs="+",
        help="Only scrape these specific course codes (e.g. MGTS1601 ACCT1101)",
    )
    parser.add_argument(
        "--max", "-m",
        type=int,
        help="Maximum number of courses to scrape (useful for testing)",
    )
    parser.add_argument(
        "--all-uq",
        action="store_true",
        default=False,
        help="Scrape all UQ courses (not just UQBS). Uses JacSON repo index "
             "as course list instead of the UQBS taxonomy.",
    )
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=None,
        help="Seconds between requests (default: 1.0). Minimum 0.2.",
    )
    parser.add_argument(
        "--allow-empty-index",
        action="store_true",
        default=False,
        help="Debugging only. If the JacSON repo index cannot be fetched (or is "
             "truncated), log the error and carry on with an empty index instead "
             "of stopping. Restores the pre-2026-08-25 behaviour.",
    )
    args = parser.parse_args()

    try:
        # --semester recent (2026-09-07): the two newest semester codes the JacSON
        # index knows about, which is the current offering and the one being
        # published for next semester. This is what the scheduled all-of-UQ run
        # uses, so nobody has to edit a semester code into the workflow each
        # semester. The scrape then runs once per code.
        semesters = [args.semester]
        if args.semester == "recent":
            index = _fetch_repo_index()
            codes = sorted({e["semester"] for entries in index.values() for e in entries if e.get("semester")})
            semesters = codes[-2:]
            log.info(f"--semester recent resolves to {', '.join(semesters)} (the two newest codes in the index)")
        for sem in semesters:
            main(
                semester_filter=sem,
                course_filter=args.courses,
                max_courses=args.max,
                all_uq=args.all_uq,
                delay=args.delay,
                allow_empty_index=args.allow_empty_index,
            )
    except RepoIndexError as e:
        log.error(f"ERROR: {e} Exiting with status 2.")
        sys.exit(2)
