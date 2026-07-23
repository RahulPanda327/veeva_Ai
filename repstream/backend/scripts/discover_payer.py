import sys
sys.path.insert(0, "D:/veeva_AI/repstream/backend")
from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text("SELECT * FROM hub_insight360.insight360_payer_access_dul ORDER BY AI_Alert_Flag DESC"))
    cols = list(result.keys())
    rows = result.fetchall()
    print(f"TOTAL ROWS: {len(rows)}")
    for row in rows:
        print("---")
        for k, v in zip(cols, row):
            print(f"  {k}: {repr(v)}")
