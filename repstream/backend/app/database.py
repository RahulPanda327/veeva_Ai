"""SQLAlchemy engine and session factory — Azure Synapse Analytics (SQL Server)."""
import logging
import re
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

log = logging.getLogger(__name__)


def _resolve_odbc_driver() -> str:
    """Pick a SQL Server ODBC driver that is actually installed on THIS machine.

    The driver is an OS-level package, not a pip dependency, so it varies per
    host: dev boxes commonly have 17, newer images ship 18, and a machine can
    have both. Hardcoding one name means the app runs wherever that exact
    version happens to be installed and dies everywhere else with
    "Can't open lib 'ODBC Driver 17 for SQL Server'".

    Order of preference:
      1. settings.DB_DRIVER, when set AND installed — an explicit override wins.
      2. The highest-numbered "ODBC Driver NN for SQL Server" present.
      3. Any other driver mentioning SQL Server (e.g. the legacy
         "SQL Server Native Client"), as a last resort.
    """
    try:
        import pyodbc   # noqa: PLC0415
        installed = pyodbc.drivers()
    except Exception as exc:  # noqa: BLE001 — pyodbc missing or no driver manager
        log.warning("Could not list ODBC drivers (%s); falling back to Driver 17.", exc)
        return "ODBC Driver 17 for SQL Server"

    # .env values are conventionally written with braces: {ODBC Driver 17 ...}
    wanted = (settings.DB_DRIVER or "").strip().strip("{}").strip()
    if wanted:
        if wanted in installed:
            return wanted
        log.warning("DB_DRIVER=%r is not installed. Installed: %s. Auto-detecting instead.",
                    wanted, installed or "none")

    numbered = []
    for name in installed:
        m = re.fullmatch(r"ODBC Driver (\d+) for SQL Server", name)
        if m:
            numbered.append((int(m.group(1)), name))
    if numbered:
        chosen = max(numbered)[1]
        log.info("Using ODBC driver %r (installed: %s).", chosen, installed)
        return chosen

    for name in installed:
        if "SQL Server" in name:
            log.warning("No versioned ODBC driver found; using %r.", name)
            return name

    raise RuntimeError(
        "No SQL Server ODBC driver is installed on this machine. "
        f"pyodbc reports: {installed or 'none'}. Install 'ODBC Driver 18 for SQL Server' "
        "(or 17), or set DB_DRIVER in .env to a driver that is installed."
    )


def _build_connection_url() -> URL:
    return URL.create(
        drivername="mssql+pyodbc",
        username=settings.DB_USER,
        password=settings.DB_PASSWORD,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        query={
            "driver": _resolve_odbc_driver(),
            # Azure Synapse requires TLS. Driver 18 defaults to Encrypt=yes and
            # 17 to Encrypt=no, so state it explicitly and the behaviour is the
            # same whichever version was picked above.
            "Encrypt": "yes",
            "TrustServerCertificate": "no",
            "autocommit": "yes",  # Azure Synapse serverless doesn't support explicit rollback
        },
    )


engine = create_engine(
    _build_connection_url(),
    pool_pre_ping=True,     # check a pooled connection is alive before handing it out
    pool_recycle=240,       # drop connections older than 4 min so Synapse's idle
                            # timeout can't hand us a already-dead one on checkout
    pool_size=5,
    max_overflow=10,
    echo=False,
    isolation_level="AUTOCOMMIT",  # Azure Synapse serverless doesn't support explicit transactions
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
