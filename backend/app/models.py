from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Investigation(Base):
    __tablename__ = "investigations"
    id: Mapped[int] = mapped_column(primary_key=True)
    psi_id: Mapped[str | None] = mapped_column(String(40))          # e.g. "PSI-98", only as typed by the user
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(500))
    # True only if the user states they checked this record against the official NASA page.
    # The application cannot verify this itself.
    nasa_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    gravity_context: Mapped[str | None] = mapped_column(String(120))
    gravity_provenance: Mapped[str] = mapped_column(String(20), default="UNKNOWN")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    files: Mapped[list["SourceFile"]] = relationship(back_populates="investigation")


class SourceFile(Base):
    __tablename__ = "source_files"
    __table_args__ = (UniqueConstraint("sha256", name="uq_source_sha256"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    investigation_id: Mapped[int] = mapped_column(ForeignKey("investigations.id"))
    filename: Mapped[str] = mapped_column(String(300))
    stored_path: Mapped[str] = mapped_column(String(600))
    source_url: Mapped[str | None] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    encoding: Mapped[str] = mapped_column(String(20))
    delimiter: Mapped[str] = mapped_column(String(4))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    parse_status: Mapped[str] = mapped_column(String(20))            # OK | WARNINGS | FAILED
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    columns: Mapped[list] = mapped_column(JSON)       # [{index,original,name,unit,unit_source,canonical}]
    column_map: Mapped[dict] = mapped_column(JSON)    # canonical variable -> column index
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    data_quality: Mapped[dict] = mapped_column(JSON, default=dict)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    pipeline_version: Mapped[str] = mapped_column(String(60))
    investigation: Mapped[Investigation] = relationship(back_populates="files")
    records: Mapped[list["DataRecord"]] = relationship(back_populates="source_file")


class DataRecord(Base):
    __tablename__ = "data_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_file_id: Mapped[int] = mapped_column(ForeignKey("source_files.id"), index=True)
    record_number: Mapped[int] = mapped_column(Integer)   # logical record, 1 = first data row
    line_start: Mapped[int] = mapped_column(Integer)      # physical lines in the file
    line_end: Mapped[int] = mapped_column(Integer)
    parse_status: Mapped[str] = mapped_column(String(20))  # OK | SHORT | LONG
    issues: Mapped[list] = mapped_column(JSON, default=list)
    raw_values: Mapped[list] = mapped_column(JSON)         # aligned to columns; null = cell absent
    extra_cells: Mapped[list] = mapped_column(JSON, default=list)
    normalized: Mapped[dict] = mapped_column(JSON, default=dict)  # derived; raw_values stay untouched
    numeric_status: Mapped[dict] = mapped_column(JSON, default=dict)  # PARSED | MISSING | SENTINEL_MISSING | NON_NUMERIC
    source_file: Mapped[SourceFile] = relationship(back_populates="records")


class ResearchQuestion(Base):
    __tablename__ = "research_questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    structured: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    results: Mapped[list["EvidenceResult"]] = relationship(back_populates="question")


class EvidenceResult(Base):
    __tablename__ = "evidence_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("research_questions.id"), index=True)
    investigation_id: Mapped[int] = mapped_column(ForeignKey("investigations.id"))
    source_file_id: Mapped[int] = mapped_column(ForeignKey("source_files.id"))
    rank: Mapped[int] = mapped_column(Integer)
    classification: Mapped[str] = mapped_column(String(12))
    relevance: Mapped[float | None] = mapped_column(Float)
    coverage: Mapped[float] = mapped_column(Float)
    payload: Mapped[dict] = mapped_column(JSON)
    question: Mapped[ResearchQuestion] = relationship(back_populates="results")
