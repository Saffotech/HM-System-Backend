from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


DATABASE_URL = "postgresql://postgres:Amaresh%40123@localhost:5432/mydb"

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
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()