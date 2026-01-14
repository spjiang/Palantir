from __future__ import annotations

import json
import re
import hashlib
import uuid
from typing import List, Tuple

from neo4j import GraphDatabase, Driver
from openai import OpenAI

from .models import Entity, Relation, ImportResult


class OntologyStore:
    """
    轻量封装 Neo4j：
    - 实体节点：(:Concept {id, name, label, props_json})
    - 关系边：  (src)-[:REL {id, type, props_json}]->(dst)

    草稿（临时图谱，按 draft_id 隔离）：
    - 实体节点：(:DraftConcept {draft_id, id, name, label, props_json})
    - 关系边：  (src)-[:DREL {draft_id, id, type, props_json}]->(dst)
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
        props_json = json.dumps(props or {}, ensure_ascii=False)
        query = """
        MERGE (n:Concept {name:$name})
        SET n.id = coalesce(n.id, $id),
            n.label = $label,
            n.props_json = $props_json
        RETURN n.id AS id, n.label AS label, n.name AS name, n.props_json AS props_json
        """
        with self.driver.session() as session:
            rec = session.run(query, name=name, id=node_id, label=label, props_json=props_json).single()
        data = rec.data()
        return Entity(id=data["id"], label=data.get("label", "Concept"), name=data["name"], props=self._loads_props(data.get("props_json")))

    def upsert_entity_by_id(self, entity_id: str, name: str, label: str, props: dict) -> Entity:
        """按 id 幂等写入（用于草稿确认入库）。"""
        props_json = json.dumps(props or {}, ensure_ascii=False)
        query = """
        MERGE (n:Concept {id:$id})
        SET n.name = $name,
            n.label = $label,
            n.props_json = $props_json
        RETURN n.id AS id, n.label AS label, n.name AS name, n.props_json AS props_json
        """
        with self.driver.session() as session:
            rec = session.run(query, id=entity_id, name=name, label=label, props_json=props_json).single()
        data = rec.data()
        return Entity(id=data["id"], label=data.get("label", "Concept"), name=data["name"], props=self._loads_props(data.get("props_json")))

    def create_relation(self, src: str, dst: str, rel_type: str, props: dict, *, rel_id: str | None = None) -> Relation:
        rel_id = rel_id or f"rel-{uuid.uuid4().hex[:8]}"
        props_json = json.dumps(props or {}, ensure_ascii=False)
        query = """
        MATCH (s {id:$src})
        MATCH (d {id:$dst})
        MERGE (s)-[r:REL {id:$id}]->(d)
        SET r.type = $type,
            r.props_json = $props_json
        RETURN r.id AS id, r.type AS type, s.id AS src, d.id AS dst, r.props_json AS props_json
        """
        with self.driver.session() as session:
            rec = session.run(query, src=src, dst=dst, type=rel_type, id=rel_id, props_json=props_json).single()
        data = rec.data()
        return Relation(id=data["id"], type=data.get("type", "RELATED_TO"), src=data["src"], dst=data["dst"], props=self._loads_props(data.get("props_json")))

    def upsert_relation_by_id(self, rel_id: str, src: str, dst: str, rel_type: str, props: dict) -> Relation:
        props_json = json.dumps(props or {}, ensure_ascii=False)
        query = """
        MATCH (s {id:$src})
        MATCH (d {id:$dst})
        MERGE (s)-[r:REL {id:$id}]->(d)
        SET r.type = $type,
            r.props_json = $props_json
        RETURN r.id AS id, r.type AS type, s.id AS src, d.id AS dst, r.props_json AS props_json
        """
        with self.driver.session() as session:
            rec = session.run(query, id=rel_id, src=src, dst=dst, type=rel_type, props_json=props_json).single()
        data = rec.data()
        return Relation(id=data["id"], type=data.get("type", "RELATED_TO"), src=data["src"], dst=data["dst"], props=self._loads_props(data.get("props_json")))

    # --------------------
    # Draft graph storage
    # --------------------

    def save_draft(self, draft_id: str, nodes: list[Entity], edges: list[Relation]) -> None:
        """把抽取结果写入“临时图谱”（隔离于正式图谱）。"""
        for n in nodes:
            self.upsert_draft_entity_by_id(draft_id, n.id, n.name, n.label or "Concept", n.props or {})
        for e in edges:
            self.upsert_draft_relation_by_id(draft_id, e.id, e.src, e.dst, e.type or "RELATED_TO", e.props or {})

    def upsert_draft_entity_by_id(self, draft_id: str, entity_id: str, name: str, label: str, props: dict) -> Entity:
        props_json = json.dumps(props or {}, ensure_ascii=False)
        query = """
        MERGE (n:DraftConcept {draft_id:$draft_id, id:$id})
        SET n.name = $name,
            n.label = $label,
            n.props_json = $props_json
        RETURN n.id AS id, n.label AS label, n.name AS name, n.props_json AS props_json
        """
        with self.driver.session() as session:
            rec = session.run(query, draft_id=draft_id, id=entity_id, name=name, label=label, props_json=props_json).single()
        data = rec.data()
        return Entity(id=data["id"], label=data.get("label", "Concept"), name=data["name"], props=self._loads_props(data.get("props_json")))

    def upsert_draft_relation_by_id(self, draft_id: str, rel_id: str, src: str, dst: str, rel_type: str, props: dict) -> Relation:
        props_json = json.dumps(props or {}, ensure_ascii=False)
        query = """
        MATCH (s:DraftConcept {draft_id:$draft_id, id:$src})
        MATCH (d:DraftConcept {draft_id:$draft_id, id:$dst})
        MERGE (s)-[r:DREL {draft_id:$draft_id, id:$id}]->(d)
        SET r.type = $type,
            r.props_json = $props_json
        RETURN r.id AS id, r.type AS type, s.id AS src, d.id AS dst, r.props_json AS props_json
        """
        with self.driver.session() as session:
            rec = session.run(
                query,
                draft_id=draft_id,
                id=rel_id,
                src=src,
                dst=dst,
                type=rel_type,
                props_json=props_json,
            ).single()
        data = rec.data()
        return Relation(id=data["id"], type=data.get("type", "RELATED_TO"), src=data["src"], dst=data["dst"], props=self._loads_props(data.get("props_json")))

    def list_draft_entities(self, draft_id: str, limit: int = 2000) -> list[Entity]:
        query = """
        MATCH (n:DraftConcept {draft_id:$draft_id})
        RETURN n.id AS id, n.label AS label, n.name AS name, n.props_json AS props_json
        ORDER BY n.name ASC
        LIMIT $limit
        """
        with self.driver.session() as session:
            items: list[Entity] = []
            for rec in session.run(query, draft_id=draft_id, limit=limit):
                data = rec.data()
                items.append(
                    Entity(
                        id=data["id"],
                        label=data.get("label", "Concept"),
                        name=data.get("name") or "",
                        props=self._loads_props(data.get("props_json")),
                    )
                )
            return items

    def list_draft_relations(self, draft_id: str, limit: int = 5000) -> list[Relation]:
        query = """
        MATCH (s:DraftConcept {draft_id:$draft_id})-[r:DREL {draft_id:$draft_id}]->(d:DraftConcept {draft_id:$draft_id})
        RETURN r.id AS id, r.type AS type, s.id AS src, d.id AS dst, r.props_json AS props_json
        ORDER BY r.type ASC
        LIMIT $limit
        """
        with self.driver.session() as session:
            items: list[Relation] = []
            for rec in session.run(query, draft_id=draft_id, limit=limit):
                data = rec.data()
                items.append(
                    Relation(
                        id=data.get("id") or "",
                        type=data.get("type", "RELATED_TO"),
                        src=data.get("src") or "",
                        dst=data.get("dst") or "",
                        props=self._loads_props(data.get("props_json")),
                    )
                )
            return items

    def delete_draft(self, draft_id: str) -> None:
        query = "MATCH (n:DraftConcept {draft_id:$draft_id}) DETACH DELETE n"
        with self.driver.session() as session:
            session.run(query, draft_id=draft_id).consume()

    def delete_draft_entity(self, draft_id: str, entity_id: str) -> None:
        query = "MATCH (n:DraftConcept {draft_id:$draft_id, id:$id}) DETACH DELETE n"
        with self.driver.session() as session:
            session.run(query, draft_id=draft_id, id=entity_id).consume()

    def delete_draft_relation(self, draft_id: str, rel_id: str) -> None:
        query = "MATCH ()-[r:DREL {draft_id:$draft_id, id:$id}]-() DELETE r"
        with self.driver.session() as session:
            session.run(query, draft_id=draft_id, id=rel_id).consume()

    def query_draft_graph(self, draft_id: str, root_id: str | None, depth: int) -> Tuple[List[Entity], List[Relation]]:
        depth = max(1, min(int(depth), 4))
        if root_id:
            query = f"""
            MATCH p=(n:DraftConcept {{draft_id:$draft_id, id:$root}})-[*1..{depth}]->(m:DraftConcept {{draft_id:$draft_id}})
            WITH nodes(p) AS ns, relationships(p) AS rs
            RETURN ns, rs
            UNION
            MATCH p=(n:DraftConcept {{draft_id:$draft_id, id:$root}})<-[*1..{depth}]-(m:DraftConcept {{draft_id:$draft_id}})
            WITH nodes(p) AS ns, relationships(p) AS rs
            RETURN ns, rs
            """
            params = {"draft_id": draft_id, "root": root_id}
        else:
            query = """
            MATCH p=(n:DraftConcept {draft_id:$draft_id})-[r:DREL {draft_id:$draft_id}]->(m:DraftConcept {draft_id:$draft_id})
            WITH nodes(p) AS ns, relationships(p) AS rs
            RETURN ns, rs LIMIT 300
            """
            params = {"draft_id": draft_id}

        nodes: dict[str, Entity] = {}
        edges: dict[str, Relation] = {}
        with self.driver.session() as session:
            for rec in session.run(query, **params):
                for n in rec["ns"]:
                    nodes[n["id"]] = Entity(
                        id=n["id"],
                        label=n.get("label", "Concept"),
                        name=n.get("name") or "",
                        props=self._loads_props(n.get("props_json")),
                    )
                for r in rec["rs"]:
                    rid = r.get("id") or f"rel-{uuid.uuid4().hex[:8]}"
                    edges[rid] = Relation(
                        id=rid,
                        type=r.get("type", "RELATED_TO"),
                        src=r.start_node["id"],
                        dst=r.end_node["id"],
                        props=self._loads_props(r.get("props_json")),
                    )
        return list(nodes.values()), list(edges.values())

    def commit_draft_id(self, draft_id: str, *, delete_after: bool = True) -> tuple[int, int]:
        """把临时图谱复制到正式图谱（幂等按 id upsert）。"""
        nodes = self.list_draft_entities(draft_id, limit=5000)
        edges = self.list_draft_relations(draft_id, limit=20000)
        created_nodes, created_edges = self.commit_draft(nodes, edges)
        if delete_after:
            self.delete_draft(draft_id)
        return created_nodes, created_edges

    def list_entities(self, limit: int = 500) -> list[Entity]:
        query = """
        MATCH (n:Concept)
        RETURN n.id AS id, n.label AS label, n.name AS name, n.props_json AS props_json
        ORDER BY n.name ASC
        LIMIT $limit
        """
        with self.driver.session() as session:
            items: list[Entity] = []
            for rec in session.run(query, limit=limit):
                data = rec.data()
                items.append(
                    Entity(
                        id=data["id"],
                        label=data.get("label", "Concept"),
                        name=data.get("name") or "",
                        props=self._loads_props(data.get("props_json")),
                    )
                )
            return items

    def list_relations(self, limit: int = 2000) -> list[Relation]:
        query = """
        MATCH (s)-[r:REL]->(d)
        RETURN r.id AS id, r.type AS type, s.id AS src, d.id AS dst, r.props_json AS props_json
        ORDER BY r.type ASC
        LIMIT $limit
        """
        with self.driver.session() as session:
            items: list[Relation] = []
            for rec in session.run(query, limit=limit):
                data = rec.data()
                items.append(
                    Relation(
                        id=data.get("id") or "",
                        type=data.get("type", "RELATED_TO"),
                        src=data.get("src") or "",
                        dst=data.get("dst") or "",
                        props=self._loads_props(data.get("props_json")),
                    )
                )
            return items

    def update_entity(self, entity_id: str, name: str | None, label: str | None, props: dict | None) -> Entity:
        query = """
        MATCH (n:Concept {id:$id})
        SET n.name = coalesce($name, n.name),
            n.label = coalesce($label, n.label),
            n.props_json = coalesce($props_json, n.props_json)
        RETURN n.id AS id, n.label AS label, n.name AS name, n.props_json AS props_json
        """
        props_json = None if props is None else json.dumps(props, ensure_ascii=False)
        with self.driver.session() as session:
            rec = session.run(query, id=entity_id, name=name, label=label, props_json=props_json).single()
        if not rec:
            raise ValueError("entity not found")
        data = rec.data()
        return Entity(id=data["id"], label=data.get("label", "Concept"), name=data["name"], props=self._loads_props(data.get("props_json")))

    def delete_entity(self, entity_id: str) -> None:
        query = "MATCH (n:Concept {id:$id}) DETACH DELETE n"
        with self.driver.session() as session:
            session.run(query, id=entity_id).consume()

    def get_relation(self, rel_id: str) -> Relation | None:
        query = """
        MATCH (s)-[r:REL {id:$id}]->(d)
        RETURN r.id AS id, r.type AS type, s.id AS src, d.id AS dst, r.props_json AS props_json
        """
        with self.driver.session() as session:
            rec = session.run(query, id=rel_id).single()
        if not rec:
            return None
        data = rec.data()
        return Relation(
            id=data.get("id") or "",
            type=data.get("type", "RELATED_TO"),
            src=data.get("src") or "",
            dst=data.get("dst") or "",
            props=self._loads_props(data.get("props_json")),
        )

    def update_relation(self, rel_id: str, rel_type: str | None, src: str | None, dst: str | None, props: dict | None) -> Relation:
        # 若需要改 src/dst：删除重建（关系无法直接“移动”到新端点）
        current = self.get_relation(rel_id)
        if not current:
            raise ValueError("relation not found")

        new_src = src or current.src
        new_dst = dst or current.dst
        new_type = rel_type or current.type
        new_props = current.props if props is None else props

        if new_src != current.src or new_dst != current.dst:
            self.delete_relation(rel_id)
            # 复用 rel_id，便于前端跟踪
            props_json = json.dumps(new_props or {}, ensure_ascii=False)
            query = """
            MATCH (s {id:$src})
            MATCH (d {id:$dst})
            CREATE (s)-[r:REL]->(d)
            SET r.id = $id,
                r.type = $type,
                r.props_json = $props_json
            RETURN r.id AS id, r.type AS type, s.id AS src, d.id AS dst, r.props_json AS props_json
            """
            with self.driver.session() as session:
                rec = session.run(query, src=new_src, dst=new_dst, id=rel_id, type=new_type, props_json=props_json).single()
            data = rec.data()
            return Relation(id=data["id"], type=data.get("type", "RELATED_TO"), src=data["src"], dst=data["dst"], props=self._loads_props(data.get("props_json")))

        # 仅更新属性
        props_json = None if props is None else json.dumps(props, ensure_ascii=False)
        query = """
        MATCH (s)-[r:REL {id:$id}]->(d)
        SET r.type = coalesce($type, r.type),
            r.props_json = coalesce($props_json, r.props_json)
        RETURN r.id AS id, r.type AS type, s.id AS src, d.id AS dst, r.props_json AS props_json
        """
        with self.driver.session() as session:
            rec = session.run(query, id=rel_id, type=rel_type, props_json=props_json).single()
        data = rec.data()
        return Relation(id=data["id"], type=data.get("type", "RELATED_TO"), src=data["src"], dst=data["dst"], props=self._loads_props(data.get("props_json")))

    def delete_relation(self, rel_id: str) -> None:
        query = "MATCH ()-[r:REL {id:$id}]-() DELETE r"
        with self.driver.session() as session:
            session.run(query, id=rel_id).consume()

    def query_graph(self, root_id: str | None, depth: int) -> Tuple[List[Entity], List[Relation]]:
        # Neo4j 不允许在可变长度模式里使用参数（[*1..$depth] 会报错），
        # 因此这里把 depth（已在上层做过限制）作为字面量拼到 Cypher 中。
        depth = max(1, min(int(depth), 4))
        if root_id:
            query = f"""
            MATCH p=(n {{id:$root}})-[*1..{depth}]->(m)
            WITH nodes(p) AS ns, relationships(p) AS rs
            RETURN ns, rs
            UNION
            MATCH p=(n {{id:$root}})<-[*1..{depth}]-(m)
            WITH nodes(p) AS ns, relationships(p) AS rs
            RETURN ns, rs
            """
            params = {"root": root_id}
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
                    nodes[n["id"]] = Entity(
                        id=n["id"],
                        label=n.get("label", "Concept"),
                        name=n["name"],
                        props=self._loads_props(n.get("props_json")),
                    )
                for r in rec["rs"]:
                    rid = r.get("id") or f"rel-{uuid.uuid4().hex[:8]}"
                    edges[rid] = Relation(
                        id=rid,
                        type=r.get("type", "RELATED_TO"),
                        src=r.start_node["id"],
                        dst=r.end_node["id"],
                        props=self._loads_props(r.get("props_json")),
                    )
        return list(nodes.values()), list(edges.values())

    def search_entities(self, keyword: str, limit: int = 20) -> List[Entity]:
        query = """
        MATCH (n:Concept)
        WHERE toLower(n.name) CONTAINS toLower($kw)
        RETURN n.id AS id, n.label AS label, n.name AS name, n.props_json AS props_json
        LIMIT $limit
        """
        with self.driver.session() as session:
            items: list[Entity] = []
            for rec in session.run(query, kw=keyword, limit=limit):
                data = rec.data()
                items.append(
                    Entity(
                        id=data["id"],
                        label=data.get("label", "Concept"),
                        name=data["name"],
                        props=self._loads_props(data.get("props_json")),
                    )
                )
            return items

    # ---------- 文本解析为简单本体 ----------

    # 注：按当前产品要求，不再提供“词法切分/规则抽取”导入能力；仅保留 DeepSeek 抽取链路。

    async def extract_draft_from_deepseek(
        self,
        text: str,
        *,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
    ) -> tuple[str, list[Entity], list[Relation]]:
        """
        DeepSeek 抽取“草稿本体图”（不入库）：
        - 为每个实体生成稳定 id：ent-<sha1(name)>
        - 为每条关系生成稳定 id：rel-<sha1(src|type|dst)>
        """
        payload = await self._deepseek_extract(text, api_key=api_key, base_url=base_url, model=model)
        draft_id = f"draft-{uuid.uuid4().hex[:10]}"

        def ent_id(name: str) -> str:
            return f"ent-{hashlib.sha1(name.encode('utf-8')).hexdigest()[:10]}"

        nodes: dict[str, Entity] = {}
        edges: dict[str, Relation] = {}

        # entities
        for ent in payload.get("entities", []):
            name = (ent.get("name") or "").strip()
            if not name:
                continue
            label = (ent.get("label") or "Concept").strip() or "Concept"
            props = ent.get("props") or {}
            props = {**props, "source": "deepseek"}
            eid = ent_id(name)
            nodes[eid] = Entity(id=eid, name=name, label=label, props=props)

        # relations（若实体缺失则补 Concept）
        def ensure_node(nm: str) -> str:
            nm = nm.strip()
            eid = ent_id(nm)
            if eid not in nodes:
                nodes[eid] = Entity(id=eid, name=nm, label="Concept", props={"source": "deepseek"})
            return eid

        for rel in payload.get("relations", []):
            rel_type = (rel.get("type") or "RELATED_TO").strip() or "RELATED_TO"
            src_name = (rel.get("src") or "").strip()
            dst_name = (rel.get("dst") or "").strip()
            if not src_name or not dst_name:
                    continue
            src = ensure_node(src_name)
            dst = ensure_node(dst_name)
            props = rel.get("props") or {}
            props = {**props, "source": "deepseek"}
            rid = f"rel-{hashlib.sha1(f'{src}|{rel_type}|{dst}'.encode('utf-8')).hexdigest()[:12]}"
            edges[rid] = Relation(id=rid, type=rel_type, src=src, dst=dst, props=props)

        # rules：作为节点 + INVOLVES 关系
        for rule in payload.get("rules", []):
            rname = (rule.get("name") or "").strip()
            if not rname:
                continue
            rid_node = ent_id(rname)
            rprops = {
                "source": "deepseek",
                "trigger": rule.get("trigger"),
                "action": rule.get("action"),
                "approval_required": rule.get("approval_required"),
                "sla_minutes": rule.get("sla_minutes"),
                "required_evidence": rule.get("required_evidence"),
            }
            nodes[rid_node] = Entity(id=rid_node, name=rname, label="Rule", props={k: v for k, v in rprops.items() if v is not None})
            involves = rule.get("involves") or []
            for obj_name in involves:
                nm = (obj_name or "").strip()
                if not nm:
                    continue
                oid = ensure_node(nm)
                rrel_id = f"rel-{hashlib.sha1(f'{rid_node}|INVOLVES|{oid}'.encode('utf-8')).hexdigest()[:12]}"
                edges[rrel_id] = Relation(id=rrel_id, type="INVOLVES", src=rid_node, dst=oid, props={"source": "deepseek"})

        return draft_id, list(nodes.values()), list(edges.values())

    def commit_draft(self, nodes: list[Entity], edges: list[Relation]) -> tuple[int, int]:
        """把草稿图写入 Neo4j（幂等按 id upsert）。"""
        created_nodes = 0
        created_edges = 0
        for n in nodes:
            self.upsert_entity_by_id(n.id, n.name, n.label or "Concept", n.props or {})
            created_nodes += 1
        for e in edges:
            self.upsert_relation_by_id(e.id, e.src, e.dst, e.type or "RELATED_TO", e.props or {})
            created_edges += 1
        return created_nodes, created_edges

    @staticmethod
    def _loads_props(v) -> dict:
        if not v:
            return {}
        if isinstance(v, dict):
            return v
        try:
            return json.loads(v)
        except Exception:
            return {}

    async def _deepseek_extract(self, text: str, *, api_key: str, base_url: str, model: str) -> dict:
        prompt = (
            "你是城市管网运维领域的本体抽取助手。"
            "请从给定的【业务方案】中抽取：entities（实体）、relations（关系）、rules（规则）。\n"
            "要求：只输出严格 JSON（不要 Markdown，不要解释文字）。\n"
            "JSON Schema：\n"
            "{\n"
            '  "entities": [{"name": "实体名", "label": "类型/标签", "props": {"desc": "...", "location": "..."} }],\n'
            '  "relations": [{"type": "关系类型", "src": "源实体名", "dst": "目标实体名", "props": {"desc": "..."} }],\n'
            '  "rules": [{"name": "规则名", "trigger": "触发条件", "action": "动作/任务", "approval_required": true/false,'
            ' "sla_minutes": 30, "required_evidence": ["定位","照片"], "involves": ["实体名1","实体名2"]}]\n'
            "}\n"
            "注意：实体名请尽量使用业务原词（如：泵站、管段、阀门、雨量站、报警事件、任务、事件/工单）。\n\n"
            f"【业务方案】\n{text}\n"
        )
        try:
            # 对齐官方示例：OpenAI SDK + base_url 指向 DeepSeek
            client = OpenAI(api_key=api_key, base_url=base_url.rstrip("/"))
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                stream=False,
            )
            content = resp.choices[0].message.content or ""
        except Exception as e:
            # openai SDK 会抛出不同异常类型，这里统一包装，message 留给上层输出
            raise RuntimeError(f"DeepSeek(OpenAI SDK) request failed: {repr(e)}") from e

        # 兼容模型偶尔包 ```json ... ```
        content = content.strip()
        content = re.sub(r"^```json\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"^```\s*", "", content)
        content = re.sub(r"\s*```$", "", content)

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"DeepSeek returned non-JSON content (head): {content[:800]}") from e

    # （保留 _deepseek_extract 的轻量内容清洗；不再需要词法抽取辅助函数）
