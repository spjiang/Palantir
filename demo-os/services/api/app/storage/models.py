from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase

from .db import engine


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ObjectState(Base):
    __tablename__ = "object_state"
    object_id = Column(String, primary_key=True)
    object_type = Column(String, index=True, nullable=False)
    area_id = Column(String, index=True, nullable=False)
    attrs = Column(JSON, nullable=False, default=dict)
    features = Column(JSON, nullable=False, default=dict)
    dq_tags = Column(JSON, nullable=False, default=dict)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class Incident(Base):
    __tablename__ = "incident"
    id = Column(String, primary_key=True)
    area_id = Column(String, index=True, nullable=False)
    title = Column(String, nullable=False)
    status = Column(String, nullable=False, default="open")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    def __init__(self, **kwargs: Any):
        # 简化：使用时间戳作为 id（演示级）
        if "id" not in kwargs:
            kwargs["id"] = f"inc-{int(datetime.now().timestamp()*1000)}"
        super().__init__(**kwargs)


class Task(Base):
    __tablename__ = "task"
    id = Column(String, primary_key=True)
    incident_id = Column(String, index=True, nullable=False)
    task_type = Column(String, nullable=False)
    target_object_id = Column(String, nullable=False)
    owner_org = Column(String, nullable=False)
    assignee = Column(String, nullable=True)
    sla_minutes = Column(Integer, nullable=False, default=60)
    required_evidence = Column(JSON, nullable=False, default=list)
    need_approval = Column(Boolean, nullable=False, default=False)
    status = Column(String, nullable=False, default="pending")
    title = Column(String, nullable=False, default="")
    detail = Column(Text, nullable=True)
    last_ack = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    def __init__(self, **kwargs: Any):
        if "id" not in kwargs:
            kwargs["id"] = f"task-{int(datetime.now().timestamp()*1000)}"
        super().__init__(**kwargs)


class TimelineEvent(Base):
    __tablename__ = "timeline_event"
    id = Column(String, primary_key=True)
    incident_id = Column(String, index=True, nullable=False)
    type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    def __init__(self, **kwargs: Any):
        if "id" not in kwargs:
            kwargs["id"] = f"tl-{int(datetime.now().timestamp()*1000)}"
        super().__init__(**kwargs)


class AlertEvent(Base):
    __tablename__ = "alert_event"
    id = Column(String, primary_key=True)
    incident_id = Column(String, index=True, nullable=False)
    area_id = Column(String, index=True, nullable=False)
    level = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    def __init__(self, **kwargs: Any):
        if "id" not in kwargs:
            kwargs["id"] = f"al-{int(datetime.now().timestamp()*1000)}"
        super().__init__(**kwargs)


def ensure_schema():
    Base.metadata.create_all(bind=engine)


