# Flame in Freefall (hackathon MVP)

A research-support tool that imports microgravity combustion CSV data with full provenance, searches it for
flame-spread evidence, shows what is missing, and writes a Mission Evidence Brief (PDF and JSON).

It is not a certified fire-risk predictor and is not endorsed by NASA. See `docs/SCIENTIFIC_LIMITATIONS.md`.

## Install on Windows
1. Install Python 3.11+ (tick "Add to PATH") and Node.js 18+ LTS.
2. Open PowerShell in this folder, then:
```
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
powershell -ExecutionPolicy Bypass -File scripts\start_windows.ps1
```
The browser opens at http://localhost:5173. API docs: http://localhost:8000/docs.

## Try it
1. Dashboard: "Load synthetic demo" (labeled SYNTHETIC - NOT NASA DATA).
2. Evidence search: "Use example question", "Interpret question", edit the query, "Search evidence".
3. Evidence gaps, then Mission evidence brief: download the PDF or JSON.

## Use real NASA data
1. Open https://psi.nasa.gov/physci/repo/data/ in your browser and find an investigation about flame spread
   (for example a SAFFIRE investigation). Check the investigation name and ID on the page yourself.
2. Download a CSV. Import data page: create the investigation, mark the NASA page check as a user attestation
   only if you did, paste the page URL, and upload the CSV. The app cannot independently verify the record,
   source URL, or page contents, and it does not retain a page-level citation.
3. Check the column table after import. Columns are recognised by header name only. If a unit is missing
   from a header, add it under "Unit overrides" (stored as USER_SUPPLIED).

## Tests
```
powershell -ExecutionPolicy Bypass -File scripts\run_tests_windows.ps1
```

## Layout
`backend/app`: database.py, models.py, ingestion.py, variables.py, evidence.py, gap_analysis.py, reports.py, main.py.
`frontend/src`: pages for the six sections. `data/raw`: immutable copies of imported files. `docs/`: provenance, limits, status.

## Backup
Copy `data\flame.db` and `data\raw\` while the backend is stopped.
