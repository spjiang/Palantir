from __future__ import annotations

import json
import hashlib
import logging
import traceback
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from ...deps import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, pg, store
from ...models import (
    DraftCommitRequest,
    DraftExtractResponse,
    Entity,
    EntityCreate,
    EntityUpdate,
    GraphQuery,
    GraphResponse,
    ImportResult,
    Relation,
    RelationCreate,
    RelationUpdate,
)

logger = logging.getLogger("pipe_china.api")

router = APIRouter(tags=["L2-OntologySemantics"])

def _require_pg():
    if not pg:
        raise HTTPException(500, "PG_DSN not configured")
    try:
        pg.connect()
    except Exception as e:
        raise HTTPException(500, f"Postgres not ready: {e}")


@router.get("/ontology/drafts")
def list_drafts(limit: int = 50):
    """
    列出当前存在的草稿 draft_id（用于下拉选择）。
    """
    limit = max(1, min(int(limit or 50), 200))
    return {"items": store.list_draft_ids(limit=limit)}


@router.post("/ontology/extract", response_model=DraftExtractResponse)
async def extract_ontology(file: UploadFile = File(...)):
    """
    上传 `需求文档.md`，仅使用 DeepSeek 进行本体抽取（实体/关系/规则），先返回草稿（不入库）。
    """
    text = (await file.read()).decode("utf-8", errors="ignore")
    try:
        if not DEEPSEEK_API_KEY:
            raise HTTPException(400, "DEEPSEEK_API_KEY is empty. Please set it and retry.")

        draft_id, nodes, edges = await store.extract_draft_from_deepseek(
            text,
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            model=DEEPSEEK_MODEL,
        )
        # 写入“临时本体库”（与正式本体库隔离），供该文档的查询/编辑使用
        store.save_draft(draft_id, nodes, edges)
        return DraftExtractResponse(draft_id=draft_id, nodes=nodes, edges=edges)
    except HTTPException:
        raise
    except Exception as e:
        error_id = f"err-{uuid.uuid4().hex[:10]}"
        logger.error("import failed (error_id=%s): %s", error_id, repr(e))
        logger.error("traceback (error_id=%s):\n%s", error_id, traceback.format_exc())

        msg = str(e).strip() or repr(e)
        raise HTTPException(
            500,
            detail={
                "error_id": error_id,
                "error_type": type(e).__name__,
                "message": msg,
                "hint": "请查看服务端日志：docker logs pipe-china-api --tail=200",
            },
        )


@router.post("/ontology/extract/stream")
async def extract_ontology_stream(file: UploadFile = File(...)):
    """
    流式抽取：实时返回 DeepSeek 输出 token（SSE），最终发送 done({draft_id,nodes,edges})。
    前端用于“高级感”的实时展示。
    """
    text = (await file.read()).decode("utf-8", errors="ignore")
    if not DEEPSEEK_API_KEY:
        raise HTTPException(400, "DEEPSEEK_API_KEY is empty. Please set it and retry.")

    def sse(event: str, data) -> bytes:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")

    def gen():
        yield sse("status", {"stage": "start", "message": "开始调用 DeepSeek（流式）…"})
        try:
            for item in store.extract_draft_from_deepseek_stream(
                text,
                api_key=DEEPSEEK_API_KEY,
                base_url=DEEPSEEK_BASE_URL,
                model=DEEPSEEK_MODEL,
            ):
                if item.get("event") == "token":
                    yield sse("token", {"text": item.get("data", "")})
                elif item.get("event") == "done":
                    data = item.get("data") or {}
                    # 写入“临时本体库”（与正式本体库隔离），供该文档的查询/编辑使用
                    draft_id = data.get("draft_id")
                    nodes = data.get("nodes") or []
                    edges = data.get("edges") or []
                    store.save_draft(
                        draft_id,
                        [Entity(**n) for n in nodes],
                        [Relation(**e) for e in edges],
                    )
                    yield sse("done", {"draft_id": draft_id, "nodes": nodes, "edges": edges})
        except Exception as e:
            error_id = f"err-{uuid.uuid4().hex[:10]}"
            logger.error("extract stream failed (error_id=%s): %s", error_id, repr(e))
            logger.error("traceback (error_id=%s):\n%s", error_id, traceback.format_exc())
            yield sse(
                "error",
                {
                    "error_id": error_id,
                    "error_type": type(e).__name__,
                    "message": str(e).strip() or repr(e),
                    "hint": "请查看服务端日志：docker logs pipe-china-api --tail=200",
                },
            )

    return StreamingResponse(gen(), media_type="text/event-stream")


