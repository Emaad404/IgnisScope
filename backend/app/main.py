import json
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import config, database
from .demo import load_synthetic
from .evidence import parse_question, run_search
from .ingestion import DuplicateFileError, IngestionError, ingest_bytes
from .models import DataRecord, EvidenceResult, Investigation, ResearchQuestion, SourceFile
from .reports import build_report, render_pdf
from .schemas import InvestigationIn, ParseRequest, StructuredQuery
from .variables import MEASUREMENT_CHOICES, VARIABLES

log = logging.getLogger("fif")


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield


app = FastAPI(title="Flame in Freefall API", version="0.1.0", lifespan=lifespan,
              description="Research-support tool. Not NASA-endorsed. Not a certified fire-risk predictor.")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
get_db = database.get_db


@app.exception_handler(Exception)
async def unhandled(_, exc: Exception):
    log.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"detail": "Internal server error. See server log."})


def _inv(i: Investigation) -> dict:
    return dict(id=i.id, psi_id=i.psi_id, title=i.title, description=i.description, source_url=i.source_url,
                nasa_verified=i.nasa_verified, is_synthetic=i.is_synthetic, gravity_context=i.gravity_context,
                gravity_provenance=i.gravity_provenance, created_at=i.created_at.isoformat(),
                n_files=len(i.files))


def _file(f: SourceFile) -> dict:
    return dict(id=f.id, investigation_id=f.investigation_id, filename=f.filename, source_url=f.source_url,
                sha256=f.sha256, size_bytes=f.size_bytes, encoding=f.encoding, delimiter=f.delimiter,
                imported_at=f.imported_at.isoformat(), parse_status=f.parse_status, row_count=f.row_count,
                columns=f.columns, column_map=f.column_map, warnings=f.warnings, data_quality=f.data_quality,
                is_synthetic=f.is_synthetic, pipeline_version=f.pipeline_version)


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.query(Investigation).count()
    return dict(status="ok", pipeline_version=config.PIPELINE_VERSION)


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)):
    files = db.query(SourceFile).all()
    return dict(
        investigations=db.query(Investigation).count(),
        source_files=len(files),
        records=db.query(func.count(DataRecord.id)).scalar(),
        malformed_records=db.query(func.count(DataRecord.id)).filter(DataRecord.parse_status != "OK").scalar(),
        synthetic_files=sum(f.is_synthetic for f in files),
        user_imported_files=sum(not f.is_synthetic for f in files),
        files_with_warnings=sum(f.parse_status == "WARNINGS" for f in files),
        recent_files=[_file(f) for f in sorted(files, key=lambda x: x.id, reverse=True)[:5]],
    )


@app.get("/api/investigations")
def list_investigations(q: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Investigation)
    if q:
        like = f"%{q}%"
        query = query.filter(Investigation.title.ilike(like) | Investigation.description.ilike(like)
                             | Investigation.psi_id.ilike(like))
    return [_inv(i) for i in query.order_by(Investigation.id)]


@app.post("/api/investigations", status_code=201)
def create_investigation(body: InvestigationIn, db: Session = Depends(get_db)):
    inv = Investigation(**body.model_dump())
    db.add(inv); db.commit()
    return _inv(inv)


@app.get("/api/investigations/{inv_id}")
def get_investigation(inv_id: int, db: Session = Depends(get_db)):
    inv = db.get(Investigation, inv_id)
    if not inv:
        raise HTTPException(404, "Investigation not found")
    return dict(**_inv(inv), files=[_file(f) for f in inv.files])


@app.get("/api/files/{file_id}/records")
def file_records(file_id: int, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
                 status: str | None = None, db: Session = Depends(get_db)):
    f = db.get(SourceFile, file_id)
    if not f:
        raise HTTPException(404, "Source file not found")
    q = db.query(DataRecord).filter_by(source_file_id=file_id)
    if status:
        q = q.filter_by(parse_status=status)
    total = q.count()
    rows = q.order_by(DataRecord.record_number).offset(offset).limit(limit).all()
    return dict(total=total, offset=offset, limit=limit, file=_file(f), records=[
        dict(id=r.id, record_number=r.record_number, line_start=r.line_start, line_end=r.line_end,
             parse_status=r.parse_status, issues=r.issues, raw_values=r.raw_values,
             extra_cells=r.extra_cells, normalized=r.normalized, numeric_status=r.numeric_status) for r in rows])


