from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ...deps import pg

router = APIRouter(tags=["L6-ReportsTraceability"])


def _require_pg():
    if not pg:
        raise HTTPException(500, "PG_DSN not configured")
    try:
        pg.connect()
    except Exception as e:
        raise HTTPException(500, f"Postgres not ready: {e}")


def _norm_ts(v) -> str:
    return str(v) if v is not None else ""


@router.get("/timeline")
def timeline(draft_id: str | None = None, segment_id: str | None = None, limit: int = 200):
    """
    L6 追溯时间线（聚合）：
    - L1: sensor_readings / alarms
    - L3: risk_events
    - L5: tasks / task_events / evidence
    """
    _require_pg()
    limit = max(1, min(limit, 1000))

    # L1
    readings = pg.list_readings(segment_id=segment_id, limit=200) if segment_id else pg.list_readings(limit=200)
    alarms = pg.list_alarms(segment_id=segment_id, limit=200) if segment_id else pg.list_alarms(limit=200)

    # L3
    risk_events = pg.list_risk_events(draft_id=draft_id, segment_id=segment_id, limit=200) if (draft_id or segment_id) else pg.list_risk_events(limit=200)

    # L5 tasks
    tasks = pg.list_tasks(draft_id=draft_id) if draft_id else pg.list_tasks()
    if segment_id:
        # 进一步按 target_entity_name/target_entity_id 模糊过滤（避免 schema 变更）
        seg = pg.fetchone("SELECT * FROM pipeline_segments WHERE id=%s;", (segment_id,))
        seg_name = seg.get("name") if seg else None
        seg_ent = f"ent-l1-{segment_id}"
        tasks = [t for t in tasks if (t.get("target_entity_id") == seg_ent) or (seg_name and t.get("target_entity_name") == seg_name)]

    # 汇总 timeline items
    items: list[dict[str, Any]] = []

    for r in readings:
        items.append(
            {
                "ts": _norm_ts(r.get("ts")),
                "kind": "L1_Reading",
                "title": f"读数：{r.get('sensor_name')}",
                "detail": {"pressure": r.get("pressure"), "flow": r.get("flow"), "sensor_id": r.get("sensor_id"), "reading_id": r.get("id")},
            }
        )

    for a in alarms:
        items.append(
            {
                "ts": _norm_ts(a.get("ts")),
                "kind": "L1_Alarm",
                "title": f"告警：{a.get('alarm_type')} ({a.get('severity')})",
                "detail": {"message": a.get("message"), "alarm_id": a.get("id"), "sensor_id": a.get("sensor_id"), "segment_id": a.get("segment_id")},
            }
        )

    for ev in risk_events:
        items.append(
            {
                "ts": _norm_ts(ev.get("ts")),
                "kind": "L3_RiskEvent",
                "title": f"风险评估：{ev.get('segment_name') or ev.get('segment_id')} → {ev.get('risk_state')} (score={ev.get('risk_score')})",
                "detail": {"explain": ev.get("explain"), "risk_event_id": ev.get("id"), "draft_id": ev.get("draft_id"), "evidence": ev.get("evidence")},
            }
        )

    for t in tasks[:200]:
        items.append(
            {
                "ts": _norm_ts(t.get("created_at")),
                "kind": "L5_Task",
                "title": f"任务创建：{t.get('title')}",
                "detail": {"task_id": t.get("id"), "status": t.get("status"), "task_type": t.get("task_type"), "draft_id": t.get("draft_id")},
            }
        )
        # task events/evidence
        for e in pg.list_task_events(task_id=t["id"])[:200]:
            items.append(
                {
                    "ts": _norm_ts(e.get("ts")),
                    "kind": "L5_TaskEvent",
                    "title": f"任务事件：{t.get('id')} · {e.get('event_type')}",
                    "detail": {"task_id": t.get("id"), "event_type": e.get("event_type"), "message": e.get("message")},
                }
            )
        for ev in pg.list_evidence(task_id=t["id"])[:200]:
            items.append(
                {
                    "ts": _norm_ts(ev.get("created_at")),
                    "kind": "L5_Evidence",
                    "title": f"证据：{ev.get('evidence_type')}",
                    "detail": {"task_id": t.get("id"), "evidence_id": ev.get("id"), "content": ev.get("content")},
                }
            )

    # 排序与截断
    items.sort(key=lambda x: x.get("ts") or "", reverse=True)
    return {"items": items[:limit]}
