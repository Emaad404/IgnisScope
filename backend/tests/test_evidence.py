from app.demo import load_synthetic
from app.evidence import parse_question, run_search
from app.ingestion import ingest_bytes
from app.models import Investigation
from app.schemas import StructuredQuery


def q(**kw):
    kw.setdefault("text", "flame spread test")
    return StructuredQuery(**kw)


def test_parse_question_never_invents_numbers():
    s = parse_question("Flame spread rate of PMMA versus oxygen on the ISS")
    assert s.material == "PMMA" and "oxygen_fraction" in s.required_measurements
    assert s.environment.name == "ISS" and s.environment.provenance == "USER_ASSUMED"
    assert s.target_conditions == []


def test_abstains_when_nothing_indexed(db):
    assert run_search(db, q()) == []


def test_synthetic_result_is_labeled_and_never_direct(db):
    load_synthetic(db)
    r = run_search(db, q(required_measurements=["flame_spread_rate", "pressure"], material="PMMA"))[0]
    assert r["is_synthetic"] and r["nasa_verified"] is False
    assert r["classification"] != "DIRECT"      # gravity context is UNKNOWN, so DIRECT is impossible
    assert 0 <= r["coverage"] <= 1 and 0 <= r["relevance"] <= 1


def test_missing_variable_is_gap_not_zero(db):
    load_synthetic(db)
    r = run_search(db, q(required_measurements=["flame_spread_rate", "temperature"]))[0]
    temp = next(p for p in r["parameters"] if p["variable"] == "temperature")
    assert temp["status"] == "NOT_IN_FILE" and temp["available"] is False and temp["match"] is None
    assert any(g["category"] == "MISSING_VARIABLE" and g["parameter"] == "Temperature" for g in r["gaps"])
    assert r["coverage"] < 1


def test_unit_mismatch_not_compared(db):
    load_synthetic(db)
    r = run_search(db, q(target_conditions=[{"variable": "pressure", "value": 14.7, "unit": "psi"}]))[0]
    p = next(p for p in r["parameters"] if p["variable"] == "pressure")
    assert p["status"] == "UNIT_NOT_COMPARABLE" and p["match"] is None


def test_condition_mismatch_detected(db):
    load_synthetic(db)
    r = run_search(db, q(target_conditions=[{"variable": "pressure", "value": 20, "unit": "kPa"}]))[0]
    assert "Pressure" in r["mismatches"]
    assert any(g["category"] == "CONDITION_MISMATCH" for g in r["gaps"])


def test_target_match_gives_high_relevance(db):
    load_synthetic(db)
    r = run_search(db, q(target_conditions=[{"variable": "pressure", "value": 101.3, "unit": "kPa"}]))[0]
    p = next(p for p in r["parameters"] if p["variable"] == "pressure")
    assert p["match"] >= 0.5 and p["status"] == "MATCH"


def test_unrelated_file_is_unknown(db):
    inv = Investigation(title="Unrelated pump test"); db.add(inv); db.commit()
    ingest_bytes(db, b"Pressure (kPa),Temperature (C)\n1,2\n", "pump.csv", inv.id)
    r = run_search(db, q())[0]
    assert r["classification"] == "UNKNOWN"


def test_direct_possible_only_with_source_supported_gravity(db):
    inv = Investigation(title="Flame spread study", gravity_context="microgravity",
                        gravity_provenance="SOURCE_SUPPORTED", nasa_verified=True)
    db.add(inv); db.commit()
    ingest_bytes(db, b"Flame spread rate (mm/s),Pressure (kPa)\n1,100\n2,101\n", "f.csv", inv.id)
    r = run_search(db, q(required_measurements=["flame_spread_rate", "pressure"]))[0]
    assert r["classification"] == "DIRECT"
    inv.gravity_provenance = "USER_ASSUMED"; db.commit()
    assert run_search(db, q(required_measurements=["flame_spread_rate", "pressure"]))[0]["classification"] == "ANALOGOUS"


def test_terrestrial_one_g_never_direct_for_microgravity(db):
    inv = Investigation(title="Flame spread terrestrial study", gravity_context="terrestrial 1g",
                        gravity_provenance="SOURCE_SUPPORTED")
    db.add(inv); db.commit()
    ingest_bytes(db, b"Flame spread rate (mm/s),Pressure (kPa)\n1,100\n2,101\n", "earth.csv", inv.id)
    r = run_search(db, q(required_measurements=["flame_spread_rate", "pressure"]))[0]
    assert r["classification"] == "ANALOGOUS"
    assert any("terrestrial/1g" in reason for reason in r["reasons"])


def test_non_microgravity_context_cannot_be_direct(db):
    inv = Investigation(title="Flame spread study", gravity_context="1g", gravity_provenance="SOURCE_SUPPORTED")
    db.add(inv); db.commit()
    ingest_bytes(db, b"Flame spread rate (mm/s),Pressure (kPa)\n1,100\n2,101\n", "oneg.csv", inv.id)
    assert run_search(db, q(required_measurements=["flame_spread_rate", "pressure"]))[0]["classification"] == "ANALOGOUS"


def test_variable_aliases_and_nasa_attestation_label(db):
    from app.variables import match_variable
    assert match_variable("Oxidizer_Fraction") == "oxygen_fraction"
    assert match_variable("Gas velocity (cm/s)") == "flow_velocity"
    inv = Investigation(title="Flame spread imported", nasa_verified=True,
                        gravity_context="microgravity on ISS", gravity_provenance="SOURCE_SUPPORTED")
    db.add(inv); db.commit()
    sf = ingest_bytes(db, b"Flame spread rate (mm/s),Pressure (kPa)\n1,100\n", "flame.csv", inv.id)
    r = run_search(db, q(required_measurements=["flame_spread_rate", "pressure"]))[0]
    assert r["provenance_label"].startswith("USER-ATTESTED")
    assert r["record_references"][0]["record_number"] == 1
    assert r["source_file_id"] == sf.id
