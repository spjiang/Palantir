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

    # -------- L1: 手动写入/模拟接入 --------
    def create_segment(
        self,
        *,
        name: str,
        latitude: float | None = None,
        longitude: float | None = None,
        ontology_class: str | None = None,
    ) -> dict[str, Any]:
        seg_id = f"seg-{uuid.uuid4().hex[:10]}"
        created = self.fetchone(
            "INSERT INTO pipeline_segments (id, name, latitude, longitude, ontology_class) VALUES (%s,%s,%s,%s,%s) "
            "ON CONFLICT(name) DO NOTHING RETURNING id,name,latitude,longitude,ontology_class,created_at;",
            (seg_id, name.strip(), latitude, longitude, (ontology_class or "管段").strip() if ontology_class is not None else "管段"),
        )
        if created:
            created["__created"] = True
            return created
        row = self.fetchone("SELECT * FROM pipeline_segments WHERE name=%s;", (name.strip(),))
        assert row is not None
        row["__created"] = False
        return row

    def update_segment(
        self,
        *,
        segment_id: str,
        name: str,
        latitude: float | None = None,
        longitude: float | None = None,
        ontology_class: str | None = None,
    ) -> Optional[dict[str, Any]]:
        cur = self.fetchone("SELECT * FROM pipeline_segments WHERE id=%s;", (segment_id,))
        if not cur:
            return None
        lat = latitude if latitude is not None else cur.get("latitude")
        lon = longitude if longitude is not None else cur.get("longitude")
        oc = (ontology_class.strip() if isinstance(ontology_class, str) and ontology_class.strip() else cur.get("ontology_class") or "管段")
        self.execute(
            "UPDATE pipeline_segments SET name=%s, latitude=%s, longitude=%s, ontology_class=%s WHERE id=%s;",
            (name.strip(), lat, lon, oc, segment_id),
        )
        return self.fetchone("SELECT * FROM pipeline_segments WHERE id=%s;", (segment_id,))

    def delete_segment(self, *, segment_id: str) -> bool:
        row = self.fetchone("SELECT id FROM pipeline_segments WHERE id=%s;", (segment_id,))
        if not row:
            return False
        self.execute("DELETE FROM pipeline_segments WHERE id=%s;", (segment_id,))
        return True

    def list_segments(self) -> list[dict[str, Any]]:
        return self.fetchall("SELECT * FROM pipeline_segments ORDER BY created_at DESC;")

    def create_sensor(self, *, name: str, sensor_type: str, segment_id: str) -> dict[str, Any]:
        sid = f"sen-{uuid.uuid4().hex[:10]}"
        created = self.fetchone(
            "INSERT INTO sensors (id, name, sensor_type, segment_id) VALUES (%s,%s,%s,%s) ON CONFLICT(name, segment_id) DO NOTHING RETURNING id,name,sensor_type,segment_id,created_at;",
            (sid, name.strip(), sensor_type.strip(), segment_id),
        )
        if created:
            created["__created"] = True
            return created
        row = self.fetchone("SELECT * FROM sensors WHERE name=%s AND segment_id=%s;", (name.strip(), segment_id))
        assert row is not None
        row["__created"] = False
        return row

    def update_sensor(
        self,
        *,
        sensor_id: str,
        name: str | None = None,
        sensor_type: str | None = None,
        segment_id: str | None = None,
    ) -> Optional[dict[str, Any]]:
        cur = self.fetchone("SELECT * FROM sensors WHERE id=%s;", (sensor_id,))
        if not cur:
            return None
        new_name = (name.strip() if isinstance(name, str) and name.strip() else cur["name"])
        new_type = (sensor_type.strip() if isinstance(sensor_type, str) and sensor_type.strip() else cur["sensor_type"])
        new_seg = (segment_id if isinstance(segment_id, str) and segment_id.strip() else cur["segment_id"])
        self.execute(
            "UPDATE sensors SET name=%s, sensor_type=%s, segment_id=%s WHERE id=%s;",
            (new_name, new_type, new_seg, sensor_id),
        )
        return self.fetchone("SELECT * FROM sensors WHERE id=%s;", (sensor_id,))

    def delete_sensor(self, *, sensor_id: str) -> bool:
        row = self.fetchone("SELECT id FROM sensors WHERE id=%s;", (sensor_id,))
        if not row:
            return False
        self.execute("DELETE FROM sensors WHERE id=%s;", (sensor_id,))
        return True

    def list_sensors(self, *, segment_id: str | None = None) -> list[dict[str, Any]]:
        if segment_id:
            return self.fetchall("SELECT * FROM sensors WHERE segment_id=%s ORDER BY created_at DESC;", (segment_id,))
        return self.fetchall("SELECT * FROM sensors ORDER BY created_at DESC;")

    def add_reading(
        self,
        *,
        sensor_id: str,
        pressure: float | None,
        flow: float | None,
        raw: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        rid = f"rd-{uuid.uuid4().hex[:10]}"
        self.execute(
            "INSERT INTO sensor_readings (id, sensor_id, pressure, flow, raw) VALUES (%s,%s,%s,%s,%s);",
            (rid, sensor_id, pressure, flow, Json(raw) if raw is not None else None),
        )
        row = self.fetchone("SELECT * FROM sensor_readings WHERE id=%s;", (rid,))
        assert row is not None
        return row

    def list_readings(self, *, segment_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        if segment_id:
            return self.fetchall(
                """
                SELECT r.*, s.name AS sensor_name, s.sensor_type, s.segment_id
                FROM sensor_readings r
                JOIN sensors s ON s.id=r.sensor_id
                WHERE s.segment_id=%s
                ORDER BY r.ts DESC
                LIMIT %s;
                """,
                (segment_id, limit),
            )
        return self.fetchall(
            """
            SELECT r.*, s.name AS sensor_name, s.sensor_type, s.segment_id
            FROM sensor_readings r
            JOIN sensors s ON s.id=r.sensor_id
            ORDER BY r.ts DESC
            LIMIT %s;
            """,
            (limit,),
        )

    def create_alarm(
        self,
        *,
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
            "INSERT INTO alarms (id, alarm_type, severity, message, sensor_id, segment_id, reading_id, raw) VALUES (%s,%s,%s,%s,%s,%s,%s,%s);",
            (aid, alarm_type, severity, message, sensor_id, segment_id, reading_id, Json(raw) if raw is not None else None),
        )
        row = self.fetchone("SELECT * FROM alarms WHERE id=%s;", (aid,))
        assert row is not None
        return row

    def list_alarms(self, *, segment_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        if segment_id:
            return self.fetchall(
                "SELECT * FROM alarms WHERE segment_id=%s ORDER BY ts DESC LIMIT %s;",
                (segment_id, limit),
            )
        return self.fetchall("SELECT * FROM alarms ORDER BY ts DESC LIMIT %s;", (limit,))

    def list_alarms_enriched(
        self,
        *,
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
        draft_id: str | None,
        segment_id: str | None,
        segment_name: str | None,
        risk_score: float,
        risk_state: str,
        explain: str | None,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        rid = f"risk-{uuid.uuid4().hex[:10]}"
        self.execute(
            """
            INSERT INTO risk_events (id, draft_id, segment_id, segment_name, risk_score, risk_state, explain, evidence)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s);
            """,
            (rid, draft_id, segment_id, segment_name, float(risk_score), risk_state, explain, Json(evidence) if evidence is not None else None),
        )
        row = self.fetchone("SELECT * FROM risk_events WHERE id=%s;", (rid,))
        assert row is not None
        return row

    def list_risk_events(self, *, draft_id: str | None = None, segment_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        if draft_id and segment_id:
            return self.fetchall(
                "SELECT * FROM risk_events WHERE draft_id=%s AND segment_id=%s ORDER BY ts DESC LIMIT %s;",
                (draft_id, segment_id, limit),
            )
        if draft_id:
            return self.fetchall("SELECT * FROM risk_events WHERE draft_id=%s ORDER BY ts DESC LIMIT %s;", (draft_id, limit))
        if segment_id:
            return self.fetchall("SELECT * FROM risk_events WHERE segment_id=%s ORDER BY ts DESC LIMIT %s;", (segment_id, limit))
        return self.fetchall("SELECT * FROM risk_events ORDER BY ts DESC LIMIT %s;", (limit,))

    def purge_sensing_and_alerts(self, *, segment_id: str | None = None) -> dict[str, int]:
        """
        清空“感知数据 + 预警数据”：
        - 感知数据：sensor_readings
        - 预警数据：alarms（包含 L1 原始告警 & L3 告警结论）、risk_events
        默认只清空数据，不删除管段/传感器等主数据。
        """
        if segment_id:
            r1 = self.fetchone(
                """
                WITH del AS (
                  DELETE FROM sensor_readings
                  WHERE sensor_id IN (SELECT id FROM sensors WHERE segment_id=%s)
                  RETURNING 1
                ) SELECT COUNT(*) AS n FROM del;
                """,
                (segment_id,),
            ) or {"n": 0}
            r2 = self.fetchone(
                "WITH del AS (DELETE FROM alarms WHERE segment_id=%s RETURNING 1) SELECT COUNT(*) AS n FROM del;",
                (segment_id,),
            ) or {"n": 0}
            r3 = self.fetchone(
                "WITH del AS (DELETE FROM risk_events WHERE segment_id=%s RETURNING 1) SELECT COUNT(*) AS n FROM del;",
                (segment_id,),
            ) or {"n": 0}
            return {"readings": int(r1.get("n") or 0), "alarms": int(r2.get("n") or 0), "risk_events": int(r3.get("n") or 0)}

        r1 = self.fetchone("WITH del AS (DELETE FROM sensor_readings RETURNING 1) SELECT COUNT(*) AS n FROM del;") or {"n": 0}
        r2 = self.fetchone("WITH del AS (DELETE FROM alarms RETURNING 1) SELECT COUNT(*) AS n FROM del;") or {"n": 0}
        r3 = self.fetchone("WITH del AS (DELETE FROM risk_events RETURNING 1) SELECT COUNT(*) AS n FROM del;") or {"n": 0}
        return {"readings": int(r1.get("n") or 0), "alarms": int(r2.get("n") or 0), "risk_events": int(r3.get("n") or 0)}

    # -------- L5: 任务管理 --------
    def create_task(
        self,
        *,
        title: str,
        task_type: str,
        draft_id: str | None,
        target_entity_id: str | None,
        target_entity_name: str | None,
        source_behavior: str | None,
    ) -> dict[str, Any]:
        tid = f"task-{uuid.uuid4().hex[:10]}"
        self.execute(
            """
            INSERT INTO tasks (id, title, task_type, status, draft_id, target_entity_id, target_entity_name, source_behavior)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (tid, title.strip(), task_type.strip(), "pending", draft_id, target_entity_id, target_entity_name, source_behavior),
        )
        self.add_task_event(task_id=tid, event_type="created", message=f"创建任务：{title.strip()}")
        row = self.get_task(tid)
        assert row is not None
        return row

    def add_task_event(self, *, task_id: str, event_type: str, message: str) -> None:
        eid = f"evt-{uuid.uuid4().hex[:10]}"
        self.execute(
            "INSERT INTO task_events (id, task_id, event_type, message) VALUES (%s,%s,%s,%s);",
            (eid, task_id, event_type, message),
        )

    def list_tasks(self, *, draft_id: str | None = None) -> list[dict[str, Any]]:
        if draft_id:
            return self.fetchall("SELECT * FROM tasks WHERE draft_id=%s ORDER BY created_at DESC;", (draft_id,))
        return self.fetchall("SELECT * FROM tasks ORDER BY created_at DESC;")

    def get_task(self, task_id: str) -> Optional[dict[str, Any]]:
        return self.fetchone("SELECT * FROM tasks WHERE id=%s;", (task_id,))

    def update_task_status(self, task_id: str, status: str) -> Optional[dict[str, Any]]:
        self.execute(
            "UPDATE tasks SET status=%s, updated_at=NOW() WHERE id=%s;",
            (status, task_id),
        )
        self.add_task_event(task_id=task_id, event_type="status", message=f"状态变更：{status}")
        return self.get_task(task_id)

    def add_evidence(self, *, task_id: str, evidence_type: str, content: str) -> dict[str, Any]:
        eid = f"evi-{uuid.uuid4().hex[:10]}"
        self.execute(
            "INSERT INTO evidence (id, task_id, evidence_type, content) VALUES (%s,%s,%s,%s);",
            (eid, task_id, evidence_type, content),
        )
        self.add_task_event(task_id=task_id, event_type="evidence", message=f"新增证据：{evidence_type}")
        row = self.fetchone("SELECT * FROM evidence WHERE id=%s;", (eid,))
        assert row is not None
        return row

    def list_evidence(self, *, task_id: str) -> list[dict[str, Any]]:
        return self.fetchall("SELECT * FROM evidence WHERE task_id=%s ORDER BY created_at DESC;", (task_id,))

    def list_task_events(self, *, task_id: str) -> list[dict[str, Any]]:
        return self.fetchall("SELECT * FROM task_events WHERE task_id=%s ORDER BY ts ASC;", (task_id,))

