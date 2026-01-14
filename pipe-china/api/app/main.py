from __future__ import annotations

import logging
import os
import traceback
import uuid
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    Entity,
    EntityCreate,
    EntityUpdate,
    DraftCommitRequest,
    DraftExtractResponse,
    GraphResponse,
    GraphQuery,
    ImportResult,
    Relation,
    RelationCreate,
    RelationUpdate,
)
from .ontology import OntologyStore


NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j_demo_pass")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()

store = OntologyStore(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

logger = logging.getLogger("pipe_china.api")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI(title="Pipe-China Ontology/行为建模 API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": store.health()}


@app.post("/ontology/extract", response_model=DraftExtractResponse)
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
        # 在容器日志中打印完整堆栈，便于定位
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


# 兼容旧前端：保留 /ontology/import，但语义改为 extract（不落库）
@app.post("/ontology/import", response_model=DraftExtractResponse)
async def import_alias(file: UploadFile = File(...)):
    return await extract_ontology(file)


@app.post("/ontology/commit", response_model=ImportResult)
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


@app.get("/ontology/drafts/{draft_id}/entities", response_model=list[Entity])
def list_draft_entities(draft_id: str, limit: int = 2000):
    try:
        return store.list_draft_entities(draft_id, limit=limit)
    except Exception as e:
        raise HTTPException(500, f"list draft entities failed: {e}")


@app.get("/ontology/drafts/{draft_id}/relations", response_model=list[Relation])
def list_draft_relations(draft_id: str, limit: int = 5000):
    try:
        return store.list_draft_relations(draft_id, limit=limit)
    except Exception as e:
        raise HTTPException(500, f"list draft relations failed: {e}")


@app.post("/ontology/drafts/{draft_id}/entities", response_model=Entity)
def create_draft_entity(draft_id: str, payload: EntityCreate):
    try:
        # 生成草稿实体 id（与正式库隔离）
        entity_id = f"ent-manual-{uuid.uuid4().hex[:10]}"
        return store.upsert_draft_entity_by_id(draft_id, entity_id, payload.name, payload.label, payload.props or {})
    except Exception as e:
        raise HTTPException(500, f"create draft entity failed: {e}")


@app.post("/ontology/drafts/{draft_id}/relations", response_model=Relation)
def create_draft_relation(draft_id: str, payload: RelationCreate):
    try:
        rel_id = f"rel-manual-{uuid.uuid4().hex[:10]}"
        return store.upsert_draft_relation_by_id(draft_id, rel_id, payload.src, payload.dst, payload.type, payload.props or {})
    except Exception as e:
        raise HTTPException(500, f"create draft relation failed: {e}")


@app.post("/ontology/drafts/{draft_id}/graph", response_model=GraphResponse)
def draft_graph(draft_id: str, query: GraphQuery):
    try:
        nodes, edges = store.query_draft_graph(draft_id, query.root_id, max(1, min(query.depth, 4)))
        return GraphResponse(nodes=nodes, edges=edges)
    except Exception as e:
        raise HTTPException(500, f"query draft graph failed: {e}")


@app.put("/ontology/drafts/{draft_id}/entities/{entity_id}", response_model=Entity)
def update_draft_entity(draft_id: str, entity_id: str, payload: EntityUpdate):
    try:
        # draft 里必须给 name/label（若不传则保持原值）
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


@app.delete("/ontology/drafts/{draft_id}/entities/{entity_id}", response_model=dict)
def delete_draft_entity(draft_id: str, entity_id: str):
    try:
        store.delete_draft_entity(draft_id, entity_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, f"delete draft entity failed: {e}")


@app.put("/ontology/drafts/{draft_id}/relations/{rel_id}", response_model=Relation)
def upsert_draft_relation(draft_id: str, rel_id: str, payload: RelationUpdate):
    try:
        # 关系必须存在端点；若未传则保持原值
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


@app.delete("/ontology/drafts/{draft_id}/relations/{rel_id}", response_model=dict)
def delete_draft_relation(draft_id: str, rel_id: str):
    try:
        store.delete_draft_relation(draft_id, rel_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, f"delete draft relation failed: {e}")


@app.post("/ontology/drafts/{draft_id}/commit", response_model=ImportResult)
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


@app.delete("/ontology/drafts/{draft_id}", response_model=dict)
def delete_draft(draft_id: str):
    try:
        store.delete_draft(draft_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, f"delete draft failed: {e}")


@app.post("/ontology/admin/purge", response_model=dict)
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


@app.post("/ontology/entities", response_model=Entity)
def create_entity(payload: EntityCreate):
    try:
        return store.upsert_entity(payload.name, payload.label, payload.props)
    except Exception as e:
        raise HTTPException(500, f"create entity failed: {e}")


@app.get("/ontology/entities", response_model=list[Entity])
def list_entities(limit: int = 500):
    try:
        return store.list_entities(limit=limit)
    except Exception as e:
        raise HTTPException(500, f"list entities failed: {e}")


@app.put("/ontology/entities/{entity_id}", response_model=Entity)
def update_entity(entity_id: str, payload: EntityUpdate):
    try:
        return store.update_entity(entity_id, payload.name, payload.label, payload.props)
    except ValueError:
        raise HTTPException(404, "entity not found")
    except Exception as e:
        raise HTTPException(500, f"update entity failed: {e}")


@app.delete("/ontology/entities/{entity_id}", response_model=dict)
def delete_entity(entity_id: str):
    try:
        store.delete_entity(entity_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, f"delete entity failed: {e}")


@app.post("/ontology/relations", response_model=Relation)
def create_relation(payload: RelationCreate):
    try:
        return store.create_relation(payload.src, payload.dst, payload.type, payload.props)
    except Exception as e:
        raise HTTPException(500, f"create relation failed: {e}")

@app.get("/ontology/relations", response_model=list[Relation])
def list_relations(limit: int = 2000):
    try:
        return store.list_relations(limit=limit)
    except Exception as e:
        raise HTTPException(500, f"list relations failed: {e}")


@app.put("/ontology/relations/{rel_id}", response_model=Relation)
def update_relation(rel_id: str, payload: RelationUpdate):
    try:
        return store.update_relation(rel_id, payload.type, payload.src, payload.dst, payload.props)
    except ValueError:
        raise HTTPException(404, "relation not found")
    except Exception as e:
        raise HTTPException(500, f"update relation failed: {e}")


@app.delete("/ontology/relations/{rel_id}", response_model=dict)
def delete_relation(rel_id: str):
    try:
        store.delete_relation(rel_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, f"delete relation failed: {e}")


@app.post("/ontology/graph", response_model=GraphResponse)
def graph(query: GraphQuery):
    try:
        nodes, edges = store.query_graph(query.root_id, max(1, min(query.depth, 4)))
        return GraphResponse(nodes=nodes, edges=edges)
    except Exception as e:
        raise HTTPException(500, f"query graph failed: {e}")


@app.get("/ontology/search", response_model=list[Entity])
def search(q: str):
    try:
        return store.search_entities(q, limit=30)
    except Exception as e:
        raise HTTPException(500, f"search failed: {e}")


@app.on_event("shutdown")
def shutdown_event():
    store.close()
