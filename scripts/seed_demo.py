"""Explicit synthetic seed with optional customer-activity fixture adapter."""
import os,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'services/api'))
if os.getenv('ENVIRONMENT','development') not in {'development','test'} or not os.getenv('DATABASE_URL'):
    raise SystemExit('Set explicit DATABASE_URL and development/test ENVIRONMENT for synthetic seeding')
from app.core.database import SessionLocal
from app.core.seeder import seed_demo_database
with SessionLocal() as db:
    seed_demo_database(db)
    if os.getenv('NEXTRM_SEED_CUSTOMER_ACTIVITY')=='true':
        from app.services.customer_activity import seed_customer_activity
        seed_customer_activity(db);db.commit()
print('Synthetic seed completed. Existing records and customer choices were preserved.')
