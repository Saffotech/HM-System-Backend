from sqlalchemy import Column, Integer, String, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from Models.tenant import TenantScoped

class Department(TenantScoped):
    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_departments_tenant_name"),
        UniqueConstraint("tenant_id", "code", name="uq_departments_tenant_code"),
    )

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String, nullable=False)   # Cardiology, Ortho, General
    code        = Column(String(10), nullable=True) # CARD, ORTH, GEN
    description = Column(String, nullable=True)
    is_active   = Column(Boolean, default=True)