@app.post("/api/ingestion/import", status_code=201)
async def import_csv(file: UploadFile = File(...), investigation_id: int = Form(...),
                     source_url: str | None = Form(None), unit_overrides: str | None = Form(None),
                     db: Session = Depends(get_db)):
    raw = await file.read(config.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    try:
        overrides = json.loads(unit_overrides) if unit_overrides else None
        if overrides is not None and not isinstance(overrides, dict):
            raise ValueError
    except ValueError:
        raise HTTPException(422, "unit_overrides must be a JSON object like {\"Pressure\": \"kPa\"}")
    try:
        sf = ingest_bytes(db, raw, file.filename or "upload.csv", investigation_id, source_url, overrides)
    except DuplicateFileError as e:
        raise HTTPException(409, str(e))
    except IngestionError as e:
        raise HTTPException(422, str(e))
    return _file(sf)


@app.post("/api/demo/synthetic", status_code=201)
def demo_synthetic(db: Session = Depends(get_db)):
    return load_synthetic(db)


@app.get("/api/variables")
def variables():
    return dict(measurements=[dict(key=k, label=VARIABLES[k]["label"]) for k in MEASUREMENT_CHOICES],
                targets=[dict(key=k, label=VARIABLES[k]["label"]) for k in
                         ("oxygen_fraction", "pressure", "flow_velocity", "temperature", "thickness", "width")])


@app.post("/api/questions/parse")
def parse(body: ParseRequest):
    return parse_question(body.text).model_dump()


@app.post("/api/evidence/search", status_code=201)
def search(q: StructuredQuery, db: Session = Depends(get_db)):
    results = run_search(db, q)
    rq = ResearchQuestion(text=q.text, structured=q.model_dump())
    db.add(rq); db.flush()
    for r in results:
        db.add(EvidenceResult(question_id=rq.id, investigation_id=r["investigation_id"],
                              source_file_id=r["source_file_id"], rank=r["rank"], classification=r["classification"],
                              relevance=r["relevance"], coverage=r["coverage"], payload=r))
    db.commit()
    return dict(question_id=rq.id, query=q.model_dump(), results=results,
                note=None if results else "Not found in the indexed corpus. Nothing is indexed yet.")


@app.get("/api/questions/{qid}")
def get_question(qid: int, db: Session = Depends(get_db)):
    rq = db.get(ResearchQuestion, qid)
    if not rq:
        raise HTTPException(404, "Question not found")
    return dict(question_id=rq.id, query=rq.structured,
                results=[r.payload for r in sorted(rq.results, key=lambda r: r.rank)])


@app.get("/api/reports/{qid}")
def report_json(qid: int, download: bool = False, db: Session = Depends(get_db)):
    try:
        rep = build_report(db, qid)
    except KeyError:
        raise HTTPException(404, "Question not found")
    if download:
        return Response(json.dumps(rep, indent=2), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="mission_evidence_brief_{qid}.json"'})
    return rep


@app.get("/api/reports/{qid}/pdf")
def report_pdf(qid: int, db: Session = Depends(get_db)):
    try:
        rep = build_report(db, qid)
    except KeyError:
        raise HTTPException(404, "Question not found")
    return Response(render_pdf(rep), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="mission_evidence_brief_{qid}.pdf"'})


@app.get("/api/methodology")
def methodology():
    return dict(methodology_version=config.METHODOLOGY_VERSION, pipeline_version=config.PIPELINE_VERSION,
                formulas=dict(coverage="C = sum(w_i * a_i) / sum(w_i)",
                              relevance="R = sum(w_i * m_i * a_i) / sum(w_i * a_i); null when nothing is available"),
                weights={k: v["weight"] for k, v in VARIABLES.items()},
                classes=dict(
                    DIRECT="phenomenon signal, coverage >= 0.8, all required measurements, no mismatch, comparable units, source-supported explicit microgravity context, non-synthetic file, and user-attested NASA page check (not independently verified)",
                    ANALOGOUS="phenomenon signal and coverage >= 0.5 but a limit above is not met",
                    LIMITED="phenomenon signal and 0 < coverage < 0.5",
                    UNKNOWN="no phenomenon signal or nothing available and comparable"),
                caveats=["Application heuristic, not scientifically validated.",
                         "Not an official NASA classification.", "controlled_counterfactual = false"])
