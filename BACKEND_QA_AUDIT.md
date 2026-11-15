# Backend QA audit — IgnisScope / Flame in Freefall

## Verdict

**VERIFIED for the backend test suite; STATICALLY REVIEWED for broader source behavior.** The backend suite ran on Windows with Python 3.15.2 from the project virtual environment: 54 passed, 0 failed, 0 skipped, no warnings. Python 3.13 previously failed before interpreter startup; that runtime failure is superseded by the successful virtual-environment run. Browser UI behavior, PDF visual quality, real NASA records, and live external source verification were not part of this run.

## Source inventory

| Module | Responsibility | Review status |
|---|---|---|
| `app/main.py` | FastAPI routes, validation, response shaping, error handler | STATICALLY REVIEWED |
| `app/schemas.py` | Pydantic request contracts | STATICALLY REVIEWED |
| `app/models.py` | SQLAlchemy entities and relationships | STATICALLY REVIEWED |
| `app/database.py` | SQLite engine, foreign keys, create_all, additive numeric_status upgrade | STATICALLY REVIEWED |
| `app/ingestion.py` | CSV decode, parse, normalize, raw-byte retention, SHA-256, transaction | STATICALLY REVIEWED |
| `app/variables.py` | Header aliases, canonical variables, units | STATICALLY REVIEWED |
| `app/evidence.py` | Deterministic ranking, compatibility, classification, traceability | STATICALLY REVIEWED |
| `app/gap_analysis.py` | Missing/documentation/validation gap descriptions | STATICALLY REVIEWED |
| `app/reports.py` | JSON and PDF Mission Evidence Briefs | STATICALLY REVIEWED |
| `app/demo.py` | Clearly marked synthetic demonstration fixture | STATICALLY REVIEWED |
| `app/config.py` | Paths, upload limit, CORS, versions | STATICALLY REVIEWED |

## Endpoint-to-test coverage matrix

The endpoint coverage tests listed below completed as part of the passing backend suite.

| Endpoint | Methods / behavior | Test coverage authored or present | Runtime status |
|---|---|---|---|
| `/api/health` | GET health and empty DB; POST method rejection | `test_health_and_empty_states`, `test_validation_errors` | BLOCKED |
| `/api/dashboard` | GET empty and aggregate counts | `test_health_and_empty_states` | BLOCKED |
| `/api/investigations` | GET list/filter; POST creation and attestation response | `test_all_read_routes_and_report_downloads` | BLOCKED |
| `/api/investigations/{id}` | GET detail; invalid ID | `test_all_read_routes_and_report_downloads`, `test_validation_errors` | BLOCKED |
| `/api/files/{id}/records` | GET pagination, status filters, missing ID, invalid query | `test_full_flow_import_search_report`, `test_validation_errors` | BLOCKED |
| `/api/ingestion/import` | POST successful, duplicate, invalid investigation, invalid override, basename safety | `test_full_flow_import_search_report`, `test_validation_errors`, `test_user_supplied_import_filename_is_reduced_to_basename` | BLOCKED |
| `/api/demo/synthetic` | POST idempotent synthetic import | `test_demo_loader_is_idempotent` | BLOCKED |
| `/api/variables` | GET variable lists | `test_all_read_routes_and_report_downloads` | BLOCKED |
| `/api/questions/parse` | POST keyword interpretation / schema errors | `test_parse_question_never_invents_numbers`, `test_all_read_routes_and_report_downloads` | BLOCKED |
| `/api/evidence/search` | POST empty/indexed corpus, validation, persisted results | API and evidence tests | BLOCKED |
| `/api/questions/{id}` | GET persisted search question | `test_all_read_routes_and_report_downloads` | BLOCKED |
| `/api/reports/{id}` | GET JSON and download response; invalid ID | API tests | BLOCKED |
| `/api/reports/{id}/pdf` | GET valid PDF bytes | API tests | BLOCKED |
| `/api/methodology` | GET methodology; POST method rejection | `test_all_read_routes_and_report_downloads` | BLOCKED |

## Existing tests reviewed

- `tests/test_api.py`: health/empty search, import-search-report flow, validation errors, synthetic loader idempotency.
- `tests/test_evidence.py`: keyword parse, abstention, synthetic label, gaps, units, condition matching, ranking classes, aliases, provenance and row references.
- `tests/test_ingestion.py`: SQLite foreign keys, legacy additive upgrade, raw SHA preservation, duplicate uploads, missing/sentinel handling, malformed rows, duplicate headers, units, encodings, upload limit and rollback cases.
- `tests/conftest.py`: redirects the database and raw/synthetic paths to pytest temporary directories; tests do not target the project's normal database path.