# 兼容旧前端：保留 /ontology/import，但语义改为 extract（不落库）
@router.post("/ontology/import", response_model=DraftExtractResponse)
async def import_alias(file: UploadFile = File(...)):
    return await extract_ontology(file)


@router.post("/ontology/commit", response_model=ImportResult)
def commit_ontology(req: DraftCommitRequest):
    """
    用户在页面编辑草稿后点击“确认入库”，才把本体与关系写入 Neo4j。
    """
    try:
        created_nodes, created_edges = store.commit_draft(req.nodes, req.edges)
        return ImportResult(
            created_nodes=created_nodes,
            created_edges=created_edges,
            sample_nodes=req.nodes[:5],
            sample_edges=req.edges[:5],
            mode="commit",
            llm_enabled=True,
            fallback_used=False,
            message=f"入库成功（draft_id={req.draft_id or '-'}）",
        )
    except Exception as e:
        raise HTTPException(500, f"commit failed: {e}")


@router.get("/ontology/drafts/{draft_id}/entities", response_model=list[Entity])
def list_draft_entities(draft_id: str, limit: int = 2000):
    try:
        return store.list_draft_entities(draft_id, limit=limit)
    except Exception as e:
        raise HTTPException(500, f"list draft entities failed: {e}")


@router.get("/ontology/drafts/{draft_id}/relations", response_model=list[Relation])
def list_draft_relations(draft_id: str, limit: int = 5000):
    try:
        return store.list_draft_relations(draft_id, limit=limit)
    except Exception as e:
        raise HTTPException(500, f"list draft relations failed: {e}")


@router.get("/ontology/stats")
def formal_stats():
    """
    正式本体库统计（不受 /ontology/relations limit 影响）。
    """
    try:
        return store.formal_stats()
    except Exception as e:
        raise HTTPException(500, f"formal stats failed: {e}")


@router.get("/ontology/drafts/{draft_id}/stats")
def draft_stats(draft_id: str):
    """
    临时本体库统计（按 draft_id 隔离）。
    """
    try:
        return store.draft_stats(draft_id)
    except Exception as e:
        raise HTTPException(500, f"draft stats failed: {e}")


@router.post("/ontology/drafts/{draft_id}/entities", response_model=Entity)
def create_draft_entity(draft_id: str, payload: EntityCreate):
    try:
        entity_id = payload.id or f"ent-manual-{uuid.uuid4().hex[:10]}"
        return store.upsert_draft_entity_by_id(draft_id, entity_id, payload.name, payload.label, payload.props or {})
    except Exception as e:
        raise HTTPException(500, f"create draft entity failed: {e}")


@router.post("/ontology/drafts/{draft_id}/relations", response_model=Relation)
def create_draft_relation(draft_id: str, payload: RelationCreate):
    try:
        rel_id = payload.id or f"rel-manual-{uuid.uuid4().hex[:10]}"
        return store.upsert_draft_relation_by_id(draft_id, rel_id, payload.src, payload.dst, payload.type, payload.props or {})
    except Exception as e:
        raise HTTPException(500, f"create draft relation failed: {e}")


@router.post("/ontology/drafts/{draft_id}/graph", response_model=GraphResponse)
def draft_graph(draft_id: str, query: GraphQuery):
    try:
        nodes, edges = store.query_draft_graph(draft_id, query.root_id, max(1, min(query.depth, 4)))
        return GraphResponse(nodes=nodes, edges=edges)
    except Exception as e:
        raise HTTPException(500, f"query draft graph failed: {e}")


@router.put("/ontology/drafts/{draft_id}/entities/{entity_id}", response_model=Entity)
def update_draft_entity(draft_id: str, entity_id: str, payload: EntityUpdate):
    try:
        current = {e.id: e for e in store.list_draft_entities(draft_id, limit=5000)}.get(entity_id)
        if not current:
            raise HTTPException(404, "draft entity not found")
        name = payload.name or current.name
        label = payload.label or current.label
        props = current.props if payload.props is None else payload.props
        return store.upsert_draft_entity_by_id(draft_id, entity_id, name, label, props or {})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"update draft entity failed: {e}")


