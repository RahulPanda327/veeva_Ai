"""SQLAlchemy engine and session factory — Azure Synapse Analytics (SQL Server)."""
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


def _build_connection_url() -> URL:
    return URL.create(
        drivername="mssql+pyodbc",
        username=settings.DB_USER,
        password=settings.DB_PASSWORD,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        query={
            "driver": "ODBC Driver 17 for SQL Server",
            "Encrypt": "yes",
            "TrustServerCertificate": "no",
            "autocommit": "yes",  # Azure Synapse serverless doesn't support explicit rollback
        },
    )


engine = create_engine(
    _build_connection_url(),
    pool_pre_ping=True,
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
