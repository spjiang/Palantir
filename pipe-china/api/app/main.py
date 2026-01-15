from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .deps import store
from .layers.l1_data_ingestion_governance.router import router as l1_router
from .layers.l2_ontology_semantics.router import router as l2_router
from .layers.l3_risk_reasoning_models.router import router as l3_router
from .layers.l4_agent_decision_making.router import router as l4_router
from .layers.l5_closed_loop_execution_workflow.router import router as l5_router
from .layers.l6_reports_traceability.router import router as l6_router

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


# -------- 路由挂载（按 L1~L6 拆分）--------
app.include_router(l1_router)
app.include_router(l2_router)
app.include_router(l3_router)
app.include_router(l4_router)
app.include_router(l5_router)
app.include_router(l6_router)


@app.on_event("shutdown")
def shutdown_event():
    store.close()

