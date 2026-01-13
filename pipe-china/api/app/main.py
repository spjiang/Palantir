from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    Entity,
    EntityCreate,
    GraphResponse,
    GraphQuery,
    ImportResult,
    Relation,
    RelationCreate,
)
from .ontology import OntologyStore


NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j_demo_pass")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()

store = OntologyStore(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

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


@app.post("/ontology/import", response_model=ImportResult)
async def import_doc(file: UploadFile = File(...)):
    """
    上传 `需求文档.md`，仅使用 DeepSeek 进行本体抽取（实体/关系/规则）并写入图数据库。
    不提供词法切分/回退模式。
    """
    text = (await file.read()).decode("utf-8", errors="ignore")
    try:
        if not DEEPSEEK_API_KEY:
            raise HTTPException(400, "DEEPSEEK_API_KEY is empty. Please set it and retry.")

        return await store.import_from_deepseek(
            text,
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            model=DEEPSEEK_MODEL,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"import failed: {e}")


@app.post("/ontology/entities", response_model=Entity)
def create_entity(payload: EntityCreate):
    try:
        return store.upsert_entity(payload.name, payload.label, payload.props)
    except Exception as e:
        raise HTTPException(500, f"create entity failed: {e}")


@app.post("/ontology/relations", response_model=Relation)
def create_relation(payload: RelationCreate):
    try:
        return store.create_relation(payload.src, payload.dst, payload.type, payload.props)
    except Exception as e:
        raise HTTPException(500, f"create relation failed: {e}")


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
