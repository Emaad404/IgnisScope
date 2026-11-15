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
    assert r["is_synthetic"] and r["user_attested_nasa_page_check"] is False
    assert r["nasa_source_independently_verified"] is False
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
    inv = Investigation(title="Flame spread pressure test")
    db.add(inv); db.commit()
    ingest_bytes(db, b"Pressure absolute (kPa),Flame spread rate (mm/s)\n100,1.2\n", "pressure.csv", inv.id)
    r = run_search(db, q(target_conditions=[{"variable": "pressure", "value": 20, "unit": "kPa",
                                             "definition": "ABSOLUTE_PRESSURE"}]))[0]
    assert "Pressure" in r["mismatches"]
    assert any(g["category"] == "CONDITION_MISMATCH" for g in r["gaps"])


def test_target_match_gives_high_relevance(db):
    inv = Investigation(title="Flame spread pressure target")
    db.add(inv); db.commit()
    ingest_bytes(db, b"Pressure absolute (kPa),Flame spread rate (mm/s)\n101.3,1.2\n", "pressure2.csv", inv.id)
    r = run_search(db, q(target_conditions=[{"variable": "pressure", "value": 101.3, "unit": "kPa",
                                             "definition": "ABSOLUTE_PRESSURE"}]))[0]
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


def test_incomplete_required_measurement_rows_block_direct(db):
    inv = Investigation(title="Flame spread incomplete rows", gravity_context="microgravity",
                        gravity_provenance="SOURCE_SUPPORTED", nasa_verified=True)
    db.add(inv); db.commit()
    ingest_bytes(db, b"Flame spread rate (mm/s),Pressure (kPa)\n1.0,100\n,101\n", "partial.csv", inv.id)
    result = run_search(db, q(required_measurements=["flame_spread_rate", "pressure"]))[0]
    assert result["classification"] == "ANALOGOUS"
    spread = next(p for p in result["parameters"] if p["variable"] == "flame_spread_rate")
    assert spread["record_completeness"] == 0.5


def test_half_matching_target_values_do_not_qualify_direct(db):
    inv = Investigation(title="Flame spread partial target", gravity_context="microgravity",
                        gravity_provenance="SOURCE_SUPPORTED", nasa_verified=True)
    db.add(inv); db.commit()
    ingest_bytes(db, b"Pressure absolute (kPa),Flame spread rate (mm/s)\n100,1.0\n200,1.1\n", "mixed.csv", inv.id)
    result = run_search(db, q(target_conditions=[{"variable": "pressure", "value": 100, "unit": "kPa",
                                                  "definition": "ABSOLUTE_PRESSURE"}]))[0]
    assert result["classification"] == "ANALOGOUS"
    assert any("do not match every" in r for r in result["reasons"])


def test_missing_target_condition_rows_block_direct(db):
    inv = Investigation(title="Flame spread target missing", gravity_context="microgravity",
                        gravity_provenance="SOURCE_SUPPORTED", nasa_verified=True)
    db.add(inv); db.commit()
    ingest_bytes(db, b"Pressure absolute (kPa),Flame spread rate (mm/s)\n100,1.0\n,1.1\n", "missing-pressure.csv", inv.id)
    result = run_search(db, q(target_conditions=[{"variable": "pressure", "value": 100, "unit": "kPa",
                                                  "definition": "ABSOLUTE_PRESSURE"}]))[0]
    assert result["classification"] == "ANALOGOUS"
    pressure = next(p for p in result["parameters"] if p["variable"] == "pressure")
    assert pressure["n_present"] == 1 and pressure["n_records"] == 2


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


def test_explicit_negation_of_microgravity_blocks_direct(db):
    inv = Investigation(title="Flame spread ground study", gravity_context="not microgravity; terrestrial 1g",
                        gravity_provenance="SOURCE_SUPPORTED", nasa_verified=True)
    db.add(inv); db.commit()
    ingest_bytes(db, b"Flame spread rate (mm/s),Pressure (kPa)\n1,100\n", "negated.csv", inv.id)
    assert run_search(db, q(required_measurements=["flame_spread_rate", "pressure"]))[0]["classification"] == "ANALOGOUS"


def test_unknown_lunar_mars_and_conflicting_gravity_never_direct(db):
    contexts = [
        (None, "UNKNOWN"),
        ("lunar surface gravity", "SOURCE_SUPPORTED"),
        ("Mars surface gravity", "SOURCE_SUPPORTED"),
        ("microgravity on ISS; terrestrial 1g reference", "SOURCE_SUPPORTED"),
    ]
    for index, (context, provenance) in enumerate(contexts):
        inv = Investigation(title=f"Flame spread context case {index}", gravity_context=context,
                            gravity_provenance=provenance, nasa_verified=True)
        db.add(inv); db.commit()
        raw = f"Flame spread rate (mm/s),Pressure (kPa)\n{index + 1},100\n".encode()
        ingest_bytes(db, raw, f"ctx{index}.csv", inv.id)
    results = run_search(db, q(required_measurements=["flame_spread_rate", "pressure"]))
    assert len(results) == len(contexts)
    assert all(r["classification"] != "DIRECT" for r in results)


def test_microgravity_evidence_for_other_environment_is_not_direct(db):
    inv = Investigation(title="Flame spread parabolic flight", gravity_context="microgravity during parabolic flight",
                        gravity_provenance="SOURCE_SUPPORTED", nasa_verified=True)
    db.add(inv); db.commit()
    ingest_bytes(db, b"Flame spread rate (mm/s),Pressure (kPa)\n1,100\n", "flight.csv", inv.id)
    query = q(required_measurements=["flame_spread_rate", "pressure"],
              environment={"name": "ISS", "provenance": "USER_ASSUMED"})
    assert run_search(db, query)[0]["classification"] == "ANALOGOUS"


