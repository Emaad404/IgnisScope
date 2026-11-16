"""Deterministic, explainable evidence search for ONE phenomenon: flame spread.

HEURISTIC, NOT VALIDATED. Formulas (w = weight from variables.py):
  coverage  C = sum(w_i * a_i) / sum(w_i)
  relevance R = sum(w_i * m_i * a_i) / sum(w_i * a_i)     (None if no parameter is available)
a_i = 1 if the parameter is available AND comparable in this file, else 0.
m_i in [0,1]: share of records matching the request (1.0 when only presence was requested).
Missing values are never treated as zero. Relevance, coverage and data quality stay separate.
"""
import re

from sqlalchemy.orm import Session

from .gap_analysis import derive_gaps
from .models import DataRecord, Investigation, SourceFile
from .schemas import StructuredQuery, TargetCondition
from .variables import MEASUREMENT_CHOICES, VARIABLES

CLASS_ORDER = {"DIRECT": 0, "ANALOGOUS": 1, "LIMITED": 2, "UNKNOWN": 3}
PHENOMENON_RE = re.compile(r"flame[\s_-]*spread|spread[\s_-]*rate|flame[\s_-]*front", re.I)
KNOWN_MATERIALS = ["pmma", "sibal", "cellulose", "paper", "cotton", "fiberglass", "acrylic", "nomex", "polyethylene"]
KEYWORDS = {
    "flame_spread_rate": ["spread rate", "flame speed", "spread speed", "rate of spread"],
    "oxygen_fraction": ["oxygen"], "pressure": ["pressure"], "flow_velocity": ["flow", "airflow", "velocity"],
    "temperature": ["temperature"], "thickness": ["thickness"], "width": ["width"],
}


def parse_question(text: str) -> StructuredQuery:
    """Keyword extraction only. Never invents numeric targets or physical conditions."""
    low = text.lower()
    meas = [k for k, words in KEYWORDS.items() if any(w in low for w in words)]
    material = next((m.upper() if len(m) <= 5 else m for m in KNOWN_MATERIALS if m in low), None)
    env = None
    if re.search(r"\biss\b|space station", low): env = "ISS"
    elif re.search(r"lunar|moon", low): env = "LUNAR_HABITAT"
    elif "mars" in low: env = "MARS_TRANSIT" if "transit" in low else "CUSTOM"
    return StructuredQuery(text=text, material=material, required_measurements=meas,
                           environment={"name": env, "provenance": "USER_ASSUMED"})


def _param_list(q: StructuredQuery):
    params: dict[str, dict] = {}
    for v in (q.required_measurements or ["flame_spread_rate"]):
        if v in VARIABLES:
            params[v] = dict(variable=v, role="required_measurement", target=None)
    for t in q.target_conditions:
        params[t.variable] = dict(variable=t.variable, role="target_condition", target=t)
    if q.material:
        params["material"] = dict(variable="material", role="material", target=q.material)
    return list(params.values())


