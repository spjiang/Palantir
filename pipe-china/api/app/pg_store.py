from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Iterable, Optional

import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import Json


class PostgresStore:
    """
    轻量 PostgreSQL 存储：
    - L1：传感器/告警等原始数据（后续扩展）
    - L5：任务/证据/状态回写
    - L6：追溯报表（事件时间线）

    设计原则：
    - 先跑通闭环（可用、可追溯、可联动）
    - 不引入复杂迁移框架（后续可换 Alembic）
    """

    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool: Optional[SimpleConnectionPool] = None

    def connect(self) -> None:
        if self.pool:
            return
        # 最多等 30s，避免 compose 启动时 postgres 尚未 ready
        last = None
        for _ in range(30):
            try:
                self.pool = SimpleConnectionPool(minconn=1, maxconn=10, dsn=self.dsn)
                self.init_schema()
                return
            except Exception as e:  # pragma: no cover
                last = e
                time.sleep(1)
        raise RuntimeError(f"Postgres connect failed after retries: {last!r}")

    def close(self) -> None:
        if self.pool:
            try:
                self.pool.closeall()
            finally:
                self.pool = None

    def _conn(self):
        if not self.pool:
            self.connect()
        assert self.pool is not None
        return self.pool.getconn()

    def _put(self, conn) -> None:
        assert self.pool is not None
        self.pool.putconn(conn)

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        conn = self._conn()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
        finally:
            self._put(conn)

    def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    cols = [d.name for d in cur.description] if cur.description else []
                    return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            self._put(conn)

    def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> Optional[dict[str, Any]]:
        conn = self._conn()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    row = cur.fetchone()
                    if not row:
                        return None
                    cols = [d.name for d in cur.description] if cur.description else []
                    return dict(zip(cols, row))
        finally:
            self._put(conn)

    def init_schema(self) -> None:
        # L1：管段/传感器/读数/告警（用于模拟真实接入）
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS pipeline_segments (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL UNIQUE,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        # 兼容迁移：旧库没有 space_id 时补齐（必须先补列，再建索引/写入）
        self.execute("ALTER TABLE pipeline_segments ADD COLUMN IF NOT EXISTS space_id TEXT NOT NULL DEFAULT 'default';")
        # Space/Tenant：把“单租户 name 唯一”升级为 “(space_id,name) 唯一”（产品级隔离）
        # 兼容迁移：先删旧约束（默认名称通常为 pipeline_segments_name_key），再建组合唯一索引
        self.execute("ALTER TABLE pipeline_segments DROP CONSTRAINT IF EXISTS pipeline_segments_name_key;")
        self.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_pipeline_segments_space_name ON pipeline_segments(space_id, name);")
        # 兼容迁移：后续补齐坐标字段（老库没有这两列）
        self.execute("ALTER TABLE pipeline_segments ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;")
        self.execute("ALTER TABLE pipeline_segments ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;")
        # 语义绑定：该实例属于哪个“本体类”（用于 L3 通过 instance_of 找规则/行为）
        self.execute("ALTER TABLE pipeline_segments ADD COLUMN IF NOT EXISTS ontology_class TEXT;")
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS sensors (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              sensor_type TEXT NOT NULL,
              segment_id TEXT NOT NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              UNIQUE(name, segment_id),
              FOREIGN KEY(segment_id) REFERENCES pipeline_segments(id) ON DELETE CASCADE
            );
            """
        )
        self.execute("ALTER TABLE sensors ADD COLUMN IF NOT EXISTS space_id TEXT NOT NULL DEFAULT 'default';")
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS sensor_readings (
              id TEXT PRIMARY KEY,
              sensor_id TEXT NOT NULL,
              ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              pressure DOUBLE PRECISION,
              flow DOUBLE PRECISION,
              raw JSONB,
              FOREIGN KEY(sensor_id) REFERENCES sensors(id) ON DELETE CASCADE
            );
            """
        )
        self.execute("ALTER TABLE sensor_readings ADD COLUMN IF NOT EXISTS space_id TEXT NOT NULL DEFAULT 'default';")
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS alarms (
              id TEXT PRIMARY KEY,
              ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              alarm_type TEXT NOT NULL,
              severity TEXT NOT NULL,
              sensor_id TEXT,
              segment_id TEXT,
              message TEXT NOT NULL,
              reading_id TEXT,
              raw JSONB,
              FOREIGN KEY(sensor_id) REFERENCES sensors(id) ON DELETE SET NULL,
              FOREIGN KEY(segment_id) REFERENCES pipeline_segments(id) ON DELETE SET NULL
            );
            """
        )
        self.execute("ALTER TABLE alarms ADD COLUMN IF NOT EXISTS space_id TEXT NOT NULL DEFAULT 'default';")

        # L3：风险评估事件（用于追溯/联动）
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS risk_events (
              id TEXT PRIMARY KEY,
              draft_id TEXT,
              segment_id TEXT,
              segment_name TEXT,
              risk_score DOUBLE PRECISION NOT NULL,
              risk_state TEXT NOT NULL,
              explain TEXT,
              evidence JSONB,
              ts TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        self.execute("ALTER TABLE risk_events ADD COLUMN IF NOT EXISTS space_id TEXT NOT NULL DEFAULT 'default';")
        # 可复现/可审计：补齐 inference/LLM 快照（MVP：JSONB）
        self.execute("ALTER TABLE risk_events ADD COLUMN IF NOT EXISTS inference_id TEXT;")
        self.execute("ALTER TABLE risk_events ADD COLUMN IF NOT EXISTS llm_mode TEXT;")
        self.execute("ALTER TABLE risk_events ADD COLUMN IF NOT EXISTS llm_input JSONB;")
        self.execute("ALTER TABLE risk_events ADD COLUMN IF NOT EXISTS llm_output JSONB;")

        # L5：任务/证据/事件时间线
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
              id TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              task_type TEXT NOT NULL,
              status TEXT NOT NULL,
              draft_id TEXT,
              target_entity_id TEXT,
              target_entity_name TEXT,
              source_behavior TEXT,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        self.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS space_id TEXT NOT NULL DEFAULT 'default';")
        # 兼容迁移：为任务增加“动作编排(Action Plan)”与“决策原因”字段（MVP）
        self.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS action_plan JSONB;")
        self.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS decision_reason TEXT;")
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS evidence (
              id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              evidence_type TEXT NOT NULL,
              content TEXT NOT NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            );
            """
        )
        self.execute("ALTER TABLE evidence ADD COLUMN IF NOT EXISTS space_id TEXT NOT NULL DEFAULT 'default';")
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS task_events (
              id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              event_type TEXT NOT NULL,
              message TEXT NOT NULL,
              ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            );
            """
        )
        self.execute("ALTER TABLE task_events ADD COLUMN IF NOT EXISTS space_id TEXT NOT NULL DEFAULT 'default';")

        # L5：任务动作执行记录（Action Run）
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS task_action_runs (
              id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              seq INTEGER NOT NULL,
              action_type TEXT NOT NULL,
              params JSONB,
              status TEXT NOT NULL,
              result JSONB,
              ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            );
            """
        )
        self.execute("ALTER TABLE task_action_runs ADD COLUMN IF NOT EXISTS space_id TEXT NOT NULL DEFAULT 'default';")

        # L2：本体发布版本（Release）+ 审计（Audit）
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS ontology_releases (
              id TEXT PRIMARY KEY,
              ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              draft_id TEXT,
              note TEXT,
              nodes JSONB NOT NULL,
              edges JSONB NOT NULL
            );
            """
        )
        self.execute("ALTER TABLE ontology_releases ADD COLUMN IF NOT EXISTS space_id TEXT NOT NULL DEFAULT 'default';")
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS ontology_audit (
              id TEXT PRIMARY KEY,
              ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              actor TEXT,
              action TEXT NOT NULL,
              payload JSONB
            );
            """
        )
        self.execute("ALTER TABLE ontology_audit ADD COLUMN IF NOT EXISTS space_id TEXT NOT NULL DEFAULT 'default';")

        # L3：同步/推理状态（用于“增量触发 + 成本闸门”）
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS l3_sync_state (
              draft_id TEXT NOT NULL,
              segment_id TEXT NOT NULL,
              last_reading_ts TIMESTAMPTZ,
              last_alarm_ts TIMESTAMPTZ,
              last_sync_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              last_reasoning_mode TEXT,
              PRIMARY KEY (draft_id, segment_id, space_id)
            );
            """
        )
        self.execute("ALTER TABLE l3_sync_state ADD COLUMN IF NOT EXISTS space_id TEXT NOT NULL DEFAULT 'default';")

    # -------- L1: 手动写入/模拟接入 --------
    def create_segment(
        self,
        *,
        space_id: str = "default",
        name: str,
        latitude: float | None = None,
        longitude: float | None = None,
        ontology_class: str | None = None,
    ) -> dict[str, Any]:
        seg_id = f"seg-{uuid.uuid4().hex[:10]}"
        created = self.fetchone(
            "INSERT INTO pipeline_segments (id, name, space_id, latitude, longitude, ontology_class) VALUES (%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT DO NOTHING RETURNING id,name,space_id,latitude,longitude,ontology_class,created_at;",
            (seg_id, name.strip(), (space_id or "default").strip() or "default", latitude, longitude, (ontology_class or "管段").strip() if ontology_class is not None else "管段"),
        )
        if created:
            created["__created"] = True
            return created
        row = self.fetchone("SELECT * FROM pipeline_segments WHERE space_id=%s AND name=%s;", ((space_id or "default").strip() or "default", name.strip()))
        assert row is not None
        row["__created"] = False
        return row

    def update_segment(
        self,
        *,
        space_id: str = "default",
        segment_id: str,
        name: str,
        latitude: float | None = None,
        longitude: float | None = None,
        ontology_class: str | None = None,
    ) -> Optional[dict[str, Any]]:
        cur = self.fetchone("SELECT * FROM pipeline_segments WHERE id=%s AND space_id=%s;", (segment_id, (space_id or "default").strip() or "default"))
        if not cur:
            return None
        lat = latitude if latitude is not None else cur.get("latitude")
        lon = longitude if longitude is not None else cur.get("longitude")
        oc = (ontology_class.strip() if isinstance(ontology_class, str) and ontology_class.strip() else cur.get("ontology_class") or "管段")
        self.execute(
            "UPDATE pipeline_segments SET name=%s, latitude=%s, longitude=%s, ontology_class=%s WHERE id=%s AND space_id=%s;",
            (name.strip(), lat, lon, oc, segment_id, (space_id or "default").strip() or "default"),
        )
        return self.fetchone("SELECT * FROM pipeline_segments WHERE id=%s AND space_id=%s;", (segment_id, (space_id or "default").strip() or "default"))

    def delete_segment(self, *, space_id: str = "default", segment_id: str) -> bool:
        row = self.fetchone("SELECT id FROM pipeline_segments WHERE id=%s AND space_id=%s;", (segment_id, (space_id or "default").strip() or "default"))
        if not row:
            return False
        self.execute("DELETE FROM pipeline_segments WHERE id=%s AND space_id=%s;", (segment_id, (space_id or "default").strip() or "default"))
        return True

    def list_segments(self, *, space_id: str = "default") -> list[dict[str, Any]]:
        return self.fetchall("SELECT * FROM pipeline_segments WHERE space_id=%s ORDER BY created_at DESC;", ((space_id or "default").strip() or "default",))

    def create_sensor(self, *, space_id: str = "default", name: str, sensor_type: str, segment_id: str) -> dict[str, Any]:
        sid = f"sen-{uuid.uuid4().hex[:10]}"
        # 保护：segment 必须属于同 space
        seg = self.fetchone("SELECT id FROM pipeline_segments WHERE id=%s AND space_id=%s;", (segment_id, (space_id or "default").strip() or "default"))
        if not seg:
            raise ValueError("segment_id not found in this space")
        created = self.fetchone(
            "INSERT INTO sensors (id, name, sensor_type, segment_id, space_id) VALUES (%s,%s,%s,%s,%s) ON CONFLICT(name, segment_id) DO NOTHING RETURNING id,name,sensor_type,segment_id,space_id,created_at;",
            (sid, name.strip(), sensor_type.strip(), segment_id, (space_id or "default").strip() or "default"),
        )
        if created:
            created["__created"] = True
            return created
        row = self.fetchone("SELECT * FROM sensors WHERE name=%s AND segment_id=%s AND space_id=%s;", (name.strip(), segment_id, (space_id or "default").strip() or "default"))
        assert row is not None
        row["__created"] = False
        return row

    def update_sensor(
        self,
        *,
        space_id: str = "default",
        sensor_id: str,
        name: str | None = None,
        sensor_type: str | None = None,
        segment_id: str | None = None,
    ) -> Optional[dict[str, Any]]:
        cur = self.fetchone("SELECT * FROM sensors WHERE id=%s AND space_id=%s;", (sensor_id, (space_id or "default").strip() or "default"))
        if not cur:
            return None
        new_name = (name.strip() if isinstance(name, str) and name.strip() else cur["name"])
        new_type = (sensor_type.strip() if isinstance(sensor_type, str) and sensor_type.strip() else cur["sensor_type"])
        new_seg = (segment_id if isinstance(segment_id, str) and segment_id.strip() else cur["segment_id"])
        if new_seg != cur["segment_id"]:
            seg = self.fetchone("SELECT id FROM pipeline_segments WHERE id=%s AND space_id=%s;", (new_seg, (space_id or "default").strip() or "default"))
            if not seg:
                return None
        self.execute(
            "UPDATE sensors SET name=%s, sensor_type=%s, segment_id=%s WHERE id=%s AND space_id=%s;",
            (new_name, new_type, new_seg, sensor_id, (space_id or "default").strip() or "default"),
        )
        return self.fetchone("SELECT * FROM sensors WHERE id=%s AND space_id=%s;", (sensor_id, (space_id or "default").strip() or "default"))

    def delete_sensor(self, *, space_id: str = "default", sensor_id: str) -> bool:
        row = self.fetchone("SELECT id FROM sensors WHERE id=%s AND space_id=%s;", (sensor_id, (space_id or "default").strip() or "default"))
        if not row:
            return False
        self.execute("DELETE FROM sensors WHERE id=%s AND space_id=%s;", (sensor_id, (space_id or "default").strip() or "default"))
        return True

    def list_sensors(self, *, space_id: str = "default", segment_id: str | None = None) -> list[dict[str, Any]]:
        if segment_id:
            return self.fetchall("SELECT * FROM sensors WHERE space_id=%s AND segment_id=%s ORDER BY created_at DESC;", ((space_id or "default").strip() or "default", segment_id))
        return self.fetchall("SELECT * FROM sensors WHERE space_id=%s ORDER BY created_at DESC;", ((space_id or "default").strip() or "default",))

    def add_reading(
        self,
        *,
        space_id: str = "default",
        sensor_id: str,
        pressure: float | None,
        flow: float | None,
        raw: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # 保护：sensor 必须属于 space
        s = self.fetchone("SELECT id FROM sensors WHERE id=%s AND space_id=%s;", (sensor_id, (space_id or "default").strip() or "default"))
        if not s:
            raise ValueError("sensor_id not found in this space")
        rid = f"rd-{uuid.uuid4().hex[:10]}"
        self.execute(
            "INSERT INTO sensor_readings (id, sensor_id, space_id, pressure, flow, raw) VALUES (%s,%s,%s,%s,%s,%s);",
            (rid, sensor_id, (space_id or "default").strip() or "default", pressure, flow, Json(raw) if raw is not None else None),
        )
        row = self.fetchone("SELECT * FROM sensor_readings WHERE id=%s;", (rid,))
        assert row is not None
        return row

    def list_readings(self, *, space_id: str = "default", segment_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        if segment_id:
            return self.fetchall(
                """
                SELECT r.*, s.name AS sensor_name, s.sensor_type, s.segment_id
                FROM sensor_readings r
                JOIN sensors s ON s.id=r.sensor_id
                WHERE r.space_id=%s AND s.segment_id=%s
                ORDER BY r.ts DESC
                LIMIT %s;
                """,
                ((space_id or "default").strip() or "default", segment_id, limit),
            )
        return self.fetchall(
            """
            SELECT r.*, s.name AS sensor_name, s.sensor_type, s.segment_id
            FROM sensor_readings r
            JOIN sensors s ON s.id=r.sensor_id
            WHERE r.space_id=%s
            ORDER BY r.ts DESC
            LIMIT %s;
            """,
            ((space_id or "default").strip() or "default", limit),
        )

    def create_alarm(
        self,
        *,
        space_id: str = "default",
        alarm_type: str,
        severity: str,
        message: str,
        sensor_id: str | None,
        segment_id: str | None,
        reading_id: str | None,
        raw: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        aid = f"alm-{uuid.uuid4().hex[:10]}"
        self.execute(
            "INSERT INTO alarms (id, space_id, alarm_type, severity, message, sensor_id, segment_id, reading_id, raw) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s);",
            (aid, (space_id or "default").strip() or "default", alarm_type, severity, message, sensor_id, segment_id, reading_id, Json(raw) if raw is not None else None),
        )
        row = self.fetchone("SELECT * FROM alarms WHERE id=%s;", (aid,))
        assert row is not None
        return row

    def list_alarms(self, *, space_id: str = "default", segment_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        if segment_id:
            return self.fetchall(
                "SELECT * FROM alarms WHERE space_id=%s AND segment_id=%s ORDER BY ts DESC LIMIT %s;",
                ((space_id or "default").strip() or "default", segment_id, limit),
            )
        return self.fetchall("SELECT * FROM alarms WHERE space_id=%s ORDER BY ts DESC LIMIT %s;", ((space_id or "default").strip() or "default", limit))

    def list_alarms_enriched(
        self,
        *,
        space_id: str = "default",
        segment_id: str | None = None,
        draft_id: str | None = None,
        source: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """
        告警列表（带名称字段）：
        - a.* + sensor_name + segment_name
        - 可选过滤：segment_id、raw.source（例如 source=l3 代表 L3 推理生成的“告警结论”）
        """
        where = []
        params: list[Any] = []
        where.append("a.space_id=%s")
        params.append((space_id or "default").strip() or "default")
        if segment_id:
            where.append("a.segment_id=%s")
            params.append(segment_id)
        if draft_id:
            where.append("(a.raw->>'draft_id')=%s")
            params.append(str(draft_id))
        if source:
            where.append("(a.raw->>'source')=%s")
            params.append(str(source))
        wh = ("WHERE " + " AND ".join(where)) if where else ""
        params.append(limit)
        return self.fetchall(
            f"""
            SELECT
              a.*,
              s.name AS sensor_name,
              p.name AS segment_name
            FROM alarms a
            LEFT JOIN sensors s ON s.id=a.sensor_id
            LEFT JOIN pipeline_segments p ON p.id=a.segment_id
            {wh}
            ORDER BY a.ts DESC
            LIMIT %s;
            """,
            tuple(params),
        )

    # -------- L3: 风险事件 --------
    def add_risk_event(
        self,
        *,
        space_id: str = "default",
        draft_id: str | None,
        segment_id: str | None,
        segment_name: str | None,
        risk_score: float,
        risk_state: str,
        explain: str | None,
        evidence: dict[str, Any] | None = None,
        inference_id: str | None = None,
        llm_mode: str | None = None,
        llm_input: dict[str, Any] | None = None,
        llm_output: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        rid = f"risk-{uuid.uuid4().hex[:10]}"
        self.execute(
            """
            INSERT INTO risk_events (id, space_id, draft_id, segment_id, segment_name, risk_score, risk_state, explain, evidence, inference_id, llm_mode, llm_input, llm_output)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
            """,
            (
                rid,
                (space_id or "default").strip() or "default",
                draft_id,
                segment_id,
                segment_name,
                float(risk_score),
                risk_state,
                explain,
                Json(evidence) if evidence is not None else None,
                inference_id,
                llm_mode,
                Json(llm_input) if llm_input is not None else None,
                Json(llm_output) if llm_output is not None else None,
            ),
        )
        row = self.fetchone("SELECT * FROM risk_events WHERE id=%s;", (rid,))
        assert row is not None
        return row

    def list_risk_events(self, *, space_id: str = "default", draft_id: str | None = None, segment_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        sid = (space_id or "default").strip() or "default"
        if draft_id and segment_id:
            return self.fetchall(
                "SELECT * FROM risk_events WHERE space_id=%s AND draft_id=%s AND segment_id=%s ORDER BY ts DESC LIMIT %s;",
                (sid, draft_id, segment_id, limit),
            )
        if draft_id:
            return self.fetchall("SELECT * FROM risk_events WHERE space_id=%s AND draft_id=%s ORDER BY ts DESC LIMIT %s;", (sid, draft_id, limit))
        if segment_id:
            return self.fetchall("SELECT * FROM risk_events WHERE space_id=%s AND segment_id=%s ORDER BY ts DESC LIMIT %s;", (sid, segment_id, limit))
        return self.fetchall("SELECT * FROM risk_events WHERE space_id=%s ORDER BY ts DESC LIMIT %s;", (sid, limit))

    def purge_sensing_and_alerts(self, *, space_id: str = "default", segment_id: str | None = None) -> dict[str, int]:
        """
        清空“感知数据 + 预警数据”：
        - 感知数据：sensor_readings
        - 预警数据：alarms（包含 L1 原始告警 & L3 告警结论）、risk_events
        默认只清空数据，不删除管段/传感器等主数据。
        """
        sid = (space_id or "default").strip() or "default"
        if segment_id:
            r1 = self.fetchone(
                """
                WITH del AS (
                  DELETE FROM sensor_readings
                  WHERE sensor_id IN (SELECT id FROM sensors WHERE segment_id=%s)
                    AND space_id=%s
                  RETURNING 1
                ) SELECT COUNT(*) AS n FROM del;
                """,
                (segment_id, sid),
            ) or {"n": 0}
            r2 = self.fetchone(
                "WITH del AS (DELETE FROM alarms WHERE segment_id=%s AND space_id=%s RETURNING 1) SELECT COUNT(*) AS n FROM del;",
                (segment_id, sid),
            ) or {"n": 0}
            r3 = self.fetchone(
                "WITH del AS (DELETE FROM risk_events WHERE segment_id=%s AND space_id=%s RETURNING 1) SELECT COUNT(*) AS n FROM del;",
                (segment_id, sid),
            ) or {"n": 0}
            return {"readings": int(r1.get("n") or 0), "alarms": int(r2.get("n") or 0), "risk_events": int(r3.get("n") or 0)}

        r1 = self.fetchone("WITH del AS (DELETE FROM sensor_readings WHERE space_id=%s RETURNING 1) SELECT COUNT(*) AS n FROM del;", (sid,)) or {"n": 0}
        r2 = self.fetchone("WITH del AS (DELETE FROM alarms WHERE space_id=%s RETURNING 1) SELECT COUNT(*) AS n FROM del;", (sid,)) or {"n": 0}
        r3 = self.fetchone("WITH del AS (DELETE FROM risk_events WHERE space_id=%s RETURNING 1) SELECT COUNT(*) AS n FROM del;", (sid,)) or {"n": 0}
        return {"readings": int(r1.get("n") or 0), "alarms": int(r2.get("n") or 0), "risk_events": int(r3.get("n") or 0)}

    # -------- L5: 任务管理 --------
    def create_task(
        self,
        *,
        space_id: str = "default",
        title: str,
        task_type: str,
        draft_id: str | None,
        target_entity_id: str | None,
        target_entity_name: str | None,
        source_behavior: str | None,
        action_plan: list[dict[str, Any]] | None = None,
        decision_reason: str | None = None,
    ) -> dict[str, Any]:
        tid = f"task-{uuid.uuid4().hex[:10]}"
        sid = (space_id or "default").strip() or "default"
        self.execute(
            """
            INSERT INTO tasks (id, title, task_type, status, space_id, draft_id, target_entity_id, target_entity_name, source_behavior, action_plan, decision_reason)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (
                tid,
                title.strip(),
                task_type.strip(),
                "pending",
                sid,
                draft_id,
                target_entity_id,
                target_entity_name,
                source_behavior,
                Json(action_plan) if action_plan is not None else None,
                decision_reason,
            ),
        )
        self.add_task_event(space_id=sid, task_id=tid, event_type="created", message=f"创建任务：{title.strip()}")
        row = self.get_task(tid, space_id=sid)
        assert row is not None
        return row

    # -------- L5: Action Run --------
    def create_action_run(
        self,
        *,
        space_id: str = "default",
        task_id: str,
        seq: int,
        action_type: str,
        params: dict[str, Any] | None = None,
        status: str = "pending",
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        rid = f"act-{uuid.uuid4().hex[:10]}"
        sid = (space_id or "default").strip() or "default"
        self.execute(
            """
            INSERT INTO task_action_runs (id, task_id, seq, action_type, params, status, result, space_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s);
            """,
            (rid, task_id, int(seq), action_type, Json(params) if params is not None else None, status, Json(result) if result is not None else None, sid),
        )
        row = self.fetchone("SELECT * FROM task_action_runs WHERE id=%s;", (rid,))
        assert row is not None
        return row

    def list_action_runs(self, *, space_id: str = "default", task_id: str) -> list[dict[str, Any]]:
        return self.fetchall(
            "SELECT * FROM task_action_runs WHERE task_id=%s AND space_id=%s ORDER BY seq ASC, ts ASC;",
            (task_id, (space_id or "default").strip() or "default"),
        )

    # -------- L2: Releases & Audit --------
    def add_ontology_release(self, *, space_id: str = "default", draft_id: str | None, note: str | None, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
        rid = f"relv-{uuid.uuid4().hex[:10]}"
        self.execute(
            "INSERT INTO ontology_releases (id, space_id, draft_id, note, nodes, edges) VALUES (%s,%s,%s,%s,%s,%s);",
            (rid, (space_id or "default").strip() or "default", draft_id, note, Json(nodes), Json(edges)),
        )
        row = self.fetchone("SELECT * FROM ontology_releases WHERE id=%s;", (rid,))
        assert row is not None
        return row

    def list_ontology_releases(self, *, space_id: str = "default", limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit or 50), 200))
        return self.fetchall(
            "SELECT * FROM ontology_releases WHERE space_id=%s ORDER BY ts DESC LIMIT %s;",
            ((space_id or "default").strip() or "default", limit),
        )

    def get_ontology_release(self, release_id: str, *, space_id: str = "default") -> Optional[dict[str, Any]]:
        return self.fetchone("SELECT * FROM ontology_releases WHERE id=%s AND space_id=%s;", (release_id, (space_id or "default").strip() or "default"))

    def add_audit(self, *, space_id: str = "default", actor: str | None, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        aid = f"aud-{uuid.uuid4().hex[:10]}"
        self.execute(
            "INSERT INTO ontology_audit (id, space_id, actor, action, payload) VALUES (%s,%s,%s,%s,%s);",
            (aid, (space_id or "default").strip() or "default", actor, action, Json(payload) if payload is not None else None),
        )
        row = self.fetchone("SELECT * FROM ontology_audit WHERE id=%s;", (aid,))
        assert row is not None
        return row

    # -------- L3: Sync State --------
    def get_l3_sync_state(self, *, space_id: str = "default", draft_id: str, segment_id: str) -> Optional[dict[str, Any]]:
        return self.fetchone(
            "SELECT * FROM l3_sync_state WHERE draft_id=%s AND segment_id=%s AND space_id=%s;",
            (draft_id, segment_id, (space_id or "default").strip() or "default"),
        )

    def upsert_l3_sync_state(
        self,
        *,
        space_id: str = "default",
        draft_id: str,
        segment_id: str,
        last_reading_ts,
        last_alarm_ts,
        last_reasoning_mode: str | None,
    ) -> None:
        self.execute(
            """
            INSERT INTO l3_sync_state (draft_id, segment_id, space_id, last_reading_ts, last_alarm_ts, last_sync_ts, last_reasoning_mode)
            VALUES (%s,%s,%s,%s,%s,NOW(),%s)
            ON CONFLICT (draft_id, segment_id, space_id)
            DO UPDATE SET last_reading_ts=EXCLUDED.last_reading_ts,
                          last_alarm_ts=EXCLUDED.last_alarm_ts,
                          last_sync_ts=NOW(),
                          last_reasoning_mode=EXCLUDED.last_reasoning_mode;
            """,
            (draft_id, segment_id, (space_id or "default").strip() or "default", last_reading_ts, last_alarm_ts, last_reasoning_mode),
        )

    def get_latest_segment_activity(self, *, space_id: str = "default", segment_id: str) -> dict[str, Any]:
        """
        返回该管段下最新读数时间、最新告警时间（用于增量触发）。
        """
        r = self.fetchone(
            """
            SELECT MAX(r.ts) AS last_reading_ts
            FROM sensor_readings r
            WHERE r.sensor_id IN (SELECT id FROM sensors WHERE segment_id=%s);
            """,
            (segment_id,),
        ) or {"last_reading_ts": None}
        a = self.fetchone(
            "SELECT MAX(ts) AS last_alarm_ts FROM alarms WHERE segment_id=%s AND space_id=%s;",
            (segment_id, (space_id or "default").strip() or "default"),
        ) or {"last_alarm_ts": None}
        return {"last_reading_ts": r.get("last_reading_ts"), "last_alarm_ts": a.get("last_alarm_ts")}

    def add_task_event(self, *, space_id: str = "default", task_id: str, event_type: str, message: str) -> None:
        eid = f"evt-{uuid.uuid4().hex[:10]}"
        self.execute(
            "INSERT INTO task_events (id, task_id, space_id, event_type, message) VALUES (%s,%s,%s,%s,%s);",
            (eid, task_id, (space_id or "default").strip() or "default", event_type, message),
        )

    def list_tasks(self, *, space_id: str = "default", draft_id: str | None = None) -> list[dict[str, Any]]:
        sid = (space_id or "default").strip() or "default"
        if draft_id:
            return self.fetchall("SELECT * FROM tasks WHERE space_id=%s AND draft_id=%s ORDER BY created_at DESC;", (sid, draft_id))
        return self.fetchall("SELECT * FROM tasks WHERE space_id=%s ORDER BY created_at DESC;", (sid,))

    def get_task(self, task_id: str, *, space_id: str = "default") -> Optional[dict[str, Any]]:
        return self.fetchone("SELECT * FROM tasks WHERE id=%s AND space_id=%s;", (task_id, (space_id or "default").strip() or "default"))

    def update_task_status(self, task_id: str, status: str, *, space_id: str = "default") -> Optional[dict[str, Any]]:
        self.execute(
            "UPDATE tasks SET status=%s, updated_at=NOW() WHERE id=%s AND space_id=%s;",
            (status, task_id, (space_id or "default").strip() or "default"),
        )
        self.add_task_event(space_id=space_id, task_id=task_id, event_type="status", message=f"状态变更：{status}")
        return self.get_task(task_id, space_id=space_id)

    def add_evidence(self, *, space_id: str = "default", task_id: str, evidence_type: str, content: str) -> dict[str, Any]:
        eid = f"evi-{uuid.uuid4().hex[:10]}"
        self.execute(
            "INSERT INTO evidence (id, task_id, space_id, evidence_type, content) VALUES (%s,%s,%s,%s,%s);",
            (eid, task_id, (space_id or "default").strip() or "default", evidence_type, content),
        )
        self.add_task_event(space_id=space_id, task_id=task_id, event_type="evidence", message=f"新增证据：{evidence_type}")
        row = self.fetchone("SELECT * FROM evidence WHERE id=%s;", (eid,))
        assert row is not None
        return row

    def list_evidence(self, *, space_id: str = "default", task_id: str) -> list[dict[str, Any]]:
        return self.fetchall(
            "SELECT * FROM evidence WHERE task_id=%s AND space_id=%s ORDER BY created_at DESC;",
            (task_id, (space_id or "default").strip() or "default"),
        )

    def list_task_events(self, *, space_id: str = "default", task_id: str) -> list[dict[str, Any]]:
        return self.fetchall(
            "SELECT * FROM task_events WHERE task_id=%s AND space_id=%s ORDER BY ts ASC;",
            (task_id, (space_id or "default").strip() or "default"),
        )

