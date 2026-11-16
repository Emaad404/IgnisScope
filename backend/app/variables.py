"""Registry of variables the app can recognise by COLUMN HEADER NAME only.

This is a heuristic. A header match does not prove what a column physically measures;
it only lets the search engine look for it. Weights are application choices, not
scientifically validated values.
"""
import re

# order matters: first matching variable claims the column
VARIABLES = {
    "flame_spread_rate": dict(label="Flame spread rate", weight=3.0, numeric=True, kind="measurement",
                              patterns=["flame spread", "spread rate", "flame speed", "flame_spread", "spread_rate", "flame propagation", "spread velocity"],
                              gap="MISSING_VARIABLE"),
    "oxygen_fraction": dict(label="Oxygen concentration", weight=2.0, numeric=True, kind="condition",
                            patterns=["oxygen", "o2", "oxidizer fraction", "oxygen mole fraction", "oxygen volume fraction"], gap="MISSING_VARIABLE"),
    "pressure": dict(label="Pressure", weight=2.0, numeric=True, kind="condition",
                     patterns=["pressure"], gap="MISSING_VARIABLE"),
    "flow_velocity": dict(label="Flow velocity", weight=2.0, numeric=True, kind="condition",
                     patterns=["flow velocity", "flow speed", "airflow", "flow_velocity", "velocity", "gas speed", "gas velocity", "bulk flow", "freestream"],
                          gap="MISSING_VARIABLE"),
    "temperature": dict(label="Temperature", weight=1.0, numeric=True, kind="condition",
                    patterns=["temperature", "temp", "ambient temp", "sample temp", "gas temp"], gap="MISSING_VARIABLE"),
    "gravity": dict(label="Gravity level", weight=1.0, numeric=True, kind="condition",
                    patterns=["gravity", "g-level", "g level", "accel", "acceleration", "microgravity", "microgravity level"], gap="MISSING_VARIABLE"),
    "thickness": dict(label="Sample thickness", weight=1.0, numeric=True, kind="geometry",
                      patterns=["thickness"], gap="GEOMETRY_SCALE_GAP"),
    "width": dict(label="Sample width", weight=1.0, numeric=True, kind="geometry",
                  patterns=["width"], gap="GEOMETRY_SCALE_GAP"),
    "material": dict(label="Material or fuel", weight=2.0, numeric=False, kind="material",
                     patterns=["material", "fuel", "sample", "specimen"], gap="MATERIAL_GAP"),
}

MEASUREMENT_CHOICES = ["flame_spread_rate", "oxygen_fraction", "pressure", "flow_velocity",
                       "temperature", "thickness", "width"]

_UNIT_RE = re.compile(r"^(.*?)[\s_]*[\[(]([^\])]*)[\])]\s*$")


def split_header(header: str) -> tuple[str, str | None]:
    """'Pressure (kPa)' -> ('Pressure', 'kPa'). Unit only if written in the header itself."""
    m = _UNIT_RE.match(header.strip())
    if m and m.group(2).strip():
        return m.group(1).strip(), m.group(2).strip()
    return header.strip(), None


def match_variable(name: str) -> str | None:
    low = re.sub(r"[_-]+", " ", name.lower())
    for key, spec in VARIABLES.items():
        if any(p in low for p in spec["patterns"]):
            return key
    return None
