"""Mission Evidence Brief: JSON and PDF. Built only from stored search results."""
import io
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session
from xml.sax.saxutils import escape

from . import config
from .models import DataRecord, EvidenceResult, Investigation, ResearchQuestion, SourceFile

LIMITATIONS = [
    "This is a research-support tool. It is not a certified fire-risk predictor and is not endorsed by NASA.",
    "Evidence classes (DIRECT, ANALOGOUS, LIMITED, UNKNOWN) are application-defined, not NASA classifications.",
    "Ranking uses a documented heuristic that has not been scientifically validated.",
    "Columns are recognised by header name only. A header match does not prove what was physically measured.",
    "'Not found in the indexed corpus' means absent from the files imported here, not that no experiment exists.",
    "Observational differences between records do not establish cause. controlled_counterfactual = false.",
    "Units are compared only when identical; no unit conversion is performed.",
    "Mission environments (ISS, lunar, Mars) are not interchangeable; selecting one fills no physical values.",
]


def build_report(db: Session, question_id: int) -> dict:
    q = db.get(ResearchQuestion, question_id)
    if q is None:
        raise KeyError(question_id)
    results = [r.payload for r in sorted(q.results, key=lambda r: r.rank)]
    include_synthetic = q.structured.get("include_synthetic", True)
    file_scope = db.query(SourceFile)
    if not include_synthetic:
        file_scope = file_scope.filter(SourceFile.is_synthetic.is_(False))
    eligible_files = file_scope.all()
    eligible_file_ids = [f.id for f in eligible_files]
    invs = db.query(Investigation).filter(Investigation.id.in_(
        [f.investigation_id for f in eligible_files])).all() if eligible_files else []
    n_files = len(eligible_files)
    n_rec = db.query(DataRecord).filter(DataRecord.source_file_id.in_(eligible_file_ids)).count() if eligible_file_ids else 0
    synthetic_files = sum(f.is_synthetic for f in eligible_files)
    synthetic_ids = [f.id for f in eligible_files if f.is_synthetic]
    synthetic_records = db.query(DataRecord).filter(DataRecord.source_file_id.in_(synthetic_ids)).count() if synthetic_ids else 0
    counts = {c: sum(1 for r in results if r["classification"] == c)
              for c in ("DIRECT", "ANALOGOUS", "LIMITED", "UNKNOWN")}
    any_syn = any(r["is_synthetic"] for r in results)
    syn_n = sum(r["is_synthetic"] for r in results)
    source_n = len(results) - syn_n
    if not results:
        summary = ("Not found in the indexed corpus. No eligible source files are indexed for this query, "
                   "so no evidence can be assessed.")
    elif counts["DIRECT"] + counts["ANALOGOUS"] + counts["LIMITED"] == 0:
        summary = ("Insufficient evidence. None of the %d indexed file(s) shows usable flame-spread evidence "
                   "for this question." % len(results))
    else:
        summary = ("%d file(s) assessed: %d DIRECT, %d ANALOGOUS, %d LIMITED, %d UNKNOWN. "
                   "Classes are heuristic; see gaps before drawing any conclusion." %
                   (len(results), counts["DIRECT"], counts["ANALOGOUS"], counts["LIMITED"], counts["UNKNOWN"]))
    if any_syn:
        summary += f" {syn_n} result(s) are synthetic demonstration data, not NASA records."
    if source_n:
        summary += f" {source_n} result(s) are user-imported records; source identity is not independently verified."
    refs = {}
    for r in results:
        refs[r["source_file_id"]] = dict(
            investigation=r["investigation_title"], psi_id=r["psi_id"], nasa_verified=r["nasa_verified"],
            filename=r["source_filename"], sha256=r["sha256"], is_synthetic=r["is_synthetic"],
            provenance_label=r["provenance_label"], nasa_verification_status=(
                "USER_ATTESTED_UNVERIFIED" if r["nasa_verified"] and not r["is_synthetic"] else
                "SYNTHETIC_NOT_NASA" if r["is_synthetic"] else "UNVERIFIED"),
            source_url=db.get(SourceFile, r["source_file_id"]).source_url)
    return dict(
        title="Mission Evidence Brief",
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        pipeline_version=config.PIPELINE_VERSION, methodology_version=config.METHODOLOGY_VERSION,
        controlled_counterfactual=False,
        research_question=q.text, structured_query=q.structured,
        search_scope=dict(investigations_indexed=len(invs), source_files_indexed=n_files, records_indexed=n_rec,
                          synthetic_files_indexed=synthetic_files,
                          user_imported_files_indexed=n_files - synthetic_files,
                          synthetic_records_indexed=synthetic_records,
                          user_imported_records_indexed=n_rec - synthetic_records,
                          nasa_source_verified_files_indexed=0,
                          user_attested_files_indexed=sum(bool(f.investigation.nasa_verified) for f in eligible_files
                                                          if not f.is_synthetic),
                          synthetic_included=include_synthetic),
        indexed_investigations=[dict(id=i.id, title=i.title, psi_id=i.psi_id,
                                     user_attested_nasa_page_check=i.nasa_verified,
                                     nasa_source_independently_verified=False,
                                     is_synthetic=i.is_synthetic) for i in invs],
        executive_summary=summary, class_counts=counts, ranked_evidence=results,
        limitations=LIMITATIONS, source_references=list(refs.values()),
        doi_note="No DOI is listed. DOIs are only included after a human verifies them against the publisher.")