@router.delete("/ontology/drafts/{draft_id}/entities/{entity_id}", response_model=dict)
def delete_draft_entity(draft_id: str, entity_id: str):
    try:
        store.delete_draft_entity(draft_id, entity_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, f"delete draft entity failed: {e}")


@router.put("/ontology/drafts/{draft_id}/relations/{rel_id}", response_model=Relation)
def upsert_draft_relation(draft_id: str, rel_id: str, payload: RelationUpdate):
    try:
        current = {r.id: r for r in store.list_draft_relations(draft_id, limit=20000)}.get(rel_id)
        if not current:
            raise HTTPException(404, "draft relation not found")
        rel_type = payload.type or current.type
        src = payload.src or current.src
        dst = payload.dst or current.dst
        props = current.props if payload.props is None else payload.props
        return store.upsert_draft_relation_by_id(draft_id, rel_id, src, dst, rel_type, props or {})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"update draft relation failed: {e}")


@router.delete("/ontology/drafts/{draft_id}/relations/{rel_id}", response_model=dict)
def delete_draft_relation(draft_id: str, rel_id: str):
    try:
        store.delete_draft_relation(draft_id, rel_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, f"delete draft relation failed: {e}")


@router.post("/ontology/drafts/{draft_id}/commit", response_model=ImportResult)
def commit_draft(draft_id: str, delete_after: bool = True, note: str | None = None, actor: str | None = None):
    try:
        _require_pg()
        # 1) 取草稿快照
        nodes = store.list_draft_entities(draft_id, limit=5000)
        edges = store.list_draft_relations(draft_id, limit=20000)
        nodes_json = [n.model_dump() for n in nodes]
        edges_json = [e.model_dump() for e in edges]

        # 2) 发布前备份当前正式本体库（用于回滚）
        formal_nodes = store.list_entities(limit=5000)
        formal_edges = store.list_relations(limit=20000)
        if formal_nodes or formal_edges:
            pg.add_ontology_release(
                draft_id=None,
                note=f"auto-backup before publish draft_id={draft_id}",
                nodes=[n.model_dump() for n in formal_nodes],
                edges=[e.model_dump() for e in formal_edges],
            )
            pg.add_audit(actor=actor, action="ontology.backup", payload={"draft_id": draft_id, "note": "auto-backup"})

        # 3) 发布：替换正式本体库
        store.purge_formal()
        created_nodes, created_edges = store.commit_draft(nodes, edges)

        # 4) 记录发布版本
        rel = pg.add_ontology_release(
            draft_id=draft_id,
            note=note or f"publish draft_id={draft_id}",
            nodes=nodes_json,
            edges=edges_json,
        )
        pg.add_audit(actor=actor, action="ontology.publish", payload={"draft_id": draft_id, "release_id": rel.get("id"), "note": note})

        # 5) 需要的话删除草稿
        if delete_after:
            try:
                store.delete_draft(draft_id)
            except Exception:
                pass
        return ImportResult(
            created_nodes=created_nodes,
            created_edges=created_edges,
            sample_nodes=[],
            sample_edges=[],
            mode="commit",
            llm_enabled=True,
            fallback_used=False,
            message=f"发布成功（draft_id={draft_id}，release_id={rel.get('id')}）",
        )
    except Exception as e:
        raise HTTPException(500, f"commit draft failed: {e}")


@router.get("/ontology/releases")
def list_releases(limit: int = 50):
    _require_pg()
    return {"items": pg.list_ontology_releases(limit=limit)}


@router.post("/ontology/releases/{release_id}/rollback")
def rollback_release(release_id: str, actor: str | None = None):
    """
    回滚正式本体库到某个发布版本（最小实现：purge formal -> replay snapshot）。
    """
    _require_pg()
    rel = pg.get_ontology_release(release_id)
    if not rel:
        raise HTTPException(404, "release not found")
    nodes = rel.get("nodes") or []
    edges = rel.get("edges") or []
    try:
        store.purge_formal()
        created_nodes, created_edges = store.commit_draft(
            [Entity(**n) for n in nodes],
            [Relation(**e) for e in edges],
        )
        pg.add_audit(actor=actor, action="ontology.rollback", payload={"release_id": release_id, "created_nodes": created_nodes, "created_edges": created_edges})
        return {"ok": True, "release_id": release_id, "created_nodes": created_nodes, "created_edges": created_edges}
    except Exception as e:
        raise HTTPException(500, f"rollback failed: {e}")


