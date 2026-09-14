# Deploying the UQBS edition — step by step (GitHub Desktop)

This puts the UQBS course profile viewer onto the school server at
`teach.business.uq.edu.au/ld/uqbsld/profiles/`.

It is safe: it only **adds** a folder to the team repo. Your existing live site
and ATLAS are not touched. The UQBS edition is tiny (~1 MB) because it pulls the
heavy course data from your existing site.

---

## What you're moving

From your cowork folder:

    Course Profile Repository/uqbs-course-profiles/build/uqbs/

into the team repo at:

    courses/uqbsld/profiles/

---

## Steps

1. **Open GitHub Desktop.** Top-left, click **Current repository** and pick
   **courses** (`UQ-Business-School/courses`).
   - Not in the list? **File → Clone repository → URL** tab → paste
     `https://github.com/UQ-Business-School/courses` → **Clone**.

2. Menu **Repository → Show in Finder**. This opens the repo folder on your Mac.

3. In that folder, open **`uqbsld`**. Inside it, make a **New Folder** called
   **`profiles`**.
   - The last folder name becomes the web address. `profiles` →
     `.../ld/uqbsld/profiles/`. Rename it if you'd prefer a different URL.

4. Open a **second Finder window** at:
   `Course Profile Repository / uqbs-course-profiles / build / uqbs /`

5. Select **everything inside** `build/uqbs/` — the `.html` files, `README.md`,
   and the **`assets`** and **`taxonomy`** folders — and **copy** them into
   `uqbsld/profiles/`.
   - Copy the *contents*, not the `uqbs` folder itself.

6. In **GitHub Desktop**, the new files appear on the left. In the **Summary**
   box (bottom-left) type `Add UQBS course profile viewer`, click
   **Commit to main**.

7. Click **Push origin** (top).

8. Wait ~15 minutes, then open
   **`http://teach.business.uq.edu.au/ld/uqbsld/profiles/`**.
   You'll land on the **front-door page** with two buttons:
   - **Strictly Business** → the UQBS viewer (with the AoL tab) — stays on this server.
   - **All of UQ** → the all-UQ view on your existing GitHub site.

---

## If something looks off

- **Page loads but no courses appear:** the data comes from your existing live
  site. Check `https://uq-business-school.github.io/uqbs-course-profiles/` is up. If you
  ever rename/retire that repo, the UQBS edition's data link must be updated
  (rebuild with a new `--all-data-base`).
- **404 / nothing there after 15 min:** confirm the files are directly inside
  `uqbsld/profiles/` (you should see `index.html` there, not another `uqbs`
  folder), and that the push succeeded in GitHub Desktop.
- **AoL tab is empty:** expected for now — the real AoL data hasn't been added
  yet (it's currently sample only). That's a later step.

---

## Rebuilding later (when data or the viewer changes)

Claude (or you, on your Mac) re-runs:

    python3 scraper/build_editions.py --editions uqbs \
        --all-data-base https://uq-business-school.github.io/uqbs-course-profiles \
        --uqbs-repo https://github.com/UQ-Business-School/courses

then repeat steps 5–7 to copy the refreshed `build/uqbs/` over the old files.
