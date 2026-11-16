def test_health_and_empty_states(client):
    assert client.get("/api/health").json()["status"] == "ok"
    d = client.get("/api/dashboard").json()
    assert d["investigations"] == 0 and d["records"] == 0
    r = client.post("/api/evidence/search", json={"text": "flame spread of PMMA"})
    assert r.status_code == 201 and r.json()["results"] == [] and "No eligible source files" in r.json()["note"]


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
    assert "SYNTHETIC" in rep["executive_summary"]
    assert rep["search_scope"]["synthetic_files_indexed"] == 1
    assert rep["search_scope"]["user_imported_files_indexed"] == 0
    assert rep["search_scope"]["nasa_source_verified_files_indexed"] == 0
    assert rep["source_references"][0]["nasa_verification_status"] == "SYNTHETIC_NOT_NASA"
    pdf = client.get(f"/api/reports/{s['question_id']}/pdf")
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"


def test_validation_errors(client):
    assert client.post("/api/evidence/search", json={"text": "x"}).status_code == 422
    assert client.post("/api/investigations", json={"title": "Old attestation name", "nasa_verified": True}).status_code == 422
    bad = client.post("/api/evidence/search", json={"text": "flame spread", "target_conditions": [
        {"variable": "pressure", "value": 1}]})
    assert bad.status_code == 422        # unit is required
    nonfinite = client.post("/api/evidence/search",
                            content='{"text":"flame spread","target_conditions":[{"variable":"pressure","value":1e9999,"unit":"kPa"}]}',
                            headers={"content-type": "application/json"})
    assert nonfinite.status_code == 422
    detail = nonfinite.json()["detail"][0]
    assert detail["type"] == "finite_number" and detail["input"] == "inf"
    assert client.get("/api/reports/999").status_code == 404
    assert client.get("/api/reports/999/pdf").status_code == 404
    assert client.get("/api/questions/999").status_code == 404
    assert client.get("/api/investigations/999").status_code == 404
    assert client.get("/api/files/999/records").status_code == 404
    assert client.get("/api/files/1/records?offset=-1").status_code == 422
    assert client.get("/api/files/1/records?limit=201").status_code == 422
    assert client.get("/api/files/1/records?status=INVALID").status_code == 422
    assert client.post("/api/health").status_code == 405
    assert client.post("/api/ingestion/import", data={"investigation_id": 99,
                                                       "unit_overrides": '{"a": ["bad"]}'},
                       files={"file": ("x.csv", b"a\n1\n", "text/csv")}).status_code == 422
    r = client.post("/api/ingestion/import", data={"investigation_id": 99},
                    files={"file": ("a.csv", b"a\n1\n", "text/csv")})
    assert r.status_code == 422


def test_all_read_routes_and_report_downloads(client):
    assert client.get("/api/investigations").json() == []
    assert client.get("/api/variables").status_code == 200
    assert client.post("/api/questions/parse", json={"text": "flame spread rate and oxygen"}).status_code == 200
    assert client.get("/api/methodology").json()["classes"]["DIRECT"]
    inv = client.post("/api/investigations", json={"title": "Imported test investigation",
                                                       "user_attested_nasa_page_check": True,
                                                       "gravity_context": "microgravity",
                                                       "gravity_provenance": "SOURCE_SUPPORTED"}).json()
    assert inv["user_attested_nasa_page_check"] is True and inv["nasa_source_independently_verified"] is False
    assert inv["gravity_context_status"] == "USER_REPORTED_SOURCE_SUPPORTED_UNVERIFIED"
    assert "nasa_verified" not in inv
    assert client.get(f"/api/investigations/{inv['id']}").json()["id"] == inv["id"]
    search = client.post("/api/evidence/search", json={"text": "flame spread"}).json()
    assert client.get(f"/api/questions/{search['question_id']}").status_code == 200
    downloaded = client.get(f"/api/reports/{search['question_id']}?download=true")
    assert downloaded.status_code == 200 and downloaded.headers["content-type"].startswith("application/json")
    assert downloaded.json()["controlled_counterfactual"] is False
    assert client.get(f"/api/reports/{search['question_id']}/pdf").content.startswith(b"%PDF-")
    assert client.post("/api/methodology").status_code == 405
    assert client.post("/api/evidence/search", content="{", headers={"content-type": "application/json"}).status_code == 422


def test_user_supplied_import_filename_is_reduced_to_basename(client):
    inv = client.post("/api/investigations", json={"title": "Upload path test"}).json()
    response = client.post("/api/ingestion/import", data={"investigation_id": inv["id"]},
                          files={"file": ("..\\..\\secret.csv", b"Mystery\n1\n", "text/csv")})
    assert response.status_code == 201
    assert response.json()["filename"] == "secret.csv"
    assert "stored_path" not in response.json()


def test_user_imported_report_counts_and_attestation_provenance(client):
    inv = client.post("/api/investigations", json={"title": "User imported flame test",
        "user_attested_nasa_page_check": True}).json()
    upload = client.post("/api/ingestion/import", data={"investigation_id": inv["id"]},
        files={"file": ("flame.csv", b"Flame spread rate (mm/s)\n1.2\n", "text/csv")})
    assert upload.status_code == 201
    search = client.post("/api/evidence/search", json={"text": "flame spread"}).json()
    report = client.get(f"/api/reports/{search['question_id']}").json()
    scope = report["search_scope"]
    assert (scope["user_imported_files_indexed"], scope["synthetic_files_indexed"],
            scope["nasa_source_verified_files_indexed"], scope["user_attested_files_indexed"]) == (1, 0, 0, 1)
    source = report["source_references"][0]
    assert source["user_attested_nasa_page_check"] is True
    assert source["nasa_source_independently_verified"] is False
    assert source["nasa_verification_status"] == "USER_ATTESTED_UNVERIFIED"


def test_excluding_synthetic_records_gives_zero_eligible_report_scope(client):
    client.post("/api/demo/synthetic")
    search = client.post("/api/evidence/search", json={"text": "flame spread", "include_synthetic": False}).json()
    assert search["results"] == []
    report = client.get(f"/api/reports/{search['question_id']}").json()
    assert report["search_scope"]["source_files_indexed"] == 0
    assert report["search_scope"]["records_indexed"] == 0
    assert report["executive_summary"].find("No eligible source files") >= 0


def test_demo_loader_is_idempotent(client):
    a = client.post("/api/demo/synthetic").json()
    b = client.post("/api/demo/synthetic").json()
    assert a["created"] is True and b["created"] is False
