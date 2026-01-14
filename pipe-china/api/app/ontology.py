from __future__ import annotations

import json
import re
import uuid
from typing import List, Tuple

from neo4j import GraphDatabase, Driver
from openai import OpenAI

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

    # 注：按当前产品要求，不再提供“词法切分/规则抽取”导入能力；仅保留 DeepSeek 抽取链路。

    async def import_from_deepseek(
        self,
        text: str,
        *,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
    ) -> ImportResult:
        """
        使用 DeepSeek 从“业务方案文本”抽取实体/关系/规则，并写入 Neo4j。
        失败时由调用方决定是否回退到 import_from_text。
        """
        payload = await self._deepseek_extract(text, api_key=api_key, base_url=base_url, model=model)

        name_to_id: dict[str, str] = {}
        created_nodes = 0
        created_edges = 0

        # 1) entities
        for ent in payload.get("entities", []):
            name = (ent.get("name") or "").strip()
            if not name:
                continue
            label = (ent.get("label") or "Concept").strip()
            props = ent.get("props") or {}
            props = {**props, "source": "deepseek"}
            node = self.upsert_entity(name=name, label=label, props=props)
            if name not in name_to_id:
                created_nodes += 1
            name_to_id[name] = node.id

        # 2) relations
        for rel in payload.get("relations", []):
            rel_type = (rel.get("type") or "RELATED_TO").strip()
            src_name = (rel.get("src") or "").strip()
            dst_name = (rel.get("dst") or "").strip()
            if not src_name or not dst_name:
                continue

            if src_name not in name_to_id:
                node = self.upsert_entity(name=src_name, label="Concept", props={"source": "deepseek"})
                name_to_id[src_name] = node.id
                created_nodes += 1
            if dst_name not in name_to_id:
                node = self.upsert_entity(name=dst_name, label="Concept", props={"source": "deepseek"})
                name_to_id[dst_name] = node.id
                created_nodes += 1

            props = rel.get("props") or {}
            props = {**props, "source": "deepseek"}
            _ = self.create_relation(name_to_id[src_name], name_to_id[dst_name], rel_type, props)
            created_edges += 1

        # 3) rules（作为节点入库，并与涉及对象建立关系）
        for rule in payload.get("rules", []):
            rname = (rule.get("name") or "").strip()
            if not rname:
                continue
            rprops = {
                "source": "deepseek",
                "trigger": rule.get("trigger"),
                "action": rule.get("action"),
                "approval_required": rule.get("approval_required"),
                "sla_minutes": rule.get("sla_minutes"),
                "required_evidence": rule.get("required_evidence"),
            }
            rnode = self.upsert_entity(name=rname, label="Rule", props={k: v for k, v in rprops.items() if v is not None})
            created_nodes += 1

            involves = rule.get("involves") or []
            for obj_name in involves:
                on = (obj_name or "").strip()
                if not on:
                    continue
                if on not in name_to_id:
                    node = self.upsert_entity(name=on, label="Concept", props={"source": "deepseek"})
                    name_to_id[on] = node.id
                    created_nodes += 1
                _ = self.create_relation(rnode.id, name_to_id[on], "INVOLVES", {"source": "deepseek"})
                created_edges += 1

        # samples
        sample_nodes: list[Entity] = []
        for nm, nid in list(name_to_id.items())[:5]:
            sample_nodes.append(Entity(id=nid, name=nm, label="Concept", props={"source": "deepseek"}))

        return ImportResult(
            created_nodes=created_nodes,
            created_edges=created_edges,
            sample_nodes=sample_nodes,
            sample_edges=[],
            mode="llm",
            llm_enabled=True,
            fallback_used=False,
            message="DeepSeek 抽取完成并已写入图数据库",
        )

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
