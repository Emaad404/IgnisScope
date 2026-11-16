# IgnisScope — Microgravity Combustion Evidence Explorer

A research-support platform for exploring microgravity combustion evidence, tracking experimental provenance, identifying evidence gaps, and generating traceable research briefs.

It is not a certified fire-risk predictor and is not endorsed by NASA. See `docs/SCIENTIFIC_LIMITATIONS.md`.

## Install on Windows

1. Install Python 3.11+ and Node.js 18+ LTS.
2. Open PowerShell in this folder, then run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
powershell -ExecutionPolicy Bypass -File scripts\start_windows.ps1
```

The browser opens at http://localhost:5173. API documentation is at http://localhost:8000/docs.

## Try it

1. On the dashboard, load the synthetic demo dataset.
2. In Evidence Search, use the example question, interpret it, edit the query, and search the evidence.
3. Review evidence gaps.
4. Generate a Mission Evidence Brief in PDF or JSON.

**Data notice:** `data/synthetic/synthetic_flame_spread.csv` contains synthetic demonstration data, not NASA experimental measurements.

## Use real NASA data

1. Visit https://psi.nasa.gov/physci/repo/data/ and locate a relevant investigation, such as a SAFFIRE investigation.
2. Verify the investigation name and ID on the official page yourself.
3. Download an appropriate CSV and import it through the application.
4. Mark an official-page check as completed only if you personally performed that check; then provide the source page URL and upload the CSV.
5. Review the imported column table. Columns are recognized by header name. Missing units can be entered through Unit overrides and are stored as `USER_SUPPLIED`.

The application does not independently verify NASA records, source URLs, or page contents, and it does not retain page-level citations.

## Tests

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_tests_windows.ps1
```

## Project layout

- `backend/app/`: API, ingestion, evidence search, gap analysis, and reports.
- `src/`: web application.
- `data/`: raw-data placeholder and synthetic demo data.
- `docs/`: provenance, implementation status, and scientific limitations.
