from sqlalchemy.orm import Session
from database import engine
from Models.doctor import Doctor
from Models.tenant import Tenant
from Services import patient_portal_service as svc
from datetime import date, timedelta

with Session(engine) as s:
    t = s.query(Tenant).filter(Tenant.code == "CALI").first()
    s.info["tenant_id"] = t.id
    docs = s.query(Doctor).all()
    print("doctors:", [(d.id, d.department_id, getattr(d, "is_active", None)) for d in docs][:10])
    for d in docs[:3]:
        for off in range(0, 3):
            day = date.today() + timedelta(days=off)
            try:
                r = svc.list_slots(s, d.id, d.department_id, day)
                print(d.id, day, str(r)[:300])
            except Exception as e:
                print(d.id, day, "ERR", repr(e)[:200])
