# Working in this repo

Public repository under the UQ-Business-School organisation. Its GitHub Pages
site is the data host for the course profile viewer, which lives in the
`courses` repo. Commits and Actions run logs are public.

## Commits

Never put attribution trailers in a commit message. No `Co-Authored-By` line
naming an AI, no `Claude-Session` link, no "Generated with" footer. GitHub reads
a co-author line as a repository contributor and shows it on the Insights page,
and a session link on a public repo points at a private conversation. Sean
Mitchell is the author of commits made on his behalf.

Plain Australian English in commit messages. No em dashes.

## The AoL feed

`taxonomy/aol-status.json` and `taxonomy/aol-template.csv` follow the AoL
register on SharePoint by themselves. A Power Automate flow, "AoL register to
course profiles", runs the Office Script in `automation/aol-register-feed.ts` at
5am Brisbane and posts the rows here as a `repository_dispatch` event;
`.github/workflows/aol-register.yml` builds the feed and commits it only when the
register changed. The payload carries six public columns and nothing else: names,
coordinators, notes and folder links stay in the workbook. Setup and
troubleshooting are in `automation/README.md`.