def _eval_param(p, sf: SourceFile, inv: Investigation, recs: list[DataRecord]) -> dict:
    var, spec = p["variable"], VARIABLES[p["variable"]]
    idx = sf.column_map.get(var)
    col = sf.columns[idx] if idx is not None else None
    vals = [r.normalized.get(var) for r in recs]
    present = [v for v in vals if v is not None]
    statuses = [r.numeric_status.get(var, "UNKNOWN") for r in recs]
    row = dict(variable=var, label=spec["label"], role=p["role"], weight=spec["weight"],
               column=col["original"] if col else None, unit=col["unit"] if col else None,
               unit_source=col["unit_source"] if col else None, n_records=len(recs), n_present=len(present),
               available=False, match=None, comparable=True, status="", value_summary=None,
               gap_category=None, note="", source="records",
               parse_status_counts={s: statuses.count(s) for s in ("PARSED", "MISSING", "SENTINEL_MISSING", "NON_NUMERIC", "UNKNOWN")})
    # --- is it there at all?
    if var == "material" and not present:
        text = f"{inv.title} {inv.description or ''}".lower()
        if p["target"] and p["target"].lower() in text:
            row.update(available=True, match=1.0, source="investigation metadata", status="MATCH",
                       note="Material found in investigation title/description, not in per-record data.")
            return row
    if col is None:
        row.update(status="NOT_IN_FILE", gap_category=spec["gap"],
                   note="No column in this file was recognised as this variable. Not found in the indexed corpus.")
        return row
    if not present:
        row.update(status="ALL_MISSING", gap_category="MISSING_MEASUREMENT",
                   note="Column exists but every value is missing. Missing is not zero.")
        return row
    row["available"] = True
    if spec["numeric"]:
        row["value_summary"] = dict(min=min(present), max=max(present), n=len(present))
        if not col["unit"]:
            row.update(gap_category="DOCUMENTATION_GAP", note="Unit not documented in the file header.")
    # --- does it match what was asked?
    tgt = p["target"]
    if p["role"] == "required_measurement":
        row.update(match=1.0, status="PRESENT", note=row["note"] or "Presence only; no target value requested.")
    elif p["role"] == "material":
        hits = sum(1 for v in present if tgt.lower() in str(v).lower())
        row.update(match=hits / len(present), status="MATCH" if hits else "MISMATCH")
        if not hits:
            row.update(gap_category="MATERIAL_GAP", note=f"Material '{tgt}' not found among recorded materials.")
    else:  # numeric target
        t: TargetCondition = tgt
        if not col["unit"] or col["unit"].strip().lower() != t.unit.strip().lower():
            row.update(available=False, comparable=False, status="UNIT_NOT_COMPARABLE",
                       gap_category="DOCUMENTATION_GAP",
                       note=f"Target unit '{t.unit}' vs file unit '{col['unit'] or 'undocumented'}'. "
                            "No verified unit conversion is implemented, so values were not compared.")
            return row
        lo, hi = t.value * (1 - t.tolerance_pct / 100), t.value * (1 + t.tolerance_pct / 100)
        lo, hi = min(lo, hi), max(lo, hi)
        m = sum(1 for v in present if lo <= v <= hi) / len(present)
        row.update(match=m, status="MATCH" if m >= 0.5 else "MISMATCH",
                   note=f"{m:.0%} of records within {t.tolerance_pct:g}% of {t.value:g} {t.unit}.")
        if m < 0.5:
            row["gap_category"] = "CONDITION_MISMATCH"
    return row


