# Data provenance

- Every imported file is stored once under `data/raw/<sha256 prefix>_<name>` (exclusive create, never overwritten)
  and fingerprinted with SHA-256. Re-importing identical bytes is rejected (HTTP 409).
- Per file: filename, source URL (as typed by the user), size, encoding, delimiter, import time, pipeline version,
  original headers (by position, duplicates allowed), parse warnings.
- Per record: logical record number, physical line range, original cell values (empty string kept as empty,
  absent cell kept as null), extra cells, row parse status (OK, SHORT, LONG), numeric parse status
  (PARSED, MISSING, SENTINEL_MISSING, NON_NUMERIC, NON_FINITE), and issues. Evidence results include record IDs and line ranges.
- Derived values live in a separate `normalized` field. Raw values are never edited.
- Missing values (empty, NA, NaN, null, none, -, --) become null, never zero.
- Values -999, -9999, -99999 are preserved in raw cells, marked SENTINEL_MISSING, and masked to null in
  normalized values so they cannot enter evidence summaries or matching.
- Non-finite numeric tokens (NaN and positive/negative infinity, including overflow such as `1e9999`) remain
  in raw cells, receive NON_FINITE status, and are masked from normalized values.
- Structurally malformed quoted CSV is rejected before raw bytes or database records are committed. If the
  database commit fails after a new raw copy is written, that newly written copy is removed.
- NaN and infinite values are preserved raw and marked NON_FINITE; exact duplicate rows are retained (not
  automatically deduplicated) and can affect record-share match calculations.
- Units are taken only from the header text (e.g. "Pressure (kPa)") or typed by the user (USER_SUPPLIED).
  No unit conversion is implemented.
- `nasa_verified` records only a user attestation that they checked a NASA page. It is not independent
  verification, and user-imported records are not described as NASA records without independently confirmed provenance.
- Synthetic data: `data/synthetic/synthetic_flame_spread.csv`, labeled SYNTHETIC - NOT NASA DATA everywhere.
