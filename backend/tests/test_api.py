def test_health_and_empty_states(client):
    assert client.get("/api/health").json()["status"] == "ok"
    d = client.get("/api/dashboard").json()
    assert d["investigations"] == 0 and d["records"] == 0
    r = client.post("/api/evidence/search", json={"text": "flame spread of PMMA"})
    assert r.status_code == 201 and r.json()["results"] == [] and "Not found in the indexed corpus" in r.json()["note"]


def test_full_flow_import_search_report(client):
    inv = client.post("/api/investigations", json={"title": "SYNTHETIC - NOT NASA DATA: api test",
                                                   "is_synthetic": True}).json()
    csv = b"Material,Flame spread rate (mm/s),Pressure (kPa)\nPMMA,1.0,101\nPMMA,,101\n"
    up = client.post("/api/ingestion/import", data={"investigation_id": inv["id"]},
                     files={"file": ("t.csv", csv, "text/csv")})
    assert up.status_code == 201 and len(up.json()["sha256"]) == 64
    again = client.post("/api/ingestion/import", data={"investigation_id": inv["id"]},
                        files={"file": ("t.csv", csv, "text/csv")})
    assert again.status_code == 409
    s = client.post("/api/evidence/search", json={"text": "flame spread PMMA", "material": "PMMA",
                                                  "required_measurements": ["flame_spread_rate"]}).json()
    assert s["results"][0]["classification"] in ("ANALOGOUS", "LIMITED")
    recs = client.get(f"/api/files/{up.json()['id']}/records").json()
    assert recs["total"] == 2 and recs["records"][1]["raw_values"][1] == ""
    assert recs["records"][0]["numeric_status"]["flame_spread_rate"] == "PARSED"
    rep = client.get(f"/api/reports/{s['question_id']}").json()
    assert rep["controlled_counterfactual"] is False and rep["source_references"][0]["is_synthetic"] is True
    assert rep["source_references"][0]["sha256"] == up.json()["sha256"]
    assert "synthetic" in rep["executive_summary"].lower()
    assert rep["search_scope"]["synthetic_files_indexed"] == 1
    assert rep["search_scope"]["user_imported_files_indexed"] == 0
    assert rep["search_scope"]["nasa_source_verified_files_indexed"] == 0
    assert rep["source_references"][0]["nasa_verification_status"] == "SYNTHETIC_NOT_NASA"
    pdf = client.get(f"/api/reports/{s['question_id']}/pdf")
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"


def test_validation_errors(client):
    assert client.post("/api/evidence/search", json={"text": "x"}).status_code == 422
    bad = client.post("/api/evidence/search", json={"text": "flame spread", "target_conditions": [
        {"variable": "pressure", "value": 1}]})
    assert bad.status_code == 422        # unit is required
    assert client.get("/api/reports/999").status_code == 404
    r = client.post("/api/ingestion/import", data={"investigation_id": 99},
                    files={"file": ("a.csv", b"a\n1\n", "text/csv")})
    assert r.status_code == 422


def test_demo_loader_is_idempotent(client):
    a = client.post("/api/demo/synthetic").json()
    b = client.post("/api/demo/synthetic").json()
    assert a["created"] is True and b["created"] is False