@router.post("/ontology/drafts/{draft_id}/behavior_model/init", response_model=dict)
def init_behavior_model(draft_id: str):
    """
    初始化一套“可执行的行为建模模板”，用于让 L3/L4 直接读取本体建模数据跑通闭环：
    - 核心对象：管段/传感器/告警/运维任务/证据
    - 风险状态：正常/波动/异常/高风险
    - 行为：异常识别/风险评估/处置决策/执行处置/复核与回归
    - 规则：压力高阈值、流量低阈值（结构化字段 metric/op/threshold/weight）

    说明：
    - 该接口是“幂等 upsert”：重复调用会覆盖/补齐同 ID 的节点与关系，不会无限增长。
    - 初始化的是“模板语义”，L1 的真实管段实例由 L3 在评估时写回草稿（ent-l1-seg-xxx）。
    """

    def hid(s: str) -> str:
        return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]

    def eid(kind: str, name: str) -> str:
        return f"ent-bm-{kind}-{hid(f'{kind}:{name}')}"

    def rid(kind: str, src: str, typ: str, dst: str) -> str:
        return f"rel-bm-{kind}-{hid(f'{src}|{typ}|{dst}')}"

    # --- Objects ---
    obj_seg = store.upsert_draft_entity_by_id(draft_id, eid("obj", "管段"), "管段", "PipelineSegment", {"source": "behavior_model"})
    obj_sensor = store.upsert_draft_entity_by_id(draft_id, eid("obj", "传感器"), "传感器", "Sensor", {"source": "behavior_model"})
    obj_alarm = store.upsert_draft_entity_by_id(draft_id, eid("obj", "告警"), "告警", "Alarm", {"source": "behavior_model"})
    obj_task = store.upsert_draft_entity_by_id(draft_id, eid("obj", "运维任务"), "运维任务", "MaintenanceTask", {"source": "behavior_model"})
    obj_ev = store.upsert_draft_entity_by_id(draft_id, eid("obj", "证据"), "证据", "Evidence", {"source": "behavior_model"})

    # 模板对象之间也建立最小关系：管段 has_sensor 传感器（语义）
    store.upsert_draft_relation_by_id(
        draft_id,
        rid("obj", obj_seg.id, "has_sensor", obj_sensor.id),
        src=obj_seg.id,
        dst=obj_sensor.id,
        rel_type="has_sensor",
        props={"source": "behavior_model"},
    )

    # --- Risk States ---
    st_normal = store.upsert_draft_entity_by_id(draft_id, eid("state", "正常"), "正常", "RiskState", {"source": "behavior_model"})
    st_fluct = store.upsert_draft_entity_by_id(draft_id, eid("state", "波动"), "波动", "RiskState", {"source": "behavior_model"})
    st_abn = store.upsert_draft_entity_by_id(draft_id, eid("state", "异常"), "异常", "RiskState", {"source": "behavior_model"})
    st_high = store.upsert_draft_entity_by_id(draft_id, eid("state", "高风险"), "高风险", "RiskState", {"source": "behavior_model"})

    # --- Behaviors ---
    beh_detect = store.upsert_draft_entity_by_id(
        draft_id,
        eid("beh", "异常识别（DetectAnomaly）"),
        "异常识别（DetectAnomaly）",
        "Behavior",
        {
            "source": "behavior_model",
            "preconditions": ["出现压力/流量异常读数或告警"],
            "inputs": ["sensor_readings", "alarms"],
            "outputs": ["Alarm"],
            "effects": ["将管段风险状态从正常/波动推进至异常"],
        },
    )
    beh_assess = store.upsert_draft_entity_by_id(
        draft_id,
        eid("beh", "风险评估（AssessRisk）"),
        "风险评估（AssessRisk）",
        "Behavior",
        {
            "source": "behavior_model",
            "preconditions": ["存在异常告警或异常识别输出"],
            "inputs": ["alarms", "recent_readings"],
            "outputs": ["risk_score", "RiskState"],
            "effects": ["更新管段风险状态（异常/高风险）并给出解释"],
        },
    )
    beh_decide = store.upsert_draft_entity_by_id(
        draft_id,
        eid("beh", "处置决策（DecideResponseAction）"),
        "处置决策（DecideResponseAction）",
        "Behavior",
        {
            "source": "behavior_model",
            "preconditions": ["风险状态达到异常/高风险"],
            "inputs": ["RiskState", "rules"],
            "outputs": ["MaintenanceTask"],
            "effects": ["生成巡检/处置/复核任务并绑定目标管段"],
        },
    )
    beh_exec = store.upsert_draft_entity_by_id(
        draft_id,
        eid("beh", "执行处置（ExecuteMaintenance）"),
        "执行处置（ExecuteMaintenance）",
        "Behavior",
        {
            "source": "behavior_model",
            "preconditions": ["存在待执行的运维任务"],
            "inputs": ["MaintenanceTask"],
            "outputs": ["Evidence"],
            "effects": ["产出证据并回写任务状态"],
        },
    )
    beh_verify = store.upsert_draft_entity_by_id(
        draft_id,
        eid("beh", "复核与回归（VerifyRecovery）"),
        "复核与回归（VerifyRecovery）",
        "Behavior",
        {
            "source": "behavior_model",
            "preconditions": ["处置完成后获取新一轮读数/复测结果"],
            "inputs": ["sensor_readings", "Evidence"],
            "outputs": ["RiskState"],
            "effects": ["风险状态回归正常或保持观察"],
        },
    )

    def link_affects(beh_id: str, obj_id: str):
        store.upsert_draft_relation_by_id(
            draft_id,
            rid("affects", beh_id, "作用于", obj_id),
            src=beh_id,
            dst=obj_id,
            rel_type="作用于",
            props={"source": "behavior_model"},
        )

    def link_produces(beh_id: str, obj_id: str):
        store.upsert_draft_relation_by_id(
            draft_id,
            rid("produces", beh_id, "产生", obj_id),
            src=beh_id,
            dst=obj_id,
            rel_type="产生",
            props={"source": "behavior_model"},
        )

    def link_state(beh_id: str, rel_type: str, st_id: str):
        store.upsert_draft_relation_by_id(
            draft_id,
            rid("state", beh_id, rel_type, st_id),
            src=beh_id,
            dst=st_id,
            rel_type=rel_type,
            props={"source": "behavior_model"},
        )

    # affects
    # 每个 Behavior 必须至少挂 1 个对象（commit 时会校验），这里统一补齐“作用于”关系。
    for b in [beh_detect, beh_assess, beh_decide, beh_exec, beh_verify]:
        link_affects(b.id, obj_seg.id)
    link_affects(beh_detect.id, obj_sensor.id)
    # 执行处置的直接输入是运维任务，因此也挂载到“运维任务”对象，便于 L4/L5 串联可执行闭环
    link_affects(beh_exec.id, obj_task.id)
    # produces
    link_produces(beh_detect.id, obj_alarm.id)
    link_produces(beh_decide.id, obj_task.id)
    link_produces(beh_exec.id, obj_ev.id)
    link_produces(beh_verify.id, obj_ev.id)
    # state transitions (用 RiskState 承载)
    link_state(beh_detect.id, "从状态", st_normal.id)
    link_state(beh_detect.id, "到状态", st_abn.id)
    link_state(beh_assess.id, "从状态", st_abn.id)
    link_state(beh_assess.id, "到状态", st_high.id)
    link_state(beh_verify.id, "从状态", st_high.id)
    link_state(beh_verify.id, "到状态", st_normal.id)

    # --- Rules (structure for L3 execution) ---
    rule_pressure = store.upsert_draft_entity_by_id(
        draft_id,
        eid("rule", "压力高阈值（PressureHigh）"),
        "压力高阈值（PressureHigh）",
        "Rule",
        {
            "source": "behavior_model",
            "trigger": "pressure > threshold",
            "action": "触发异常识别",
            # L3 可执行字段（关键）
            "metric": "pressure",
            "op": ">",
            "threshold": 8.5,
            "weight": 0.55,
            "severity": "high",
            "governs_behavior": beh_detect.name,
        },
    )
    rule_flow = store.upsert_draft_entity_by_id(
        draft_id,
        eid("rule", "流量低阈值（FlowLow）"),
        "流量低阈值（FlowLow）",
        "Rule",
        {
            "source": "behavior_model",
            "trigger": "flow < threshold",
            "action": "触发异常识别",
            "metric": "flow",
            "op": "<",
            "threshold": 60.0,
            "weight": 0.35,
            "severity": "medium",
            "governs_behavior": beh_detect.name,
        },
    )

    # rules -> behavior
    for r in [rule_pressure, rule_flow]:
        store.upsert_draft_relation_by_id(
            draft_id,
            rid("governs", r.id, "约束", beh_detect.id),
            src=r.id,
            dst=beh_detect.id,
            rel_type="约束",
            props={"source": "behavior_model"},
        )
        # rule involves segment
        store.upsert_draft_relation_by_id(
            draft_id,
            rid("involves", r.id, "涉及", obj_seg.id),
            src=r.id,
            dst=obj_seg.id,
            rel_type="涉及",
            props={"source": "behavior_model"},
        )

    return {
        "ok": True,
        "draft_id": draft_id,
        "message": "behavior model initialized",
    }


