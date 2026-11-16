"""CSV ingestion with provenance. Source bytes are stored once and never modified."""
import csv
import hashlib
import io
import re
from pathlib import Path

from sqlalchemy.orm import Session

from . import config
from .models import DataRecord, Investigation, SourceFile
from .variables import VARIABLES, match_variable, split_header

MISSING_TOKENS = {"", "na", "n/a", "nan", "null", "none", "--", "-"}
SENTINEL_CANDIDATES = {-999.0, -9999.0, -99999.0}
ALLOWED_SUFFIXES = {".csv", ".tsv", ".txt"}


class IngestionError(Exception):
    pass


class DuplicateFileError(IngestionError):
    def __init__(self, existing_id: int):
        super().__init__(f"A file with identical content is already imported (source file id {existing_id}).")
        self.existing_id = existing_id


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", Path(name).name)[:100] or "upload.csv"


def decode(raw: bytes) -> tuple[str, str, list[str]]:
    try:
        return raw.decode("utf-8-sig"), "utf-8", []
    except UnicodeDecodeError:
        return raw.decode("latin-1"), "latin-1", [
            "File is not valid UTF-8. Decoded as latin-1 as a guess; check special characters."]


def sniff_delimiter(text: str, filename: str) -> tuple[str, list[str]]:
    if filename.lower().endswith(".tsv"):
        return "\t", []
    try:
        return csv.Sniffer().sniff(text[:4096], delimiters=",;\t").delimiter, []
    except csv.Error:
        return ",", ["Delimiter could not be detected; assumed comma."]


def to_number(token: str | None):
    if token is None or token.strip().lower() in MISSING_TOKENS:
        return None
    try:
        return float(token.strip())
    except ValueError:
        return "NON_NUMERIC"