def evaluate_file(sf: SourceFile, inv: Investigation, q: StructuredQuery, recs: list[DataRecord]) -> dict:
    params = [_eval_param(p, sf, inv, recs) for p in _param_list(q)]
    sw = sum(r["weight"] for r in params)
    swa = sum(r["weight"] for r in params if r["available"])
    swma = sum(r["weight"] * (r["match"] or 0) for r in params if r["available"])
    coverage = swa / sw if sw else 0.0
    relevance = swma / swa if swa else None
    phen = bool(sf.column_map.get("flame_spread_rate")) or bool(
        PHENOMENON_RE.search(f"{inv.title} {inv.description or ''} {sf.filename}"))
    mism = [r for r in params if r["status"] in ("MISMATCH",)]
    req_ok = all(r["available"] for r in params if r["role"] == "required_measurement")
    units_ok = all(r["comparable"] for r in params)
    reasons = []
    gravity_text = (inv.gravity_context or "").strip().lower()
    terrestrial = bool(re.search(r"\b1\s*g\b|terrestrial|earth gravity|ground[- ]based", gravity_text))
    microgravity = bool(re.search(r"micro[- ]?gravity|\b0\s*g\b|\bzero[- ]?g\b|\bμg\b|\bµg\b", gravity_text))
    if terrestrial:
        reasons.append("Documented gravity context is terrestrial/1g and cannot be direct evidence for microgravity claims.")
    if not phen:
        cls = "UNKNOWN"; reasons.append("No flame-spread signal in column headers, title, description or filename.")
    elif swa == 0:
        cls = "UNKNOWN"; reasons.append("None of the requested parameters is available and comparable in this file.")
    elif (coverage >= 0.8 and req_ok and not mism and units_ok and inv.gravity_provenance == "SOURCE_SUPPORTED"
          and microgravity and not terrestrial and inv.nasa_verified and not sf.is_synthetic):
        cls = "DIRECT"; reasons.append("Coverage >= 0.8, all required measurements present, no mismatches, "
                                       "units comparable, source-supported microgravity context, and user-attested "
                                       "NASA page check (not independently verified by this application).")
    elif coverage >= 0.5:
        cls = "ANALOGOUS"; reasons.append("Relevant, but at least one limit applies to transferability:")
        if coverage < 0.8: reasons.append("coverage below 0.8")
        if not req_ok: reasons.append("a required measurement is missing")
        if mism: reasons.append("condition/material mismatch: " + ", ".join(r["label"] for r in mism))
        if not units_ok: reasons.append("a unit could not be compared")
        if inv.gravity_provenance != "SOURCE_SUPPORTED": reasons.append("gravity context not source-supported")
        elif not microgravity: reasons.append("source-supported context does not explicitly identify microgravity")
        if terrestrial: reasons.append("terrestrial 1g context is not direct microgravity evidence")
        if not inv.nasa_verified: reasons.append("NASA page check not attested by user")
        if sf.is_synthetic: reasons.append("synthetic demonstration data cannot be classified DIRECT")
    else:
        cls = "LIMITED"; reasons.append("Flame-spread signal present, but coverage of requested parameters is below 0.5.")
    result = dict(
        investigation_id=inv.id, investigation_title=inv.title, psi_id=inv.psi_id, nasa_verified=inv.nasa_verified,
        is_synthetic=sf.is_synthetic, source_file_id=sf.id, source_filename=sf.filename, sha256=sf.sha256,
        classification=cls, relevance=None if relevance is None else round(relevance, 3),
        coverage=round(coverage, 3), data_quality=sf.data_quality, phenomenon_signal=phen,
        gravity_context=inv.gravity_context, gravity_provenance=inv.gravity_provenance,
        provenance_label=("SYNTHETIC DEMONSTRATION DATA — NOT NASA EXPERIMENTAL DATA" if sf.is_synthetic else
                          "USER-ATTESTED NASA PAGE CHECK — UNVERIFIED BY THIS APPLICATION" if inv.nasa_verified else
                          "SOURCE IDENTITY/VERIFICATION UNVERIFIED"), parameters=params, reasons=reasons,
        matching=[r["label"] for r in params if r["status"] in ("MATCH", "PRESENT")],
        missing=[r["label"] for r in params if r["status"] in ("NOT_IN_FILE", "ALL_MISSING")],
        mismatches=[r["label"] for r in mism], records_scored=len(recs),
        records_excluded_malformed=sf.row_count - len(recs),
        record_references=[dict(record_id=r.id, record_number=r.record_number, line_start=r.line_start,
                                line_end=r.line_end, parse_status=r.parse_status)
                           for r in recs if any(r.normalized.get(p["variable"]) is not None for p in params)],
        explanation=(f"Coverage = {swa:g}/{sw:g} weight; relevance = "
                     + (f"{swma:g}/{swa:g}" if swa else "n/a (nothing available)") + ". Heuristic, not validated."),
    )
    result["gaps"] = derive_gaps(result, q)
    return result


def run_search(db: Session, q: StructuredQuery) -> list[dict]:
    out = []
    for sf in db.query(SourceFile).order_by(SourceFile.id):
        if sf.parse_status == "FAILED" or (sf.is_synthetic and not q.include_synthetic):
            continue
        inv = db.get(Investigation, sf.investigation_id)
        recs = db.query(DataRecord).filter_by(source_file_id=sf.id, parse_status="OK").all()
        out.append(evaluate_file(sf, inv, q, recs))
    out.sort(key=lambda r: (CLASS_ORDER[r["classification"]], -(r["relevance"] or 0), -r["coverage"]))
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return out