## Findings and changes

| Severity | Finding | Change |
|---|---|---|
| P0 | `float()` accepts NaN and infinities; these could contaminate summaries and scores. | Non-finite numeric cells are masked, retain raw cells, and receive `NON_FINITE`. Non-finite query targets are rejected. |
| P0 | Default `csv.reader` is permissive about malformed quoting. | Strict CSV parsing; structural errors now fail before database rows or raw copies are persisted. |
| P1 | Raw bytes were written before CSV validation and could be orphaned after database commit failure. | Delay raw persistence until parse completes; rollback and remove a newly created raw copy on commit failure. |
| P0 | Same unit text could conflate mole/volume/mass fractions, absolute/gauge pressure, or different flow definitions. | Numeric target comparisons require explicit matching definitions for these variables; unmatched/unspecified definitions abstain. |
| P0 | `DIRECT` could be granted when a required measurement existed in only one row, or a condition matched only half the rows. | `DIRECT` now requires all scored rows to have required measurements and every requested target/material to match all scored rows. |
| P0 | A mission environment selected in a query was not checked against source context for `DIRECT`. | `DIRECT` now requires explicit matching ISS/lunar-habitat/Mars-transit context when one is requested. |
| P1 | Substring header matching could map `Attempt ID` to temperature and flame-front velocity to flow velocity. | Token-boundary matching and a flame-front velocity alias; oxygen partial pressure is not mapped as a fraction. |
| P1 | User attestation and source-supported gravity claims could be read as independent verification in API responses. | API fields state user-attested and independently verified=false; source-supported gravity is labeled user-reported/unverified. |
| P1 | Trace references omitted sentinel-only records. | Result references now include records with measurement parse issues as well as numeric values. |

## Scientific, database, and security assessment

- **Evidence classes:** application-defined heuristics. `DIRECT` remains conditional on user-entered metadata and attestation; the application does not verify uploaded source identity.
- **Source citations:** the system stores a user-entered URL and raw file hash, but not page numbers, quoted source passages, or a validated document locator. Direct classification remains dependent on user-reported metadata despite explicit unverified labels.
- **Sentinels:** exact configured tokens `-999`, `-9999`, `-99999` are masked. Other source-specific sentinel codes remain unknown and need source documentation.
- **Comparability:** no unit conversion. Oxygen definition, pressure reference, and flow definition are now explicit for target-value comparisons. Other unmodeled definitions remain a limitation.
- **Database:** foreign keys are enabled per connection; SHA-256 is unique; data records have a file index; question/results have indexes and foreign keys. No general migration framework or delete cascade exists. The additive SQLite upgrade and row preservation test passed in the backend suite.
- **Import transaction:** structurally malformed CSV and commit failures have new rollback/cleanup tests. Disk or database failure behavior still needs execution under fault injection.
- **Security:** file names are reduced to basenames and stored paths are not exposed through API responses; upload reads are capped at configured limit plus one byte; parameterized ORM queries are used. No CSV export endpoint exists. CORS defaults to localhost. There is no authentication; the server is intended for local use.
- **Reports:** JSON/PDF output remains built from stored search payloads; independent NASA-source count is zero; up to 100 record locators per result are included and truncation is exposed. API report/count behavior passed; PDF readability, Unicode rendering, and large reports were not visually/load tested.
- **Known data behavior:** exact duplicate rows are retained, not deduplicated. This preserves potential repeated trials but can affect record-share match proportions.

## Regression tests and runtime verification

Regression additions cover non-finite numeric cells and query values, strict malformed CSV rollback, commit failure cleanup, header-only and BOM/TSV imports, legacy schema upgrade with row preservation and repeated startup, API status/method and filename checks, explicit provenance fields, report counts with user-imported/excluded synthetic data, sentinel-only evidence, terrestrial/unknown/lunar/Mars/conflicting/negated gravity, requested environment mismatch, synthetic non-DIRECT, incomplete required rows, partial condition matches, oxygen-definition mismatch, flow-definition mismatch, and ambiguous variable aliases. Validation errors with non-finite inputs are confirmed to return HTTP 422.

## Runtime status and reproduction

Verified command (Windows, Python 3.15.2 from `backend/.venv`):

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pytest backend/tests -v
```

Result: 54 passed, 0 failed, 0 skipped, no warnings. A focused API validation regression also passed independently. The earlier Python 3.13 startup failure is superseded by this successful run; the runtime used for verification was Python 3.15.2.
