import hashlib

import pytest

from app.demo import SYNTHETIC_CSV, load_synthetic
from app.ingestion import DuplicateFileError, IngestionError, ingest_bytes
from app.models import DataRecord, Investigation


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
    with database.engine.begin() as conn:
        conn.execute(text("ALTER TABLE data_records DROP COLUMN numeric_status"))
    database.init_db(f"sqlite:///{env / 't.db'}")
    assert "numeric_status" in {c["name"] for c in inspect(database.engine).get_columns("data_records")}


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


def test_latin1_fallback_warns(db):
    inv = make_inv(db)
    sf = ingest_bytes(db, "Material,Pressure (kPa)\nPap\xe9r,1\n".encode("latin-1"), "l.csv", inv.id)
    assert sf.encoding == "latin-1" and any("UTF-8" in w for w in sf.warnings)