@router.delete("/ontology/drafts/{draft_id}", response_model=dict)
def delete_draft(draft_id: str):
    try:
        store.delete_draft(draft_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, f"delete draft failed: {e}")


@router.post("/ontology/admin/purge", response_model=dict)
def purge_all_graph(confirm: str = ""):
    """
    危险：一键清空图数据库（正式 + 临时）。
    需要显式传入 confirm=YES 才执行，避免误触。
    """
    if confirm != "YES":
        raise HTTPException(400, "missing confirm=YES")
    try:
        store.purge_all()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, f"purge failed: {e}")


@router.post("/ontology/entities", response_model=Entity)
def create_entity(payload: EntityCreate):
    try:
        if payload.id:
            return store.upsert_entity_by_id(payload.id, payload.name, payload.label, payload.props)
        return store.upsert_entity(payload.name, payload.label, payload.props)
    except Exception as e:
        raise HTTPException(500, f"create entity failed: {e}")


@router.get("/ontology/entities", response_model=list[Entity])
def list_entities(limit: int = 500):
    try:
        return store.list_entities(limit=limit)
    except Exception as e:
        raise HTTPException(500, f"list entities failed: {e}")


@router.put("/ontology/entities/{entity_id}", response_model=Entity)
def update_entity(entity_id: str, payload: EntityUpdate):
    try:
        return store.update_entity(entity_id, payload.name, payload.label, payload.props)
    except ValueError:
        raise HTTPException(404, "entity not found")
    except Exception as e:
        raise HTTPException(500, f"update entity failed: {e}")


