from __future__ import annotations

import json
import logging
import traceback
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from ...deps import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, store
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
        # 写入“临时图谱”（与正式图谱隔离），供该文档的图查询/编辑使用
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
                    # 写入“临时图谱”（与正式图谱隔离），供该文档的图查询/编辑使用
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
def commit_draft(draft_id: str, delete_after: bool = True):
    try:
        created_nodes, created_edges = store.commit_draft_id(draft_id, delete_after=delete_after)
        return ImportResult(
            created_nodes=created_nodes,
            created_edges=created_edges,
            sample_nodes=[],
            sample_edges=[],
            mode="commit",
            llm_enabled=True,
            fallback_used=False,
            message=f"入库成功（draft_id={draft_id}）",
        )
    except Exception as e:
        raise HTTPException(500, f"commit draft failed: {e}")


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

