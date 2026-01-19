from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...deps import pg, store

router = APIRouter(tags=["L5-ClosedLoopExecutionWorkflow"])


class TaskCreate(BaseModel):
    title: str = Field(..., description="任务标题/名称，例如：巡检运维任务")
    task_type: str = Field(default="巡检", description="任务类型，例如：巡检/处置/复核")
    draft_id: str | None = Field(default=None, description="可选：绑定到临时本体库 draft_id")
    target_entity_id: str | None = Field(default=None, description="可选：目标对象实体ID（临时本体库 ent-xxx）")
    target_entity_name: str | None = Field(default=None, description="可选：目标对象名称（如管段）")
    source_behavior: str | None = Field(default=None, description="可选：来源行为名（Behavior.name）")
    action_plan: list[dict] | None = Field(default=None, description="可选：动作编排（Action/Function 契约）")
    decision_reason: str | None = Field(default=None, description="可选：决策原因/说明（来自 L4/LLM）")


class TaskStatusUpdate(BaseModel):
    status: str = Field(..., description="pending/accepted/in_progress/done/rejected")


class EvidenceCreate(BaseModel):
    evidence_type: str = Field(..., description="证据类型，例如：定位信息/现场照片/报告")
    content: str = Field(..., description="证据内容：URL/文本/路径等")
    draft_id: str | None = Field(default=None, description="可选：绑定到临时本体库 draft_id（用于写入本体关系）")


def _require_pg():
    if not pg:
        raise HTTPException(500, "PG_DSN not configured")
    try:
        pg.connect()
    except Exception as e:
        raise HTTPException(500, f"Postgres not ready: {e}")


@router.get("/workflow/tasks")
def list_tasks(draft_id: str | None = None):
    _require_pg()
    return {"items": pg.list_tasks(draft_id=draft_id)}


@router.post("/workflow/tasks")
def create_task(payload: TaskCreate):
    _require_pg()
    task = pg.create_task(
        title=payload.title,
        task_type=payload.task_type,
        draft_id=payload.draft_id,
        target_entity_id=payload.target_entity_id,
        target_entity_name=payload.target_entity_name,
        source_behavior=payload.source_behavior,
        action_plan=payload.action_plan,
        decision_reason=payload.decision_reason,
    )

    # 与本体联动：若给了 draft_id，则把任务实体与 targets 关系写入临时本体库（供 L2/L5 联动展示）
    if payload.draft_id:
        try:
            task_ent_id = task["id"]
            store.upsert_draft_entity_by_id(
                payload.draft_id,
                task_ent_id,
                name=task["title"],
                label="MaintenanceTask",
                props={
                    "source": "workflow",
                    "task_type": task["task_type"],
                    "status": task["status"],
                    "source_behavior": task.get("source_behavior"),
                    "decision_reason": task.get("decision_reason"),
                    "action_plan": task.get("action_plan"),
                },
            )
            if payload.target_entity_id:
                rel_id = f"rel-{uuid.uuid4().hex[:10]}"
                store.upsert_draft_relation_by_id(
                    payload.draft_id,
                    rel_id,
                    src=task_ent_id,
                    dst=payload.target_entity_id,
                    rel_type="targets",
                    props={"source": "workflow"},
                )
        except Exception as e:
            raise HTTPException(500, f"task created but failed to link ontology draft: {e}")

    return task


@router.get("/workflow/tasks/{task_id}/actions")
def list_task_actions(task_id: str):
    """
    返回任务动作编排（action_plan）与执行记录（action_runs）。
    """
    _require_pg()
    task = pg.get_task(task_id)
    if not task:
        raise HTTPException(404, "task not found")
    runs = pg.list_action_runs(task_id=task_id)
    return {"task_id": task_id, "action_plan": task.get("action_plan") or [], "runs": runs}


class ActionRunCreate(BaseModel):
    seq: int = Field(..., description="动作序号（从 1 开始）")
    action_type: str = Field(..., description="动作类型（契约）")
    params: dict | None = Field(default=None, description="动作参数")
    result: dict | None = Field(default=None, description="执行结果（可选）")
    status: str = Field(default="done", description="pending|done|failed（MVP 默认 done）")
    draft_id: str | None = Field(default=None, description="可选：写回临时本体库（动作执行节点）")


@router.post("/workflow/tasks/{task_id}/actions/run")
def create_action_run(task_id: str, payload: ActionRunCreate):
    """
    MVP：模拟执行动作，并写入 task_action_runs。
    后续可在此对接外部系统（工单、短信、阀控、巡检 APP、告警平台等）。
    """
    _require_pg()
    task = pg.get_task(task_id)
    if not task:
        raise HTTPException(404, "task not found")
    run = pg.create_action_run(
        task_id=task_id,
        seq=int(payload.seq),
        action_type=payload.action_type,
        params=payload.params or {},
        status=payload.status,
        result=payload.result or {},
    )

    # 可选：写回临时本体库（供 L2 可视化闭环）
    if payload.draft_id:
        try:
            store.upsert_draft_entity_by_id(
                payload.draft_id,
                run["id"],
                name=f"{payload.action_type}",
                label="ActionRun",
                props={
                    "source": "workflow",
                    "task_id": task_id,
                    "seq": payload.seq,
                    "status": payload.status,
                    "params": payload.params or {},
                    "result": payload.result or {},
                },
            )
            store.upsert_draft_relation_by_id(
                payload.draft_id,
                f"rel-workflow-has_action-{task_id}-{run['id']}",
                src=task_id,
                dst=run["id"],
                rel_type="has_action",
                props={"source": "workflow"},
            )
        except Exception as e:
            raise HTTPException(500, f"action run created but failed to link ontology draft: {e}")

    return run


@router.put("/workflow/tasks/{task_id}/status")
def update_task_status(task_id: str, payload: TaskStatusUpdate):
    _require_pg()
    task = pg.update_task_status(task_id, payload.status)
    if not task:
        raise HTTPException(404, "task not found")
    return task


@router.get("/workflow/tasks/{task_id}/evidence")
def list_task_evidence(task_id: str):
    _require_pg()
    task = pg.get_task(task_id)
    if not task:
        raise HTTPException(404, "task not found")
    return {"items": pg.list_evidence(task_id=task_id)}


@router.post("/workflow/tasks/{task_id}/evidence")
def add_task_evidence(task_id: str, payload: EvidenceCreate):
    _require_pg()
    task = pg.get_task(task_id)
    if not task:
        raise HTTPException(404, "task not found")
    ev = pg.add_evidence(task_id=task_id, evidence_type=payload.evidence_type, content=payload.content)

    # 与本体联动：若给了 draft_id，则把证据实体与 has_evidence 关系写入临时本体库
    if payload.draft_id:
        try:
            evid = ev["id"]
            store.upsert_draft_entity_by_id(
                payload.draft_id,
                evid,
                name=f"{payload.evidence_type}",
                label="Evidence",
                props={"source": "workflow", "content": payload.content},
            )
            rel_id = f"rel-{uuid.uuid4().hex[:10]}"
            store.upsert_draft_relation_by_id(
                payload.draft_id,
                rel_id,
                src=task_id,
                dst=evid,
                rel_type="has_evidence",
                props={"source": "workflow"},
            )
        except Exception as e:
            raise HTTPException(500, f"evidence created but failed to link ontology draft: {e}")

    return ev


@router.get("/workflow/tasks/{task_id}/timeline")
def task_timeline(task_id: str):
    _require_pg()
    task = pg.get_task(task_id)
    if not task:
        raise HTTPException(404, "task not found")
    return {"task": task, "events": pg.list_task_events(task_id=task_id)}

