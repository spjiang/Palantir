from __future__ import annotations

import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./demo.db")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def session():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


