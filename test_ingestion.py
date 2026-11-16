import hashlib

import pytest

from app.demo import SYNTHETIC_CSV, load_synthetic
from app.ingestion import DuplicateFileError, IngestionError, ingest_bytes
from app.models import DataRecord, Investigation, SourceFile


def make_inv(db, **kw):
    inv = Investigation(title=kw.pop("title", "SYNTHETIC - NOT NASA DATA: test"), is_synthetic=True, **kw)
    db.add(inv); db.commit()
    return inv


def test_database_initialises_with_foreign_keys(db):
    from sqlalchemy import text
    assert db.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_database_additively_upgrades_legacy_record_table(db, env):
    from sqlalchemy import inspect, text
    from app import database
    from app.models import DataRecord
    inv = make_inv(db)
    sf = ingest_bytes(db, b"Flame spread rate (mm/s)\n2\n", "before-upgrade.csv", inv.id)
    record_id = db.query(DataRecord).filter_by(source_file_id=sf.id).one().id
    with database.engine.begin() as conn:
        conn.execute(text("ALTER TABLE data_records DROP COLUMN numeric_status"))
    database.init_db(f"sqlite:///{env / 't.db'}")
    database.init_db(f"sqlite:///{env / 't.db'}")  # repeated startup/upgrade must remain safe
    assert "numeric_status" in {c["name"] for c in inspect(database.engine).get_columns("data_records")}
    upgraded_session = database.SessionLocal()
    try:
        preserved = upgraded_session.get(DataRecord, record_id)
        assert preserved.raw_values == ["2"] and preserved.normalized["flame_spread_rate"] == 2.0
        assert preserved.numeric_status == {}
    finally:
        upgraded_session.close()


def test_sha256_and_raw_bytes_preserved(db):
    inv = make_inv(db)
    raw = SYNTHETIC_CSV.encode()
    sf = ingest_bytes(db, raw, "a.csv", inv.id)
    assert sf.sha256 == hashlib.sha256(raw).hexdigest()
    from pathlib import Path
    assert Path(sf.stored_path).read_bytes() == raw


def test_duplicate_file_rejected_not_overwritten(db):
    inv = make_inv(db)
    ingest_bytes(db, b"a,b\n1,2\n", "a.csv", inv.id)
    with pytest.raises(DuplicateFileError):
        ingest_bytes(db, b"a,b\n1,2\n", "other_name.csv", inv.id)


def test_missing_values_stay_missing_not_zero(db):
    inv = make_inv(db)
    sf = ingest_bytes(db, SYNTHETIC_CSV.encode(), "a.csv", inv.id)
    r4 = db.query(DataRecord).filter_by(source_file_id=sf.id, record_number=4).one()
    assert r4.normalized["flame_spread_rate"] is None
    assert r4.raw_values[5] == ""          # original empty string preserved


def test_sentinel_masked_from_analysis_but_raw_value_preserved(db):
    inv = make_inv(db)
    sf = ingest_bytes(db, SYNTHETIC_CSV.encode(), "a.csv", inv.id)
    r5 = db.query(DataRecord).filter_by(source_file_id=sf.id, record_number=5).one()
    assert r5.normalized["flame_spread_rate"] is None
    assert r5.numeric_status["flame_spread_rate"] == "SENTINEL_MISSING"
    assert r5.raw_values[5] == "-999"
    assert any("sentinel" in i for i in r5.issues)


def test_non_numeric_has_explicit_parse_status(db):
    inv = make_inv(db)
    sf = ingest_bytes(db, b"Flame spread rate (mm/s)\nfast\n", "n.csv", inv.id)
    record = db.query(DataRecord).filter_by(source_file_id=sf.id).one()
    assert record.normalized["flame_spread_rate"] is None
    assert record.numeric_status["flame_spread_rate"] == "NON_NUMERIC"


@pytest.mark.parametrize("value", ["nan", "NaN", "inf", "-Infinity", "1e9999"])
def test_non_finite_numbers_are_masked(db, value):
    inv = make_inv(db)
    sf = ingest_bytes(db, f"Flame spread rate (mm/s)\n{value}\n".encode(), "nf.csv", inv.id)
    record = db.query(DataRecord).filter_by(source_file_id=sf.id).one()
    assert record.normalized["flame_spread_rate"] is None
    assert record.numeric_status["flame_spread_rate"] == "NON_FINITE"


def test_malformed_quoted_csv_fails_without_orphan_file_or_rows(db, env):
    inv = make_inv(db)
    raw = b'Flame spread rate (mm/s)\n"unterminated\n'
    with pytest.raises(IngestionError, match="CSV parse error"):
        ingest_bytes(db, raw, "bad.csv", inv.id)
    assert db.query(SourceFile).count() == 0
    assert db.query(DataRecord).count() == 0
    assert list((env / "raw").iterdir()) == []


