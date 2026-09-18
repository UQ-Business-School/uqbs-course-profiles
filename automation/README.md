# AoL register to course profiles: the automatic feed

The course profiles viewer (teach.business.uq.edu.au/ld/uqbsld/profiles/) shows each course's Assurance of Learning status from `taxonomy/aol-status.json`. That file now follows the AoL register on SharePoint by itself. Learning designers edit the register, and the viewer shows the change the next morning. Nobody runs anything.

## How it works

1. **5:00 am Brisbane, every day.** A Power Automate flow, "AoL register to course profiles", runs the Office Script `aol-register-feed.ts` (this folder) against `UQBS-AoL-Register.xlsx`. The script only reads. It returns course, GA, assessment, status, First implemented and the rubric file for every row of the `AoLRegister` table. Names, coordinators, notes and folder links stay in the workbook.
2. **The flow sends that to GitHub** with the GitHub connector's "Create a repository dispatch event" action (event type `aol-register`). Excel Online (Business) and GitHub are both standard connectors, so no premium licence is needed. GitHub never signs in to SharePoint and the repo holds no Microsoft credentials.
3. **`.github/workflows/aol-register.yml` runs.** It passes the rows to `scraper/export_aol_register.py --payload`, which writes `taxonomy/aol-template.csv`, checks it with `import_aol.py`, and builds `aol-status.json`. If the CSV is the same as yesterday's, the run stops there. If it changed, the bot commits the three feed files and redeploys Pages. The viewer reads the new JSON a few minutes later.

The semester on each row follows the same rules as a local export. The terms the September 2026 Blackboard sweeps found are saved in `data/aol-semester-evidence.csv`, because the automatic run cannot see the pull folders. After that the row's First implemented is used, and otherwise the current semester (January to June is S1, July to December S2).

## What learning designers need to know

- Add rows inside the register table. Typing on the first empty row under it extends the table; rows outside the table are not sent.
- Pick Status and GA from the dropdowns. A status or GA the feed does not know stops that morning's update (see below), and so does a blank GA on any row that isn't N/A or TBD. A row with no Status is left out of the feed.
- Fill in First implemented (for example `S1 2027`) when you know it. Otherwise the row shows under the current semester.
- Link rubrics the usual way, `=HYPERLINK(FileBase&"CODE/file","Rubric")`. That is where the rubric file comes from, so never paste values over the Rubric column; the feed refuses to lose more than a fifth of its links in one go.
- A course that is not in `taxonomy/uqbs-programs.json` still goes into the feed, but it won't appear in the programme views until it is added to the taxonomy.

## Setting it up (once)

The GitHub side is this repo; it is live once `aol-register.yml` is on `main`. The Microsoft side takes about fifteen minutes. UQ's Power Platform data policy has to allow Excel Online (Business) and GitHub in the same flow; if it doesn't, the flow will refuse to save at step 3 and this route is closed until ITS allows it.

**Office Script**

1. Open `UQBS-AoL-Register.xlsx` in Excel for the web. Go to **Automate > New Script**. (No Automate tab means Office Scripts are switched off for your account.)
2. Delete what is there, paste in the whole of `automation/aol-register-feed.ts`, and rename the script "AoL register feed". Save.
3. Select **Run**. The output pane should say something like `203 register rows, 21920 bytes`. The register is not changed.
4. Move the script somewhere the team can reach: select the script name, then **Move**, and pick a folder on the Curriculum Uplift team site (for example an `Automation` folder beside `4. AoL (Sean)`). Scripts left in a personal OneDrive can only be edited by their owner.

**Flow**

1. In Power Automate, **Create > Scheduled cloud flow**. Name it "AoL register to course profiles", repeat every 1 day, then open the Recurrence trigger and set the time zone to (UTC+10:00) Brisbane, at hour 5.
2. Add **Excel Online (Business) > Run script from SharePoint library**.
   - Workbook Location: the Curriculum Uplift team site (`https://uq.sharepoint.com/teams/bs3u7kls`). Workbook Library: Documents.
   - Workbook: `Curriculum Uplift and New Course Development/01. Assurance of Learning (AoL)/4. AoL (Sean)/UQBS-AoL-Register.xlsx`.
   - Script Location, Script Library, Script: wherever you moved "AoL register feed.osts".