def ingest_bytes(db: Session, raw: bytes, filename: str, investigation_id: int,
                 source_url: str | None = None, unit_overrides: dict | None = None,
                 is_synthetic: bool = False) -> SourceFile:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise IngestionError(f"Unsupported file type '{suffix}'. Use .csv, .tsv or .txt.")
    if not raw:
        raise IngestionError("File is empty.")
    if len(raw) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise IngestionError(f"File is larger than {config.MAX_UPLOAD_MB} MB.")
    inv = db.get(Investigation, investigation_id)
    if inv is None:
        raise IngestionError(f"Investigation {investigation_id} does not exist.")

    sha = hashlib.sha256(raw).hexdigest()
    existing = db.query(SourceFile).filter_by(sha256=sha).first()
    if existing:
        raise DuplicateFileError(existing.id)

    # immutable raw copy: exclusive-create so an existing file can never be overwritten
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    stored = config.RAW_DIR / f"{sha[:16]}_{safe_name(filename)}"
    if not stored.exists():
        with open(stored, "xb") as fh:
            fh.write(raw)

    text, encoding, warnings = decode(raw)
    delimiter, w = sniff_delimiter(text, filename)
    warnings += w
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)

    try:
        header = next(reader)
    except (StopIteration, csv.Error):
        raise IngestionError("No header row could be read.")
    header_end_line = reader.line_num

    overrides = {k.strip().lower(): v for k, v in (unit_overrides or {}).items()}
    columns, column_map, seen = [], {}, {}
    for i, original in enumerate(header):
        name, unit = split_header(original)
        unit_source = "HEADER" if unit else None
        if not unit and original.strip().lower() in overrides:
            unit, unit_source = overrides[original.strip().lower()], "USER_SUPPLIED"
        canonical = match_variable(name)
        if canonical and canonical in column_map:
            warnings.append(f"Column {i + 1} '{original}' also looks like '{canonical}' but column "
                            f"{column_map[canonical] + 1} was used. Column kept, not mapped.")
            canonical = None
        elif canonical:
            column_map[canonical] = i
        if not original.strip():
            warnings.append(f"Column {i + 1} has a blank header.")
        seen.setdefault(original.strip().lower(), []).append(i + 1)
        columns.append(dict(index=i, original=original, name=name, unit=unit,
                            unit_source=unit_source, canonical=canonical))
    for h, positions in seen.items():
        if len(positions) > 1:
            warnings.append(f"Duplicate header '{h}' in columns {positions}. Identified by position.")

    sentinel_hits: dict[int, int] = {}
    records, prev_end = [], header_end_line
    n = len(columns)
    fatal = None
    rec_no = 0
    while True:
        try:
            row = next(reader)
        except StopIteration:
            break
        except csv.Error as e:
            fatal = f"CSV parse error after line {prev_end}: {e}. Later rows were not imported."
            break
        start, end = prev_end + 1, reader.line_num
        prev_end = end
        if not row:
            warnings.append(f"Blank line at {start}, skipped (not a record).")
            continue
        rec_no += 1
        issues, status, extra = [], "OK", []
        values: list = list(row[:n])
        if len(row) < n:
            status = "SHORT"
            issues.append(f"Row has {len(row)} cells, expected {n}. Missing cells are stored as absent (null).")
            values += [None] * (n - len(row))
        elif len(row) > n:
            status = "LONG"
            extra = row[n:]
            issues.append(f"Row has {len(row)} cells, expected {n}. Extra cells kept separately.")
        norm, numeric_status = {}, {}
        for canonical, idx in column_map.items():
            tok = values[idx]
            if VARIABLES[canonical]["numeric"]:
                num = to_number(tok)
                if num == "NON_NUMERIC":
                    issues.append(f"Non-numeric value '{tok}' in '{columns[idx]['original']}'.")
                    num = None
                    numeric_status[canonical] = "NON_NUMERIC"
                elif num is not None and num in SENTINEL_CANDIDATES:
                    sentinel_hits[idx] = sentinel_hits.get(idx, 0) + 1
                    issues.append(f"Value {tok} in '{columns[idx]['original']}' may be a missing-data "
                                  "sentinel. Masked from numeric analysis; original cell is preserved.")
                    numeric_status[canonical] = "SENTINEL_MISSING"
                    num = None
                elif num is None:
                    numeric_status[canonical] = "MISSING"
                else:
                    numeric_status[canonical] = "PARSED"
                norm[canonical] = num
            else:
                norm[canonical] = None if tok is None or tok.strip().lower() in MISSING_TOKENS else tok.strip()
        records.append(DataRecord(record_number=rec_no, line_start=start, line_end=end, parse_status=status,
                                  issues=issues, raw_values=values, extra_cells=extra, normalized=norm,
                                  numeric_status=numeric_status))

    for idx, count in sentinel_hits.items():
        warnings.append(f"{count} value(s) in '{columns[idx]['original']}' match common sentinel codes "
                        "(-999, -9999, -99999). Review before use.")
    if fatal:
        warnings.append(fatal)
    bad = sum(1 for r in records if r.parse_status != "OK")
    if bad:
        warnings.append(f"{bad} of {len(records)} record(s) are malformed (see record issues). "
                        "They are stored but excluded from evidence scoring.")

    # data-quality indicators (kept separate, never merged into one score)
    ok = [r for r in records if r.parse_status == "OK"]
    mapped_cells = [r.normalized.get(c) for r in ok for c in column_map]
    num_cols = [c for c in column_map if VARIABLES[c]["numeric"]]
    with_unit = [c for c in num_cols if columns[column_map[c]]["unit"]]
    quality = dict(
        records=len(records),
        parseability=round(len(ok) / len(records), 3) if records else None,
        completeness_mapped_columns=(round(sum(v is not None for v in mapped_cells) / len(mapped_cells), 3)
                                     if mapped_cells else None),
        unit_completeness=round(len(with_unit) / len(num_cols), 3) if num_cols else None,
        provenance_completeness=round(sum([bool(source_url or inv.source_url), True, True, inv.nasa_verified]) / 4, 2),
        sentinel_candidate_columns=len(sentinel_hits), sentinel_values_excluded=sum(sentinel_hits.values()),
    )
    status = "FAILED" if fatal and not records else ("WARNINGS" if warnings else "OK")
    sf = SourceFile(investigation_id=inv.id, filename=Path(filename).name, stored_path=str(stored),
                    source_url=source_url, sha256=sha, size_bytes=len(raw), encoding=encoding,
                    delimiter=delimiter, parse_status=status, row_count=len(records), columns=columns,
                    column_map=column_map, warnings=warnings, data_quality=quality,
                    is_synthetic=is_synthetic or inv.is_synthetic, pipeline_version=config.PIPELINE_VERSION)
    sf.records = records
    db.add(sf)
    db.commit()
    return sf
