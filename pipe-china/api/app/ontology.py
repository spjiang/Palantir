from __future__ import annotations

import json
import re
import hashlib
import uuid
from pathlib import Path
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
        MERGE (n:Concept {id:$id})
        SET n.name = $name,
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

    def list_draft_ids(self, limit: int = 50) -> list[str]:
        """
        返回当前图数据库中存在的草稿 draft_id 列表（去重）。
        用于前端下拉选择（L2/L4/L3 等）。
        """
        query = """
        MATCH (n:DraftConcept)
        RETURN DISTINCT n.draft_id AS draft_id
        ORDER BY n.draft_id DESC
        LIMIT $limit
        """
        with self.driver.session() as session:
            out: list[str] = []
            for rec in session.run(query, limit=max(1, min(int(limit), 200))):
                did = (rec.get("draft_id") or "").strip()
                if did:
                    out.append(did)
            return out

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

    def purge_all(self) -> None:
        """
        危险操作：清空整个图数据库（包含正式图谱 Concept/REL 与临时图谱 DraftConcept/DREL）。
        """
        query = "MATCH (n) DETACH DELETE n"
        with self.driver.session() as session:
            session.run(query).consume()

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
        """
        查询“正式图谱”：
        - 仅返回 (:Concept)-[:REL]->(:Concept)
        - 避免把草稿图谱 (:DraftConcept)-[:DREL]->(:DraftConcept) 混进来
        """
        # Neo4j 不允许在可变长度模式里使用参数（[*1..$depth] 会报错），
        # 因此这里把 depth（已在上层做过限制）作为字面量拼到 Cypher 中。
        depth = max(1, min(int(depth), 4))
        if root_id:
            query = f"""
            MATCH p=(n:Concept {{id:$root}})-[:REL*1..{depth}]->(m:Concept)
            WITH nodes(p) AS ns, relationships(p) AS rs
            RETURN ns, rs
            UNION
            MATCH p=(n:Concept {{id:$root}})<-[:REL*1..{depth}]-(m:Concept)
            WITH nodes(p) AS ns, relationships(p) AS rs
            RETURN ns, rs
            """
            params = {"root": root_id}
        else:
            query = """
            MATCH p=(n:Concept)-[r:REL]->(m:Concept)
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
        return self._payload_to_draft_graph(payload)

    def extract_draft_from_deepseek_stream(
        self,
        text: str,
        *,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
    ):
        """
        DeepSeek 流式抽取：逐步 yield token，最后 yield done({draft_id,nodes,edges})。
        注意：此方法是同步 generator（OpenAI SDK stream 是阻塞的），由 FastAPI StreamingResponse 驱动。
        """
        prompt = self._render_prompt_template(template_name="deepseek_extract.md", context={"BUSINESS_TEXT": text})
        try:
            client = OpenAI(api_key=api_key, base_url=base_url.rstrip("/"))
            stream = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a senior ontology and behavior modeling assistant for oil & gas pipeline operations."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                stream=True,
            )
        except Exception as e:
            raise RuntimeError(f"DeepSeek(OpenAI SDK) stream request failed: {repr(e)}") from e

        content = ""
        for event in stream:
            try:
                delta = getattr(event.choices[0].delta, "content", None)  # type: ignore[attr-defined]
            except Exception:
                delta = None
            if delta:
                content += delta
                yield {"event": "token", "data": delta}

        # 兼容模型偶尔包 ```json ... ```
        raw = content.strip()
        raw = re.sub(r"^```json\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"^```\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"DeepSeek returned non-JSON content (head): {raw[:800]}") from e

        draft_id, nodes, edges = self._payload_to_draft_graph(payload)
        yield {"event": "done", "data": {"draft_id": draft_id, "nodes": [n.model_dump() for n in nodes], "edges": [e.model_dump() for e in edges]}}

    def _payload_to_draft_graph(self, payload: dict) -> tuple[str, list[Entity], list[Relation]]:
        draft_id = f"draft-{uuid.uuid4().hex[:10]}"

        def ent_id(name: str, label: str = "Concept") -> str:
            # label + name 共同参与，避免同名不同类型碰撞（Behavior/Rule/State 等在产品中很常见）
            key = f"{label.strip() or 'Concept'}::{name.strip()}"
            return f"ent-{hashlib.sha1(key.encode('utf-8')).hexdigest()[:10]}"

        nodes: dict[str, Entity] = {}
        edges: dict[str, Relation] = {}
        # 以 (label,name) 为主键的索引，用于去重同类同名节点（不同类型允许同名共存）
        key_to_id: dict[str, str] = {}
        # 以 name 为主键的“优选节点 id”（用于 relations/behaviors/rules 里仅给了 name 的场景）
        # 规则：优先选择非 Concept 的实体（例如 PipelineSegment/Sensor/...），避免生成同名 Concept 重复节点
        name_to_preferred_id: dict[str, str] = {}

        # entities（对象/状态/行为/证据等都作为实体节点承载，label 决定类型）
        for ent in payload.get("entities", []):
            name = (ent.get("name") or "").strip()
            if not name:
                continue
            label = (ent.get("label") or "Concept").strip() or "Concept"
            props = ent.get("props") or {}
            props = {**props, "source": "deepseek"}
            key = f"{label}::{name}"
            if key in key_to_id:
                eid = key_to_id[key]
            else:
                eid = ent_id(name, label)
                key_to_id[key] = eid
            nodes[eid] = Entity(id=eid, name=name, label=label, props=props)
            # 更新 name -> preferred id：优先使用非 Concept 的 label
            if label != "Concept":
                name_to_preferred_id[name] = eid
            elif name not in name_to_preferred_id:
                name_to_preferred_id[name] = eid

        # relations（若实体缺失则补 Concept）
        def ensure_node(nm: str, label: str = "Concept") -> str:
            nm = nm.strip()
            # 对于“只有 name 的引用”（relations/behaviors/rules/produces/inputs/outputs 等），
            # 优先复用 entities 里已抽到的同名节点，避免生成同名不同 label 的重复节点。
            # 典型问题：produces 里写了“运维任务”，代码用 ensure_node(...,"Artifact") 会额外生成 Artifact::运维任务，
            # 但 entities 已经定义 MaintenanceTask::运维任务，应复用它。
            if nm in name_to_preferred_id and label in {"Concept", "Artifact", "Evidence"}:
                return name_to_preferred_id[nm]
            key = f"{label}::{nm}"
            if key in key_to_id:
                return key_to_id[key]
            eid = ent_id(nm, label)
            nodes[eid] = Entity(id=eid, name=nm, label=label, props={"source": "deepseek"})
            key_to_id[key] = eid
            if label != "Concept":
                name_to_preferred_id[nm] = eid
            elif nm not in name_to_preferred_id:
                name_to_preferred_id[nm] = eid
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
            rid_node = ensure_node(rname, "Rule")
            rprops = {
                "source": "deepseek",
                "trigger": rule.get("trigger"),
                "action": rule.get("action"),
                "approval_required": rule.get("approval_required"),
                "sla_minutes": rule.get("sla_minutes"),
                "required_evidence": rule.get("required_evidence"),
                "forbids": rule.get("forbids"),
                "allows": rule.get("allows"),
                "governs_behavior": rule.get("behavior") or rule.get("governs_behavior"),
            }
            nodes[rid_node] = Entity(id=rid_node, name=rname, label="Rule", props={k: v for k, v in rprops.items() if v is not None})
            involves = rule.get("involves") or []
            for obj_name in involves:
                nm = (obj_name or "").strip()
                if not nm:
                    continue
                oid = ensure_node(nm)
                rrel_id = f"rel-{hashlib.sha1(f'{rid_node}|INVOLVES|{oid}'.encode('utf-8')).hexdigest()[:12]}"
                edges[rrel_id] = Relation(id=rrel_id, type="涉及", src=rid_node, dst=oid, props={"source": "deepseek"})

            # rule -> behavior（若提供）
            bname = (rule.get("behavior") or rule.get("governs_behavior") or "").strip()
            if bname:
                bid = ensure_node(bname, "Behavior")
                rrel_id = f"rel-{hashlib.sha1(f'{rid_node}|GOVERNS|{bid}'.encode('utf-8')).hexdigest()[:12]}"
                edges[rrel_id] = Relation(id=rrel_id, type="约束", src=rid_node, dst=bid, props={"source": "deepseek"})

            # rule -> evidence（若提供 required_evidence）
            for ev in rule.get("required_evidence") or []:
                evn = (ev or "").strip()
                if not evn:
                    continue
                evid = ensure_node(evn, "Evidence")
                rrel_id = f"rel-{hashlib.sha1(f'{rid_node}|REQUIRES_EVIDENCE|{evid}'.encode('utf-8')).hexdigest()[:12]}"
                edges[rrel_id] = Relation(id=rrel_id, type="需要证据", src=rid_node, dst=evid, props={"source": "deepseek"})

        # behaviors：行为作为一级对象，显式表达“条件→行为→状态变化→新数据”
        for beh in payload.get("behaviors", []):
            bname = (beh.get("name") or "").strip()
            if not bname:
                continue
            bid = ensure_node(bname, "Behavior")
            bprops = {
                "source": "deepseek",
                "preconditions": beh.get("preconditions") or beh.get("trigger") or beh.get("conditions"),
                "inputs": beh.get("inputs"),
                "outputs": beh.get("outputs"),
                "effects": beh.get("effects") or beh.get("result"),
                "explain": beh.get("explain") or beh.get("desc"),
            }
            # 合并到节点 props（若已存在则补齐）
            nodes[bid] = Entity(
                id=bid,
                name=bname,
                label="Behavior",
                props={**(nodes.get(bid).props or {}), **{k: v for k, v in bprops.items() if v is not None}},
            )

            # affects / involves
            for obj_name in beh.get("affects") or beh.get("involves") or []:
                nm = (obj_name or "").strip()
                if not nm:
                    continue
                oid = ensure_node(nm, "Concept")
                rrel_id = f"rel-{hashlib.sha1(f'{bid}|AFFECTS|{oid}'.encode('utf-8')).hexdigest()[:12]}"
                edges[rrel_id] = Relation(id=rrel_id, type="作用于", src=bid, dst=oid, props={"source": "deepseek"})

            # state transition
            st_from = (beh.get("state_from") or beh.get("from_state") or "").strip()
            st_to = (beh.get("state_to") or beh.get("to_state") or "").strip()
            if st_from:
                sid = ensure_node(st_from, "State")
                rrel_id = f"rel-{hashlib.sha1(f'{bid}|FROM_STATE|{sid}'.encode('utf-8')).hexdigest()[:12]}"
                edges[rrel_id] = Relation(id=rrel_id, type="从状态", src=bid, dst=sid, props={"source": "deepseek"})
            if st_to:
                tid = ensure_node(st_to, "State")
                rrel_id = f"rel-{hashlib.sha1(f'{bid}|TO_STATE|{tid}'.encode('utf-8')).hexdigest()[:12]}"
                edges[rrel_id] = Relation(id=rrel_id, type="到状态", src=bid, dst=tid, props={"source": "deepseek"})

            # produces artifacts / evidence / task
            for out in beh.get("produces") or beh.get("artifacts") or []:
                onm = (out or "").strip()
                if not onm:
                    continue
                aid = ensure_node(onm, "Artifact")
                rrel_id = f"rel-{hashlib.sha1(f'{bid}|PRODUCES|{aid}'.encode('utf-8')).hexdigest()[:12]}"
                edges[rrel_id] = Relation(id=rrel_id, type="产生", src=bid, dst=aid, props={"source": "deepseek"})

        # state_transitions：显式状态迁移表（可选）
        for st in payload.get("state_transitions", []):
            obj = (st.get("object") or st.get("target") or "").strip()
            frm = (st.get("from") or st.get("from_state") or "").strip()
            to = (st.get("to") or st.get("to_state") or "").strip()
            via = (st.get("via") or st.get("behavior") or "").strip()
            if not (obj and frm and to and via):
                continue
            oid = ensure_node(obj, "Concept")
            bid = ensure_node(via, "Behavior")
            fid = ensure_node(frm, "State")
            tid = ensure_node(to, "State")
            for t, dst in [("适用对象", oid), ("从状态", fid), ("到状态", tid)]:
                rrel_id = f"rel-{hashlib.sha1(f'{bid}|{t}|{dst}'.encode('utf-8')).hexdigest()[:12]}"
                edges[rrel_id] = Relation(id=rrel_id, type=t, src=bid, dst=dst, props={"source": "deepseek"})

        return draft_id, list(nodes.values()), list(edges.values())

    def commit_draft(self, nodes: list[Entity], edges: list[Relation]) -> tuple[int, int]:
        """把草稿图写入 Neo4j（幂等按 id upsert）。"""
        self._validate_behaviors_have_objects(nodes, edges)
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
    def _validate_behaviors_have_objects(nodes: list[Entity], edges: list[Relation]) -> None:
        """
        产品硬规则：每个 Behavior 必须至少挂 1 个“对象”。
        判定方式：Behavior 节点至少有一条从自己出发的关系，type 属于 {作用于, 适用对象, AFFECTS, APPLIES_TO}
        且 dst 节点 label 不属于 {Behavior, Rule, State, Evidence, Artifact}。
        """
        id_to_label = {n.id: (n.label or "Concept") for n in nodes}
        id_to_name = {n.id: n.name for n in nodes}
        behavior_ids = [n.id for n in nodes if (n.label or "") == "Behavior"]
        if not behavior_ids:
            return

        allowed_types = {"作用于", "适用对象", "AFFECTS", "APPLIES_TO"}
        non_object_labels = {"Behavior", "Rule", "State", "Evidence", "Artifact"}

        # 建立行为 -> 目标集合
        targets: dict[str, set[str]] = {bid: set() for bid in behavior_ids}
        for e in edges:
            if e.src in targets and (e.type or "") in allowed_types:
                targets[e.src].add(e.dst)

        missing: list[str] = []
        for bid in behavior_ids:
            ok = False
            for dst in targets.get(bid, set()):
                if id_to_label.get(dst, "Concept") not in non_object_labels:
                    ok = True
                    break
            if not ok:
                missing.append(f"{id_to_name.get(bid, bid)}({bid})")

        if missing:
            raise ValueError("行为未挂载对象（每个行为必须至少作用于 1 个对象）: " + ", ".join(missing))

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
        prompt = self._render_prompt_template(
            template_name="deepseek_extract.md",
            context={"BUSINESS_TEXT": text},
        )
        try:
            # 对齐官方示例：OpenAI SDK + base_url 指向 DeepSeek
            client = OpenAI(api_key=api_key, base_url=base_url.rstrip("/"))
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a senior ontology and behavior modeling assistant for oil & gas pipeline operations."},
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

    @staticmethod
    def _render_prompt_template(template_name: str, context: dict[str, str]) -> str:
        """
        读取 Markdown 提示词模板并做简单变量替换，便于非开发人员直接改提示词。
        默认模板位置：app/prompts/<template_name>
        占位符格式：{{VAR_NAME}}
        """
        base = Path(__file__).resolve().parent
        path = base / "prompts" / template_name
        if not path.exists():
            # 兜底：避免模板文件丢失导致线上不可用
            fallback = (
                "你是【油气管网运维】领域的本体论/行为建模抽取助手。\n"
                "核心要求：一定要以【行为建模】为中心，把业务方案里的“条件→行为→状态变化→新数据/证据”显性化。\n"
                "语言要求：能用中文的地方都用中文（实体 name、关系 type、规则 trigger/action、证据名称等尽量用中文）。\n"
                "为保证产品识别与配色，label 使用英文枚举（Behavior/Rule/State/Evidence/Artifact/...），但 name 必须尽量中文。\n"
                "只输出严格 JSON（不要 Markdown，不要解释文字）。\n\n"
                f"【业务方案】\n{context.get('BUSINESS_TEXT','')}\n"
            )
            return fallback
        tpl = path.read_text(encoding="utf-8")
        for k, v in context.items():
            tpl = tpl.replace(f"{{{{{k}}}}}", v)
        return tpl.strip()

    # （保留 _deepseek_extract 的轻量内容清洗；不再需要词法抽取辅助函数）