3. Add **GitHub > Create a repository dispatch event**. Sign in to GitHub when asked. If GitHub asks for access to the UQ-Business-School organisation, grant it (an organisation owner may need to approve the app).
   - Repository Owner: `UQ-Business-School`. Repository Name: `uqbs-course-profiles`. Event Name: `aol-register`.
   - Event Payload: choose **result** from the Run script step's dynamic content. If the field won't take it, add a key `feed` with the expression `string(outputs('Run_script_from_SharePoint_library')?['body/result'])` (if you renamed the step, use its new name with underscores for spaces). The workflow accepts either shape.
4. Optional, recommended: add **Office 365 Outlook > Send an email (V2)** after the GitHub step, and under its **Settings > Run after** tick "has failed", "is skipped" and "has timed out" for the GitHub step. Send it to whoever looks after the register.
5. Save, then **Test > Manually**. In GitHub, **Actions > AoL register feed** should show a run within a minute. With the register unchanged it ends with "The register has not changed since the last feed", which is a pass.
6. **Details > Owners > Edit**: add the person who looks after the register while you are away. Co-owners can use the flow's GitHub and Microsoft connections. The GitHub connection can write to every repo its account can, so only add people you would trust with that, or sign the GitHub step in with an account whose only write access is this repo.

## When it fails

A failed GitHub run raises an issue called "AoL register feed failed" in this repo (or comments on the one already open), and GitHub emails the account the flow signs in with. The site keeps showing the last good register. Open the run and read the last lines of the "Build the feed" step.

| The run says | Fix |
|---|---|
| `invalid status` or `invalid ga` on a row | Correct that row in the register. It goes through the next morning. A genuinely new status goes into the register's Lists tab, `STATUSES` in `import_aol.py` and `AOL_STATUS` in the viewer's `app.js` (courses repo), in that order. |
| `Refusing to replace the feed` | The register lost more than a fifth of its rows or rubric links since the last feed. Pasting values over the Rubric column does this. If it was a mistake, restore the register from SharePoint version history. If it was deliberate, run the export once locally with `--allow-shrink` (below) and push. |
| `payload says N rows but carries M` | The event arrived cut short. Rerun the flow. |
| `S1 2028 is not in teaching-periods.json` | Add the new year's semesters to `taxonomy/teaching-periods.json`. |
| The Power Automate run fails at Run script | The error names the problem: the `AoLRegister` table, a renamed column heading, or the `FileBase` name. Put it back, or change the script and `PAYLOAD_COLUMNS` in the exporter together. |
| `No saved sweep evidence` | `data/aol-semester-evidence.csv` is missing or empty. Restore it from git history. |
| `is not on https://uq.sharepoint.com/` | The FileBase name on the register's Folders sheet no longer points at UQ SharePoint. Fix it there. |
| `Could not start the Pages deploy` | The feed is committed but the site wasn't rebuilt. Run **Deploy Course Profile Viewer** by hand from the Actions tab. |
| `GitHub takes less than 64 KB` from the script | The register has outgrown one event (roughly 500 rows). The flow needs splitting into two events before more rows go in. |

## Running it by hand

Anyone with a clone, push rights to this repo, Python with `openpyxl` (`pip install openpyxl`) and the synced SharePoint folder can still run the export locally, as before:

```bash
python3 scraper/export_aol_register.py --workbook "<SharePoint>/4. AoL (Sean)/UQBS-AoL-Register.xlsx"
git add taxonomy/aol-template.csv taxonomy/aol-status.json logs/aol-export-report.csv
git commit -m "AoL feed: register as at <date>" && git push
```

Add the `--pulls` and `--native-rubrics` arguments from the main README to re-read the sweep evidence; `--write-evidence data/aol-semester-evidence.csv` saves what they find for the automatic run. `--emit-payload file.json` writes exactly what the Office Script would send, which is how `data/aol-register-payload-sample.json` was made. A manual run of the workflow from the Actions tab checks that sample (including the status and GA checks) and never commits.

## Changing what is sent

The script and the exporter agree on six columns (`PAYLOAD_COLUMNS`), found by their headings, and a schema number. Change both files in one commit, bump the schema in both, then paste the new script into the register's Automate tab. Anyone can read this public repo's run logs and feed files, so nothing private should ever be added to the payload.
