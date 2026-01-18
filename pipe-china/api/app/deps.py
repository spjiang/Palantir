from __future__ import annotations

import os

from .ontology import OntologyStore
from .pg_store import PostgresStore

# 统一集中管理环境变量/依赖，避免各 router 重复定义导致多份连接
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j_demo_pass")

PG_DSN = os.getenv("PG_DSN", "").strip()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()

store = OntologyStore(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
pg = PostgresStore(PG_DSN) if PG_DSN else None

