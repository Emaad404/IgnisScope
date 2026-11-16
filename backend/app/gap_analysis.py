"""Turns per-parameter evidence rows into a gap table. A gap means 'not found in the indexed
file', never 'the experiment did not measure it'."""

LIMITS = {
    "MISSING_VARIABLE": "No column recognised. The experiment may still have measured it; it is not in this file.",
    "MISSING_MEASUREMENT": "Column present but empty. Do not read this as a measurement of zero.",
    "CONDITION_MISMATCH": "Recorded conditions differ from the requested target. Transferability is limited.",
    "MATERIAL_GAP": "Requested material not documented or not matching.",
    "GEOMETRY_SCALE_GAP": "Sample geometry or scale not documented; scaling to the target cannot be assessed.",
    "DOCUMENTATION_GAP": "Metadata (unit, environment, gravity) missing; absence of documentation is not absence of a measurement.",
    "VALIDATION_GAP": "Validation or replication status is not documented in the indexed data.",
}


def derive_gaps(result: dict, q) -> list[dict]:
    gaps = []
    for p in result["parameters"]:
        if p["gap_category"]:
            gaps.append(dict(parameter=p["label"], required=p["role"] == "required_measurement", status=p["status"],
                             category=p["gap_category"], source=result["source_filename"], unit=p["unit"],
                             value=p["value_summary"], detail=p["note"], limitation=LIMITS[p["gap_category"]]))
    if result["gravity_provenance"] != "SOURCE_SUPPORTED":
        gaps.append(dict(parameter="Gravity context", required=True, status="NOT_SOURCE_SUPPORTED",
                         category="DOCUMENTATION_GAP", source=result["source_filename"], unit=None, value=None,
                         detail=f"Gravity provenance is {result['gravity_provenance']}.",
                         limitation=LIMITS["DOCUMENTATION_GAP"]))
    if q.environment.name:
        gaps.append(dict(parameter=f"Mission environment ({q.environment.name})", required=False,
                         status="NOT_COMPARABLE", category="DOCUMENTATION_GAP", source=result["source_filename"],
                         unit=None, value=None,
                         detail="Environment chosen by the user (USER_ASSUMED). The indexed file documents no "
                                "mission-environment conditions, so none are assumed.",
                         limitation=LIMITS["DOCUMENTATION_GAP"]))
    gaps.append(dict(parameter="Validation / replication", required=False, status="NOT_DOCUMENTED",
                     category="VALIDATION_GAP", source=result["source_filename"], unit=None, value=None,
                     detail="No replication or validation fields are indexed.", limitation=LIMITS["VALIDATION_GAP"]))
    return gaps