@router.delete("/ontology/entities/{entity_id}", response_model=dict)
def delete_entity(entity_id: str):
    try:
        store.delete_entity(entity_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, f"delete entity failed: {e}")


@router.post("/ontology/relations", response_model=Relation)
def create_relation(payload: RelationCreate):
    try:
        return store.create_relation(payload.src, payload.dst, payload.type, payload.props, rel_id=payload.id)
    except Exception as e:
        raise HTTPException(500, f"create relation failed: {e}")


@router.get("/ontology/relations", response_model=list[Relation])
def list_relations(limit: int = 2000):
    try:
        return store.list_relations(limit=limit)
    except Exception as e:
        raise HTTPException(500, f"list relations failed: {e}")


@router.put("/ontology/relations/{rel_id}", response_model=Relation)
def update_relation(rel_id: str, payload: RelationUpdate):
    try:
        return store.update_relation(rel_id, payload.type, payload.src, payload.dst, payload.props)
    except ValueError:
        raise HTTPException(404, "relation not found")
    except Exception as e:
        raise HTTPException(500, f"update relation failed: {e}")


@router.delete("/ontology/relations/{rel_id}", response_model=dict)
def delete_relation(rel_id: str):
    try:
        store.delete_relation(rel_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, f"delete relation failed: {e}")


@router.post("/ontology/graph", response_model=GraphResponse)
def graph(query: GraphQuery):
    try:
        nodes, edges = store.query_graph(query.root_id, max(1, min(query.depth, 4)))
        return GraphResponse(nodes=nodes, edges=edges)
    except Exception as e:
        raise HTTPException(500, f"query graph failed: {e}")


@router.get("/ontology/search", response_model=list[Entity])
def search(q: str):
    try:
        return store.search_entities(q, limit=30)
    except Exception as e:
        raise HTTPException(500, f"search failed: {e}")

