import sys
sys.path.insert(0, "D:/veeva_AI/repstream/backend")
from app.database import engine
from sqlalchemy import text

views = [
    "vw_tdim_healthcarepractitioner_zenpep_reporting_dul",
    "vw_tfact_prescribersales_zenpep_reporting_dul",
    "vw_tfact_callactivitydetails_zenpep_reporting_dul",
]

for v in views:
    print(f"\n=== {v} ===")
    try:
        with engine.connect() as conn:
            r = conn.execute(text(f"SELECT TOP 1 * FROM hub_insight360.{v}"))
            cols = list(r.keys())
            print("COLUMNS:", cols)
            row = r.fetchone()
            if row:
                for k, val in zip(cols, row):
                    print(f"  {k}: {repr(val)}")
            else:
                print("  (no rows)")
    except Exception as e:
        print(f"  ERROR: {e}")
