# Implementation status

Prior audit baseline (Linux, before remediation):
- Backend pytest: 23 passed. Frontend: `tsc --noEmit` and `vite build` succeeded.
- A live uvicorn run: demo load, evidence search, JSON report and a 2-page PDF were produced.

Remediation in this working copy:
- Sentinel values (-999, -9999, -99999) are preserved raw and masked from normalized numeric analysis.
- Numeric cells distinguish PARSED, MISSING, SENTINEL_MISSING, NON_NUMERIC, and NON_FINITE.
- Non-finite measurements and target values are rejected from numerical analysis. Oxygen, pressure reference type,
  and flow definitions must match for numeric target comparisons; mission labels must also match the documented context for DIRECT.
- NaN/infinite measurements and query targets are rejected from numerical analysis; malformed quoted CSV fails before raw/database persistence.
- New raw bytes are removed if the database commit fails; existing files are preserved. Duplicate row values remain retained as possible replicates.
- API attestation fields explicitly say USER-ATTESTED and independently verified=false; gravity claims marked SOURCE_SUPPORTED are returned as user-reported and unverified.
- DIRECT now requires user-attested NASA page checking, source-supported explicit microgravity context,
  comparable evidence and non-synthetic data; terrestrial 1g can never be DIRECT.
- Provenance labels state user attestations are not independently verified. Synthetic and user-imported
  counts are reported separately; user-imported records are not called real or NASA-verified.
- Evidence includes traceable record IDs and physical line ranges; variable recognition includes additional aliases.
- Existing SQLite databases receive a safe additive `numeric_status` column upgrade at startup.
- Added regression coverage for scientific evidence, provenance, ingestion integrity, API validation, and reports.
- API validation sanitizes non-finite values in Pydantic error details so invalid numeric inputs return a valid
  422 response instead of failing response serialization with a 500.
- Executive summaries use the uppercase `SYNTHETIC` disclosure token and state that demo data are not NASA records.
- `httpx2>=2.0.0` is declared for Starlette TestClient compatibility; legacy `httpx` remains declared.
- Backend verification: Windows, Python 3.15.2 in `backend/.venv`; `python -m pytest backend/tests -v` collected
  54 tests and passed all 54, with 0 failures, 0 skips, and no warnings.
- Frontend `npm ci` completed after network access was allowed; `npm run build` passed (TypeScript and Vite).
- npm reported two dependency advisories (one moderate, one high); dependency updates were not applied.

NOT verified:
- Backend tests ran on Windows with Python 3.15.2, not the Python 3.11.16 environment in the initial request.
  The UI was not opened in a browser, so layout and interactions are untested by eye.
- No frontend unit tests were written.
- NASA PSI could not be reached from the build environment (DNS failure). No real NASA data was imported,
  no PSI investigation ID was verified, and the column names of real SAFFIRE files are unknown.

Not implemented: other phenomena, unit conversion, experiment comparison, mission scenario builder,
assistant, authentication, or a general migration framework. Tables are primarily initialized with SQLAlchemy
`create_all`; only the additive `numeric_status` upgrade is handled explicitly.
