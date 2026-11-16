from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from . import config


class Base(DeclarativeBase):
    pass


def make_engine(url: str | None = None):
    url = url or f"sqlite:///{config.DB_PATH}"
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):  # SQLite ignores foreign keys unless this is set per connection
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


engine = None
SessionLocal = sessionmaker(autoflush=False, expire_on_commit=False)


def init_db(url: str | None = None):
    """Create the engine (once) and all tables. Safe to call repeatedly."""
    global engine
    from . import models  # noqa: F401  (registers tables)
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    engine = make_engine(url)
    SessionLocal.configure(bind=engine)
    Base.metadata.create_all(engine)
    # Small additive upgrade for databases created before numeric parse statuses existed.
    # Keep raw data and all existing tables intact; no destructive migration is performed.
    columns = {c["name"] for c in inspect(engine).get_columns("data_records")}
    if "numeric_status" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE data_records ADD COLUMN numeric_status JSON NOT NULL DEFAULT '{}'"))
    return engine


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
