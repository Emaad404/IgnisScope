"""Synthetic demonstration data. Every record is fabricated for software testing only."""
from sqlalchemy.orm import Session

from . import config
from .ingestion import DuplicateFileError, ingest_bytes
from .models import Investigation

SYNTHETIC_CSV = """Run ID,Material,Oxygen concentration (%),Pressure (kPa),Flow velocity (cm/s),Flame spread rate (mm/s),Sample thickness (mm),Notes
S-001,SYNTHETIC-PMMA,21,101.3,5,1.20,1.0,synthetic row
S-002,SYNTHETIC-PMMA,21,101.3,10,1.55,1.0,synthetic row
S-003,SYNTHETIC-PMMA,30,101.3,5,2.40,1.0,synthetic row
S-004,SYNTHETIC-PMMA,30,70.0,5,,1.0,spread rate missing on purpose
S-005,SYNTHETIC-PMMA,21,70.0,10,-999,1.0,sentinel candidate on purpose
S-006,SYNTHETIC-PMMA,25,101.3
S-007,SYNTHETIC-PMMA,25,101.3,5,1.90,1.0,"note with a comma, and
a line break",extra-cell-on-purpose
"""

SYNTHETIC_TITLE = f"{config.SYNTHETIC_LABEL}: demo flame-spread table"


def load_synthetic(db: Session) -> dict:
    inv = db.query(Investigation).filter_by(title=SYNTHETIC_TITLE).first()
    if not inv:
        inv = Investigation(
            title=SYNTHETIC_TITLE, is_synthetic=True, nasa_verified=False,
            description=f"{config.SYNTHETIC_LABEL}. Fabricated rows for testing the software. "
                        "Flame spread table. Not a NASA measurement and not a real experiment.",
            gravity_context=None, gravity_provenance="UNKNOWN")
        db.add(inv); db.commit()
    (config.SYNTHETIC_DIR).mkdir(parents=True, exist_ok=True)
    path = config.SYNTHETIC_DIR / "synthetic_flame_spread.csv"
    if not path.exists():
        path.write_text(SYNTHETIC_CSV, encoding="utf-8", newline="")
    try:
        sf = ingest_bytes(db, path.read_bytes(), path.name, inv.id,
                          source_url="local synthetic fixture", is_synthetic=True)
        return dict(investigation_id=inv.id, source_file_id=sf.id, created=True)
    except DuplicateFileError as e:
        return dict(investigation_id=inv.id, source_file_id=e.existing_id, created=False)