def test_synthetic_microgravity_claim_never_direct(db):
    inv = Investigation(title="Synthetic flame spread", is_synthetic=True, nasa_verified=True,
                        gravity_context="microgravity", gravity_provenance="SOURCE_SUPPORTED")
    db.add(inv); db.commit()
    ingest_bytes(db, b"Flame spread rate (mm/s),Pressure (kPa)\n1,100\n", "syn-micro.csv", inv.id)
    result = run_search(db, q(required_measurements=["flame_spread_rate", "pressure"]))[0]
    assert result["classification"] == "ANALOGOUS"
    assert result["provenance_label"].startswith("SYNTHETIC")


def test_sentinel_only_values_are_unavailable_and_do_not_form_summary(db):
    inv = Investigation(title="Flame spread sentinel test")
    db.add(inv); db.commit()
    ingest_bytes(db, b"Flame spread rate (mm/s)\n-999\n-9999\n-99999\n", "sentinels.csv", inv.id)
    result = run_search(db, q(required_measurements=["flame_spread_rate"]))[0]
    param = result["parameters"][0]
    assert result["classification"] == "UNKNOWN"
    assert param["status"] == "ALL_MISSING" and param["value_summary"] is None
    assert param["parse_status_counts"]["SENTINEL_MISSING"] == 3
    assert len(result["record_references"]) == 3
    assert result["record_references_total"] == 3 and result["record_references_truncated"] is False
    assert all(ref["numeric_status"]["flame_spread_rate"] == "SENTINEL_MISSING"
               for ref in result["record_references"])


def test_oxygen_fraction_definitions_are_not_silently_compared(db):
    inv = Investigation(title="Flame spread oxygen definition")
    db.add(inv); db.commit()
    ingest_bytes(db, b"Oxygen mole fraction (%),Flame spread rate (mm/s)\n21,1.2\n", "oxygen.csv", inv.id)
    mismatched = run_search(db, q(target_conditions=[{"variable": "oxygen_fraction", "value": 21,
                                                       "unit": "%", "definition": "VOLUME_FRACTION"}]))[0]
    row = next(p for p in mismatched["parameters"] if p["variable"] == "oxygen_fraction")
    assert row["status"] == "DEFINITION_NOT_COMPARABLE" and row["match"] is None
    matched = run_search(db, q(target_conditions=[{"variable": "oxygen_fraction", "value": 21,
                                                    "unit": "%", "definition": "MOLE_FRACTION"}]))[0]
    row = next(p for p in matched["parameters"] if p["variable"] == "oxygen_fraction")
    assert row["status"] == "MATCH"


def test_oxygen_partial_pressure_is_not_mapped_as_fraction():
    from app.variables import match_variable
    assert match_variable("Oxygen partial pressure (kPa)") is None


def test_bulk_flow_and_free_stream_flow_are_not_silently_compared(db):
    inv = Investigation(title="Flame spread flow definition")
    db.add(inv); db.commit()
    ingest_bytes(db, b"Bulk flow velocity (cm/s),Flame spread rate (mm/s)\n5,1.2\n", "bulk.csv", inv.id)
    result = run_search(db, q(target_conditions=[{"variable": "flow_velocity", "value": 5,
                                                  "unit": "cm/s", "definition": "FREE_STREAM_FLOW"}]))[0]
    param = next(p for p in result["parameters"] if p["variable"] == "flow_velocity")
    assert param["status"] == "DEFINITION_NOT_COMPARABLE" and param["match"] is None


def test_absolute_and_gauge_pressure_are_not_silently_compared(db):
    inv = Investigation(title="Flame spread pressure reference")
    db.add(inv); db.commit()
    ingest_bytes(db, b"Pressure gauge (kPa),Flame spread rate (mm/s)\n5,1.2\n", "gauge.csv", inv.id)
    result = run_search(db, q(target_conditions=[{"variable": "pressure", "value": 5,
                                                  "unit": "kPa", "definition": "ABSOLUTE_PRESSURE"}]))[0]
    param = next(p for p in result["parameters"] if p["variable"] == "pressure")
    assert param["status"] == "DEFINITION_NOT_COMPARABLE" and param["match"] is None


def test_variable_aliases_and_nasa_attestation_label(db):
    from app.variables import match_variable
    assert match_variable("Oxidizer_Fraction") == "oxygen_fraction"
    assert match_variable("Gas velocity (cm/s)") == "flow_velocity"
    assert match_variable("Flame front velocity (mm/s)") == "flame_spread_rate"
    assert match_variable("Attempt ID") is None
    inv = Investigation(title="Flame spread imported", nasa_verified=True,
                        gravity_context="microgravity on ISS", gravity_provenance="SOURCE_SUPPORTED")
    db.add(inv); db.commit()
    sf = ingest_bytes(db, b"Flame spread rate (mm/s),Pressure (kPa)\n1,100\n", "flame.csv", inv.id)
    r = run_search(db, q(required_measurements=["flame_spread_rate", "pressure"]))[0]
    assert r["provenance_label"].startswith("USER-ATTESTED")
    assert r["record_references"][0]["record_number"] == 1
    assert r["source_file_id"] == sf.id