def test_database_commit_failure_rolls_back_rows_and_new_raw_file(db, env, monkeypatch):
    inv = make_inv(db)
    def fail_commit():
        raise RuntimeError("simulated commit failure")
    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="simulated commit failure"):
        ingest_bytes(db, b"Flame spread rate (mm/s)\n1\n", "commit-fail.csv", inv.id)
    assert db.query(SourceFile).count() == 0
    assert db.query(DataRecord).count() == 0
    assert list((env / "raw").iterdir()) == []


def test_header_only_file_is_imported_as_empty_file_with_header(db):
    inv = make_inv(db)
    sf = ingest_bytes(db, b"Flame spread rate (mm/s)\n", "header.csv", inv.id)
    assert sf.row_count == 0 and sf.columns[0]["canonical"] == "flame_spread_rate"


def test_utf8_bom_tsv_and_duplicate_data_rows_preserve_raw_values(db):
    inv = make_inv(db)
    raw = "\ufeffPressure (kPa)\tFlame spread rate (mm/s)\n-1.25\t0.125\n-1.25\t0.125\n".encode("utf-8")
    sf = ingest_bytes(db, raw, "repeat.tsv", inv.id)
    rows = db.query(DataRecord).filter_by(source_file_id=sf.id).order_by(DataRecord.record_number).all()
    assert sf.encoding == "utf-8" and sf.delimiter == "\t"
    assert sf.sha256 == hashlib.sha256(raw).hexdigest()
    assert len(rows) == 2 and rows[0].raw_values == rows[1].raw_values
    assert rows[0].normalized["pressure"] == -1.25 and rows[0].normalized["flame_spread_rate"] == 0.125


def test_malformed_rows_kept_with_status_and_locators(db):
    inv = make_inv(db)
    sf = ingest_bytes(db, SYNTHETIC_CSV.encode(), "a.csv", inv.id)
    recs = {r.record_number: r for r in db.query(DataRecord).filter_by(source_file_id=sf.id)}
    assert len(recs) == 7
    assert recs[6].parse_status == "SHORT" and recs[6].raw_values[-1] is None
    assert recs[7].parse_status == "LONG" and recs[7].extra_cells == ["extra-cell-on-purpose"]
    assert recs[7].line_end == recs[7].line_start + 1      # embedded newline spans two physical lines
    assert sf.parse_status == "WARNINGS"


def test_duplicate_headers_and_unknown_columns_preserved(db):
    inv = make_inv(db)
    sf = ingest_bytes(db, b"Pressure (kPa),Pressure (kPa),Mystery\n1,2,x\n", "d.csv", inv.id)
    assert [c["original"] for c in sf.columns] == ["Pressure (kPa)", "Pressure (kPa)", "Mystery"]
    assert sf.column_map == {"pressure": 0}
    assert any("Duplicate header" in w for w in sf.warnings)
    assert sf.columns[2]["canonical"] is None


def test_unit_from_header_and_override(db):
    inv = make_inv(db)
    sf = ingest_bytes(db, b"Pressure,Oxygen (%)\n1,2\n", "u.csv", inv.id, unit_overrides={"Pressure": "kPa"})
    p, o = sf.columns
    assert (p["unit"], p["unit_source"]) == ("kPa", "USER_SUPPLIED")
    assert (o["unit"], o["unit_source"]) == ("%", "HEADER")


def test_rejects_bad_type_and_empty(db):
    inv = make_inv(db)
    with pytest.raises(IngestionError):
        ingest_bytes(db, b"x", "a.exe", inv.id)
    with pytest.raises(IngestionError):
        ingest_bytes(db, b"", "a.csv", inv.id)


def test_upload_size_limit_rejects_before_raw_or_database_write(db, env, monkeypatch):
    from app import config
    inv = make_inv(db)
    monkeypatch.setattr(config, "MAX_UPLOAD_MB", 0)
    with pytest.raises(IngestionError, match="larger than"):
        ingest_bytes(db, b"x", "large.csv", inv.id)
    assert db.query(SourceFile).count() == 0
    assert db.query(DataRecord).count() == 0
    assert list((env / "raw").iterdir()) == []


def test_latin1_fallback_warns(db):
    inv = make_inv(db)
    sf = ingest_bytes(db, "Material,Pressure (kPa)\nPap\xe9r,1\n".encode("latin-1"), "l.csv", inv.id)
    assert sf.encoding == "latin-1" and any("UTF-8" in w for w in sf.warnings)