def _p(text, style):
    return Paragraph(escape(str(text)), style)


def render_pdf(rep: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm, title=rep["title"])
    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9, leading=12)
    small = ParagraphStyle("s", parent=body, fontSize=7.5, leading=9.5)
    h1, h2 = ss["Title"], ParagraphStyle("h2", parent=ss["Heading2"], spaceBefore=10)
    st = [_p(rep["title"], h1), _p(f"Generated {rep['generated_at']} | {rep['pipeline_version']} | "
                                   f"{rep['methodology_version']}", small), Spacer(1, 6)]
    if any(r["is_synthetic"] for r in rep["ranked_evidence"]):
        st.append(_p("Contains SYNTHETIC test data. NOT NASA DATA.", ParagraphStyle(
            "w", parent=body, textColor=colors.HexColor("#9a3412"), fontName="Helvetica-Bold")))
    st += [_p("1. Research question", h2), _p(rep["research_question"], body),
           _p("2. Structured interpretation", h2),
           _p(f"Phenomenon: flame spread. Material: {rep['structured_query'].get('material') or 'not specified'}. "
              f"Required measurements: {', '.join(rep['structured_query'].get('required_measurements') or ['flame_spread_rate (default)'])}. "
              f"Environment: {rep['structured_query']['environment'].get('name') or 'none'} "
              f"({rep['structured_query']['environment'].get('provenance')}).", body)]
    sc = rep["search_scope"]
    st += [_p("3. Search scope", h2), _p(f"{sc['investigations_indexed']} investigation(s), {sc['source_files_indexed']} "
                                         f"source file(s), {sc['records_indexed']} record(s) indexed.", body),
           _p("4. Executive summary", h2), _p(rep["executive_summary"], body), _p("5. Ranked evidence", h2)]
    for r in rep["ranked_evidence"]:
        tag = " [SYNTHETIC]" if r["is_synthetic"] else ""
        st.append(_p(f"#{r['rank']} {r['classification']}: {r['investigation_title']}{tag}",
                     ParagraphStyle("h3", parent=body, fontName="Helvetica-Bold", spaceBefore=6)))
        st.append(_p(f"File: {r['source_filename']} (SHA-256 {r['sha256'][:16]}...). Relevance "
                     f"{r['relevance'] if r['relevance'] is not None else 'n/a'}, coverage {r['coverage']}. "
                     f"Records scored {r['records_scored']}, malformed excluded {r['records_excluded_malformed']}.", body))
        st.append(_p("Why: " + " ".join(r["reasons"]) + " " + r["explanation"], body))
        rows = [[_p(x, small) for x in ("Parameter", "Status", "Column / unit", "Match", "Note")]]
        for p in r["parameters"]:
            rows.append([_p(p["label"], small), _p(p["status"], small),
                         _p(f"{p['column'] or '-'} / {('text' if p['variable'] == 'material' else (p['unit'] or 'unit undocumented'))}", small),
                         _p("n/a" if p["match"] is None else f"{p['match']:.2f}", small), _p(p["note"], small)])
        t = Table(rows, colWidths=[30 * mm, 26 * mm, 40 * mm, 12 * mm, 66 * mm], repeatRows=1)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5edf0")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        st += [Spacer(1, 3), t]
    st.append(_p("6. Evidence gaps", h2))
    for r in rep["ranked_evidence"]:
        if not r["gaps"]:
            continue
        st.append(_p(f"{r['source_filename']}", ParagraphStyle("h3b", parent=body, fontName="Helvetica-Bold")))
        rows = [[_p(x, small) for x in ("Parameter", "Category", "Detail", "Limitation")]]
        for g in r["gaps"]:
            rows.append([_p(g["parameter"], small), _p(g["category"], small), _p(g["detail"], small),
                         _p(g["limitation"], small)])
        t = Table(rows, colWidths=[32 * mm, 30 * mm, 56 * mm, 56 * mm], repeatRows=1)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5edf0")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        st += [Spacer(1, 3), t]
    st.append(_p("7. Limitations", h2))
    st += [_p("- " + l, body) for l in rep["limitations"]]
    st.append(_p("8. Source references", h2))
    for s in rep["source_references"]:
        flag = s["provenance_label"]
        st.append(_p(f"{s['investigation']} | {s['filename']} | SHA-256 {s['sha256']} | "
                     f"{s['source_url'] or 'no URL recorded'} | {flag}", small))
    st.append(_p(rep["doi_note"], small))
    doc.build(st)
    return buf.getvalue()
