from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from openai import OpenAI

from ...deps import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, pg, store

router = APIRouter(tags=["L4-AgentDecisionMaking"])


def _require_pg():
    if not pg:
        raise HTTPException(500, "PG_DSN not configured")
    try:
        pg.connect()
    except Exception as e:
        raise HTTPException(500, f"Postgres not ready: {e}")


def _segment_node_id(segment_id: str) -> str:
    return f"ent-l1-{segment_id}"


class AgentDecideRequest(BaseModel):
    draft_id: str = Field(..., description="使用哪个草稿本体做决策（draft_id）")
    segment_id: str = Field(..., description="L1 管段ID（seg-xxx）")
    min_risk_state: str = Field(default="异常", description="达到该风险状态才生成任务：波动/异常/高风险")
    task_type: str = Field(default="巡检", description="任务类型：巡检/处置/复核")


class AgentDecideFromAlertRequest(BaseModel):
    draft_id: str = Field(..., description="草稿图谱 draft_id（用于读取本体行为/规则并回写任务）")
    alarm_id: str = Field(..., description="L3 生成的预警/告警结论 ID（alm-xxx）")
    task_type: str = Field(default="巡检", description="任务类型：巡检/处置/复核（可由大模型覆盖）")


def _llm_decide_task(*, alarm: dict[str, Any], behaviors: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    可选：调用 DeepSeek（若配置了 key）让大模型从候选行为中选择，并给出任务标题/说明。
    没有 key 时返回 None，走确定性兜底。
    """
    if not DEEPSEEK_API_KEY:
        return None
    try:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        prompt = {
            "role": "user",
            "content": (
                "你是油气管网运维的智能体决策模块（L4）。\n"
                "给定一条预警（告警结论）与候选行为列表，请选择最合适的行为并生成一个运维任务。\n"
                "只输出严格 JSON：{ \"task_type\": \"巡检|处置|复核\", \"title\": \"...\", \"reason\": \"...\", \"chosen_behavior\": \"...\" }\n\n"
                f"预警（alarm）：{alarm}\n\n"
                f"候选行为（behaviors）：{behaviors}\n"
            ),
        }
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL or "deepseek-chat",
            messages=[prompt],
            temperature=0.2,
        )
        text = (resp.choices[0].message.content or "").strip()
        import json

        return json.loads(text)
    except Exception:
        return None


@router.post("/agent/decide")
def decide(payload: AgentDecideRequest):
    """
    一个“可跑通闭环”的确定性智能体：
    - 输入：L2 草稿本体（draft_id）+ L1 管段（segment_id）
    - 读取：最新 risk_events（来自 L3），以及草稿图谱里的 behaviors/rules（用于解释与命名）
    - 输出：创建 L5 任务（写入 Postgres tasks），并回写到草稿图谱（MaintenanceTask + targets）
    """
    _require_pg()

    seg = pg.fetchone("SELECT * FROM pipeline_segments WHERE id=%s;", (payload.segment_id,))
    if not seg:
        raise HTTPException(404, "segment not found")

    # 取最新风险事件（优先匹配 draft_id+segment_id）
    risks = pg.list_risk_events(draft_id=payload.draft_id, segment_id=payload.segment_id, limit=1)
    if not risks:
        risks = pg.list_risk_events(segment_id=payload.segment_id, limit=1)
    if not risks:
        raise HTTPException(400, "no risk event yet. please run L3 /risk/evaluate first.")
    risk = risks[0]

    state = (risk.get("risk_state") or "").strip()
    score = float(risk.get("risk_score") or 0.0)

    order = {"正常": 0, "波动": 1, "异常": 2, "高风险": 3}
    if order.get(state, 0) < order.get(payload.min_risk_state, 2):
        return {"ok": True, "created": False, "reason": f"风险状态={state} 未达到触发阈值 {payload.min_risk_state}", "risk": risk}

    # 从 L2 草稿中挑一个“推荐行为”（用于标题解释）
    behaviors = [e for e in store.list_draft_entities(payload.draft_id, limit=5000) if (e.label or "") == "Behavior"]
    preferred_beh = None
    # 简单策略：高风险优先“处置”，否则“巡检/复核”
    if state == "高风险":
        preferred_beh = next((b for b in behaviors if "处置" in (b.name or "")), None) or (behaviors[0] if behaviors else None)
    else:
        preferred_beh = next((b for b in behaviors if "巡检" in (b.name or "")), None) or next((b for b in behaviors if "复核" in (b.name or "")), None) or (behaviors[0] if behaviors else None)

    beh_name = preferred_beh.name if preferred_beh else None
    title = f"{payload.task_type}任务：{seg['name']}（{state}，score={score:.2f}）"
    if beh_name:
        title = f"{title} · 来源行为：{beh_name}"

    # 创建 L5 任务（落库 Postgres）
    task = pg.create_task(
        title=title,
        task_type=payload.task_type,
        draft_id=payload.draft_id,
        target_entity_id=_segment_node_id(payload.segment_id),
        target_entity_name=seg["name"],
        source_behavior=beh_name,
    )

    # 回写到 L2 草稿图谱：任务节点 + targets 关系（让 L2 图谱能看到“任务闭环”）
    try:
        store.upsert_draft_entity_by_id(
            payload.draft_id,
            task["id"],
            name=task["title"],
            label="MaintenanceTask",
            props={
                "source": "l4",
                "task_type": task["task_type"],
                "status": task["status"],
                "risk_state": state,
                "risk_score": score,
                "risk_event_id": risk.get("id"),
                "source_behavior": beh_name,
            },
        )
        rel_id = f"rel-l4-targets-{task['id']}"
        store.upsert_draft_relation_by_id(
            payload.draft_id,
            rel_id,
            src=task["id"],
            dst=_segment_node_id(payload.segment_id),
            rel_type="targets",
            props={"source": "l4"},
        )
    except Exception as e:
        raise HTTPException(500, f"task created but failed to write back to draft graph: {e}")

    return {"ok": True, "created": True, "task": task, "risk": risk}


@router.post("/agent/decide_from_alert")
def decide_from_alert(payload: AgentDecideFromAlertRequest):
    """
    从“预警/告警结论（L3 输出）”触发 L4 决策，生成任务并回写草稿图谱。
    - 输入：draft_id + alarm_id
    - 图谱查询：根据 alarm.raw.rule_id 找到关联 Rule，再通过 “约束” 找到 Behavior 候选
    - 输出：创建 L5 任务（Postgres），并回写草稿图谱 targets
    """
    _require_pg()
    alarm = pg.fetchone("SELECT * FROM alarms WHERE id=%s;", (payload.alarm_id,))
    if not alarm:
        raise HTTPException(404, "alarm not found")
    raw = alarm.get("raw") if isinstance(alarm.get("raw"), dict) else {}
    rule_id = (raw.get("rule_id") or "").strip() if isinstance(raw, dict) else ""
    if not rule_id:
        raise HTTPException(400, "alarm has no rule_id in raw; cannot map to behaviors")

    # segment
    seg_id = alarm.get("segment_id")
    if not seg_id:
        raise HTTPException(400, "alarm has no segment_id")
    seg = pg.fetchone("SELECT * FROM pipeline_segments WHERE id=%s;", (seg_id,))
    seg_name = seg.get("name") if seg else (alarm.get("segment_id") or "")

    # behaviors candidates from draft graph
    ents = store.list_draft_entities(payload.draft_id, limit=5000)
    rels = store.list_draft_relations(payload.draft_id, limit=20000)
    id_to_ent = {e.id: e for e in ents}
    candidates = []
    for r in rels:
        if (r.type or "") == "约束" and r.src == rule_id:
            b = id_to_ent.get(r.dst)
            if b and (b.label or "") == "Behavior":
                candidates.append({"id": b.id, "name": b.name, "props": b.props or {}})

    llm = _llm_decide_task(alarm=alarm, behaviors=candidates) if candidates else None
    chosen_behavior = None
    task_type = payload.task_type
    reason = None
    title = f"{task_type}任务：{seg_name} · 预警={alarm.get('alarm_type')}({alarm.get('severity')})"
    if llm:
        task_type = llm.get("task_type") or task_type
        title = llm.get("title") or title
        reason = llm.get("reason")
        chosen_behavior = llm.get("chosen_behavior")
    else:
        # 兜底：优先取候选中的第一个
        chosen_behavior = candidates[0]["name"] if candidates else None
        reason = "未配置大模型，使用确定性规则：取 Rule 约束的首个 Behavior"

    task = pg.create_task(
        title=f"{title}{(' · 来源行为：' + chosen_behavior) if chosen_behavior else ''}",
        task_type=task_type,
        draft_id=payload.draft_id,
        target_entity_id=_segment_node_id(seg_id),
        target_entity_name=seg_name,
        source_behavior=chosen_behavior,
    )

    # 回写草稿图谱：任务节点 + targets
    try:
        # 确保“目标管段实例”节点存在（避免仅通过 L3 回写时才有）
        store.upsert_draft_entity_by_id(
            payload.draft_id,
            _segment_node_id(seg_id),
            name=seg_name,
            label="PipelineSegment",
            props={"source": "l1", "pg_id": seg_id},
        )

        # 确保“预警/告警结论”节点存在（用于 has_evidence）
        store.upsert_draft_entity_by_id(
            payload.draft_id,
            payload.alarm_id,
            name=f"{alarm.get('alarm_type')}（{alarm.get('severity')}）",
            label="Alarm",
            props={
                "source": "l3",
                "pg_alarm_id": payload.alarm_id,
                "alarm_type": alarm.get("alarm_type"),
                "severity": alarm.get("severity"),
                "message": alarm.get("message"),
                "rule_id": rule_id,
            },
        )

        store.upsert_draft_entity_by_id(
            payload.draft_id,
            task["id"],
            name=task["title"],
            label="MaintenanceTask",
            props={
                "source": "l4",
                "task_type": task["task_type"],
                "status": task["status"],
                "alarm_id": payload.alarm_id,
                "rule_id": rule_id,
                "source_behavior": chosen_behavior,
                "reason": reason,
            },
        )
        store.upsert_draft_relation_by_id(
            payload.draft_id,
            f"rel-l4-targets-{task['id']}",
            src=task["id"],
            dst=_segment_node_id(seg_id),
            rel_type="targets",
            props={"source": "l4"},
        )
        # 可选：task -> alarm（证据/线索）
        store.upsert_draft_relation_by_id(
            payload.draft_id,
            f"rel-l4-has_evidence-{task['id']}",
            src=task["id"],
            dst=payload.alarm_id,
            rel_type="has_evidence",
            props={"source": "l4"},
        )
    except Exception as e:
        raise HTTPException(500, f"task created but failed to write back to draft graph: {e}")

    return {"ok": True, "task": task, "alarm": alarm, "behaviors": candidates, "llm_used": bool(llm), "reason": reason}
