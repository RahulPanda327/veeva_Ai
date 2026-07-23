"""Test Azure Synapse connection and print first 3 rows from active alerts."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from app.config import settings

print(f"Host     : {settings.DB_HOST}")
print(f"Port     : {settings.DB_PORT}")
print(f"Database : {settings.DB_NAME}")
print(f"User     : {settings.DB_USER}")
print(f"Password : {settings.DB_PASSWORD[:6]}***")
print(f"Schema   : {settings.HUB_SCHEMA}")
print()

from app.database import engine
from sqlalchemy import text

try:
    with engine.connect() as conn:
        rows = conn.execute(
            text(f"SELECT TOP 5 * FROM {settings.HUB_SCHEMA}.insight360_active_alerts_dul")
        ).fetchall()
        print(f"Connected! Found {len(rows)} rows.")
        for r in rows:
            print(dict(r._mapping))
except Exception as e:
    print(f"Connection failed: {e}")
