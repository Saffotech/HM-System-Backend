from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# DATABASE_URL = "postgresql://postgres:Admin%401234@localhost:5432/hospital_db"

DATABASE_URL = "postgresql://postgres:Admin%401234@localhost:5432/hospital_db"
engine  = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    bind = engine,
    autocommit = False,
    autoflush = False
)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()