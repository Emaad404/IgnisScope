# Implementation status

Prior audit baseline (Linux, before remediation):
- Backend pytest: 23 passed. Frontend: `tsc --noEmit` and `vite build` succeeded.
- A live uvicorn run: demo load, evidence search, JSON report and a 2-page PDF were produced.

Remediation in this working copy:
- Sentinel values (-999, -9999, -99999) are preserved raw and masked from normalized numeric analysis.
- Numeric cells distinguish PARSED, MISSING, SENTINEL_MISSING, and NON_NUMERIC.
- DIRECT now requires user-attested NASA page checking, source-supported explicit microgravity context,
  comparable evidence and non-synthetic data; terrestrial 1g can never be DIRECT.
- Provenance labels state user attestations are not independently verified. Synthetic and user-imported
  counts are reported separately; user-imported records are not called real or NASA-verified.
- Evidence includes traceable record IDs and physical line ranges; variable recognition includes additional aliases.
- Existing SQLite databases receive a safe additive `numeric_status` column upgrade at startup.
- Added regression tests. This Windows environment's Python 3.13 runtime fails at startup (status -1073741515),
  so the updated backend suite could not be executed here.
- Frontend `npm ci` completed after network access was allowed; `npm run build` passed (TypeScript and Vite).
- npm reported two dependency advisories (one moderate, one high); dependency updates were not applied.

NOT verified:
- Not run on Windows. Not opened in a browser, so the React UI layout and interactions are untested by eye.
- No frontend unit tests were written.
- NASA PSI could not be reached from the build environment (DNS failure). No real NASA data was imported,
  no PSI investigation ID was verified, and the column names of real SAFFIRE files are unknown.

Not implemented: other phenomena, unit conversion, experiment comparison, mission scenario builder,
assistant, authentication, migrations (tables are created with SQLAlchemy create_all).
