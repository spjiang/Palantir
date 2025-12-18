from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .storage import db
from .storage.models import (
    AlertEvent,
    Incident,
    ObjectState,
    Task,
    TimelineEvent,
    ensure_schema,
)


MODEL_SERVICE_URL = os.getenv("MODEL_SERVICE_URL", "http://model-service:8002").rstrip("/")
AUTO_SEED = os.getenv("AUTO_SEED", "false").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_schema()
    if AUTO_SEED:
        seed_demo_data()
    yield


app = FastAPI(title="Flood Demo API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# 数据契约（演示级）
# -----------------------------


class RiskItem(BaseModel):
    target_id: str
    target_type: str = "road_segment"
    risk_score: float
    risk_level: str
    confidence: float
    explain_factors: list[str] = Field(default_factory=list)
    model_version: str


class RiskTopNResponse(BaseModel):
    time: str
    area_id: str
    items: list[RiskItem]


class AgentTask(BaseModel):
    task_type: str
    target_object_id: str
    owner_org: str
    sla_minutes: int = 60
    required_evidence: list[str] = Field(default_factory=list)
    need_approval: bool = False
    title: str | None = None
    detail: str | None = None


class TaskPack(BaseModel):
    incident_id: str
    tasks: list[AgentTask]


class WorkflowTriggerResponse(BaseModel):
    incident_id: str
    created_task_ids: list[str]
    status: str


class TaskAck(BaseModel):
    actor: str = "mobile_user"
    status: str = "done"
    note: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class AgentChatRequest(BaseModel):
    incident_id: str | None = None
    area_id: str = "A-001"
    message: str


class AgentChatResponse(BaseModel):
    summary: str
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    risk_controls: dict[str, Any] = Field(default_factory=dict)


# -----------------------------
# 核心接口（供前端/智能体工具调用）
# -----------------------------


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/risk/topn", response_model=RiskTopNResponse)
async def risk_topn(area_id: str = "A-001", n: int = 5):
    """对标 V7：TopN 风险点位（模型+置信度+解释因子）。"""
    now = datetime.now(timezone.utc)
    # 从对象状态表取路段列表（演示：取前 N*2 再让模型排序）
    with db.session() as s:
        roads = (
            s.query(ObjectState)
            .filter(ObjectState.object_type == "road_segment", ObjectState.area_id == area_id)
            .limit(max(n * 2, n))
            .all()
        )
    if not roads:
        raise HTTPException(404, "no road segments in this area")

    payload = {
        "time": now.isoformat(),
        "area_id": area_id,
        "targets": [{"target_id": r.object_id, "features": r.features or {}} for r in roads],
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(f"{MODEL_SERVICE_URL}/infer/topn", json=payload)
    if resp.status_code != 200:
        raise HTTPException(502, f"model-service error: {resp.text}")
    data = resp.json()
    items = [RiskItem(**it) for it in data["items"][:n]]
    return RiskTopNResponse(time=payload["time"], area_id=area_id, items=items)


@app.get("/objects/{object_id}")
def get_object_state(object_id: str):
    """对标 V7：对象状态快照接口 get_object_state(object_id)。"""
    with db.session() as s:
        obj = s.query(ObjectState).filter(ObjectState.object_id == object_id).first()
        if not obj:
            raise HTTPException(404, "object not found")
        return {
            "object_id": obj.object_id,
            "object_type": obj.object_type,
            "area_id": obj.area_id,
            "attrs": obj.attrs or {},
            "features": obj.features or {},
            "dq_tags": obj.dq_tags or {},
            "updated_at": obj.updated_at.isoformat(),
        }


@app.post("/workflow/incidents", response_model=dict)
def create_incident(area_id: str = "A-001", title: str = "暴雨内涝事件"):
    with db.session() as s:
        inc = Incident(area_id=area_id, title=title, status="open")
        s.add(inc)
        s.flush()
        s.add(TimelineEvent(incident_id=inc.id, type="incident_created", payload={"title": title}))
        s.commit()
        return {"incident_id": inc.id, "status": inc.status}


@app.post("/workflow/incidents/{incident_id}/tasks", response_model=WorkflowTriggerResponse)
def create_tasks(incident_id: str, task_pack: TaskPack):
    """创建任务（演示级）。"""
    if incident_id != task_pack.incident_id:
        raise HTTPException(400, "incident_id mismatch")
    created: list[str] = []
    with db.session() as s:
        inc = s.query(Incident).filter(Incident.id == incident_id).first()
        if not inc:
            raise HTTPException(404, "incident not found")
        for t in task_pack.tasks:
            task = Task(
                incident_id=incident_id,
                task_type=t.task_type,
                target_object_id=t.target_object_id,
                owner_org=t.owner_org,
                sla_minutes=t.sla_minutes,
                required_evidence=t.required_evidence,
                need_approval=t.need_approval,
                status="pending",
                title=t.title or t.task_type,
                detail=t.detail,
            )
            s.add(task)
            s.flush()
            created.append(task.id)
            s.add(
                TimelineEvent(
                    incident_id=incident_id,
                    type="task_created",
                    payload={"task_id": task.id, "task_type": task.task_type, "target": task.target_object_id},
                )
            )
        s.commit()
    return WorkflowTriggerResponse(incident_id=incident_id, created_task_ids=created, status="created")


@app.get("/workflow/incidents/{incident_id}/tasks")
def list_tasks(incident_id: str):
    with db.session() as s:
        tasks = s.query(Task).filter(Task.incident_id == incident_id).order_by(Task.created_at.desc()).all()
        return [
            {
                "task_id": t.id,
                "task_type": t.task_type,
                "target_object_id": t.target_object_id,
                "owner_org": t.owner_org,
                "sla_minutes": t.sla_minutes,
                "status": t.status,
                "need_approval": t.need_approval,
                "required_evidence": t.required_evidence,
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
            }
            for t in tasks
        ]


@app.post("/workflow/tasks/{task_id}/ack")
def ack_task(task_id: str, ack: TaskAck):
    with db.session() as s:
        task = s.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(404, "task not found")
        task.status = ack.status
        task.last_ack = {"actor": ack.actor, "note": ack.note, "evidence": ack.evidence, "time": datetime.now(timezone.utc).isoformat()}
        task.updated_at = datetime.now(timezone.utc)
        s.add(
            TimelineEvent(
                incident_id=task.incident_id,
                type="task_ack",
                payload={"task_id": task.id, "status": task.status, "actor": ack.actor, "evidence": ack.evidence},
            )
        )
        s.commit()
        return {"ok": True}


@app.get("/reports/incidents/{incident_id}")
def incident_report(incident_id: str):
    """演示级战报：时间线 + 指标（极简）。"""
    with db.session() as s:
        inc = s.query(Incident).filter(Incident.id == incident_id).first()
        if not inc:
            raise HTTPException(404, "incident not found")
        timeline = (
            s.query(TimelineEvent).filter(TimelineEvent.incident_id == incident_id).order_by(TimelineEvent.created_at.asc()).all()
        )
        tasks = s.query(Task).filter(Task.incident_id == incident_id).all()
    done = sum(1 for t in tasks if t.status == "done")
    return {
        "incident_id": incident_id,
        "title": inc.title,
        "status": inc.status,
        "metrics": {
            "task_total": len(tasks),
            "task_done": done,
            "task_done_rate": (done / len(tasks)) if tasks else 0.0,
        },
        "timeline": [{"time": e.created_at.isoformat(), "type": e.type, "payload": e.payload} for e in timeline],
    }


# -----------------------------
# 演示数据初始化
# -----------------------------


def seed_demo_data():
    now = datetime.now(timezone.utc)
    with db.session() as s:
        areas = [
            ("A-001", "示范区"),
            ("A-002", "江北新区"),
            ("A-003", "高新区"),
        ]

        for area_id, admin_area in areas:
            # 若该区域已有对象则跳过
            if s.query(ObjectState).filter(ObjectState.area_id == area_id).count() > 0:
                continue
            # 12 个路段对象，前 3 条调高风险（红/橙）
            for i in range(1, 13):
                oid = f"road-{i:03d}"
                high_risk = i <= 3
                features = {
                    "rain_now_mmph": 60 + i * 3 if high_risk else 30 + i * 1.5,
                    "rain_1h_mm": 40 + i * 2 if high_risk else 20 + i * 1.2,
                    "water_level_m": 6.0 - i * 0.15 if high_risk else 2.5 + (i % 5) * 0.3,
                    "pump_status": "fault" if high_risk and i % 2 == 0 else ("running" if i % 4 != 0 else "fault"),
                    "traffic_index": 0.6 + (i % 4) * 0.1,
                    "drainage_capacity": 0.8 if high_risk else 1.0 + (i % 3) * 0.2,
                    "elevation_m": 2.5 if high_risk else 5.0 - i * 0.2,
                }
                s.add(
                    ObjectState(
                        object_id=oid,
                        object_type="road_segment",
                        area_id=area_id,
                        attrs={"name": f"路段{i}", "admin_area": admin_area, "elevation_m": features["elevation_m"], "drainage_capacity": features["drainage_capacity"]},
                        features=features,
                        dq_tags={"freshness": 0.95, "validity": True},
                        updated_at=now,
                    )
                )

            # 默认事件与预警
            inc = Incident(area_id=area_id, title=f"{admin_area} 暴雨内涝处置事件（演示）", status="open")
            s.add(inc)
            s.flush()
            s.add(TimelineEvent(incident_id=inc.id, type="incident_created", payload={"title": inc.title}))
            s.add(
                AlertEvent(
                    incident_id=inc.id,
                    area_id=area_id,
                    level="红" if area_id == "A-002" else "橙",
                    reason="雨强上升+低洼路段风险提升",
                    created_at=now - timedelta(minutes=5),
                )
            )
            s.add(TimelineEvent(incident_id=inc.id, type="alert_event", payload={"level": "红" if area_id == "A-002" else "橙", "reason": "雨强上升"}))

        s.commit()


