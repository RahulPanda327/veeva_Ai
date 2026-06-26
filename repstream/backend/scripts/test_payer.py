import sys
sys.path.insert(0, "D:/veeva_AI/repstream/backend")

from app.database import SessionLocal
from app.services.action_center.payer_access_svc import get_payer_access

db = SessionLocal()
try:
    result = get_payer_access(db)
    print(f"Total: {result.total}")
    print(f"Alert count: {result.ai_alert_count}")
    for item in result.items[:3]:
        print(f"  {item.plan_id} | {item.payer_name} | {item.status_badge} | score={item.ai_impact_score} | {item.ai_impact_level}")
        print(f"    tier: {item.tier_previous} -> {item.tier_current} ({item.ai_tier_change_direction})")
        print(f"    badges: {item.analysis_badges}")
        print(f"    nlp_category: {item.ai_nlp_action_category} | urgency: {item.ai_nlp_urgency}")
        print(f"    gpt title: {item.ai_impact_summary[:60] if item.ai_impact_summary else 'N/A'}")
finally:
    db.close()
