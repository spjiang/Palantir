from __future__ import annotations

import re
import uuid
from typing import Iterable, List, Tuple

from neo4j import GraphDatabase, Driver

from .models import Entity, Relation, ImportResult


class OntologyStore:
    """
    轻量封装 Neo4j：
    - 实体节点：(:Concept {id, name, label, props})
    - 关系边：  (src)-[:TYPE {id, props}]->(dst)
    """

    def __init__(self, uri: str, user: str, password: str):
        self.driver: Driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        self.driver.close()

    def health(self) -> bool:
        try:
            with self.driver.session() as session:
                result = session.run("RETURN 1 AS ok").single()
                return bool(result and result["ok"] == 1)
        except Exception:
            return False

    def upsert_entity(self, name: str, label: str, props: dict) -> Entity:
        node_id = f"ent-{uuid.uuid4().hex[:8]}"
        query = """
        MERGE (n:Concept {name:$name})
        SET n.id = coalesce(n.id, $id),
            n.label = $label,
            n.props = coalesce(n.props, {}) + $props
        RETURN n.id AS id, n.label AS label, n.name AS name, n.props AS props
        """
        with self.driver.session() as session:
            rec = session.run(query, name=name, id=node_id, label=label, props=props or {}).single()
        return Entity(**rec.data())

    def create_relation(self, src: str, dst: str, rel_type: str, props: dict) -> Relation:
        rel_id = f"rel-{uuid.uuid4().hex[:8]}"
        query = """
        MATCH (s {id:$src})
        MATCH (d {id:$dst})
        MERGE (s)-[r:REL {type:$type}]->(d)
        SET r.id = coalesce(r.id, $id),
            r.props = coalesce(r.props, {}) + $props
        RETURN r.id AS id, r.type AS type, s.id AS src, d.id AS dst, r.props AS props
        """
        with self.driver.session() as session:
            rec = session.run(query, src=src, dst=dst, type=rel_type, id=rel_id, props=props or {}).single()
        return Relation(**rec.data())

    def query_graph(self, root_id: str | None, depth: int) -> Tuple[List[Entity], List[Relation]]:
        if root_id:
            query = """
            MATCH p=(n {id:$root})-[*1..$depth]->(m)
            WITH nodes(p) AS ns, relationships(p) AS rs
            RETURN ns, rs
            UNION
            MATCH p=(n {id:$root})<-[*1..$depth]-(m)
            WITH nodes(p) AS ns, relationships(p) AS rs
            RETURN ns, rs
            """
            params = {"root": root_id, "depth": depth}
        else:
            query = """
            MATCH p=()-[r]->()
            WITH nodes(p) AS ns, relationships(p) AS rs
            RETURN ns, rs LIMIT 200
            """
            params = {}

        nodes: dict[str, Entity] = {}
        edges: dict[str, Relation] = {}
        with self.driver.session() as session:
            for rec in session.run(query, **params):
                for n in rec["ns"]:
                    nodes[n["id"]] = Entity(id=n["id"], label=n.get("label", "Concept"), name=n["name"], props=n.get("props", {}))
                for r in rec["rs"]:
                    rid = r.get("id") or f"rel-{uuid.uuid4().hex[:8]}"
                    edges[rid] = Relation(
                        id=rid,
                        type=r.get("type", "RELATED_TO"),
                        src=r.start_node["id"],
                        dst=r.end_node["id"],
                        props=r.get("props", {}),
                    )
        return list(nodes.values()), list(edges.values())

    def search_entities(self, keyword: str, limit: int = 20) -> List[Entity]:
        query = """
        MATCH (n:Concept)
        WHERE toLower(n.name) CONTAINS toLower($kw)
        RETURN n.id AS id, n.label AS label, n.name AS name, n.props AS props
        LIMIT $limit
        """
        with self.driver.session() as session:
            return [Entity(**rec.data()) for rec in session.run(query, kw=keyword, limit=limit)]

    # ---------- 文本解析为简单本体 ----------

    def import_from_text(self, text: str) -> ImportResult:
        sentences = self._split_sentences(text)
        tokens = self._extract_tokens(sentences)
        entities = [self.upsert_entity(name=t, label="Concept", props={"source": "import"}) for t in tokens]

        edges: list[Relation] = []
        # 简单把相邻词汇链接，形成可视化骨架
        for a, b in zip(entities, entities[1:]):
            rel = self.create_relation(a.id, b.id, "RELATED_TO", {"source": "co_occurrence"})
            edges.append(rel)

        return ImportResult(
            created_nodes=len(entities),
            created_edges=len(edges),
            sample_nodes=entities[:5],
            sample_edges=edges[:5],
        )

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        parts = re.split(r"[。；;.!?\n]", text)
        return [p.strip() for p in parts if p.strip()]

    @staticmethod
    def _extract_tokens(sentences: Iterable[str]) -> list[str]:
        tokens: list[str] = []
        for sent in sentences:
            for token in re.findall(r"[A-Za-z0-9\u4e00-\u9fa5]{2,12}", sent):
                if len(token) < 2:
                    continue
                tokens.append(token)
        # 去重保序
        seen = set()
        uniq = []
        for t in tokens:
            if t in seen:
                continue
            seen.add(t)
            uniq.append(t)
        return uniq[:40]
