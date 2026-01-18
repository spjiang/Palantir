from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Iterable, Optional

import psycopg2
from psycopg2.pool import SimpleConnectionPool


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
        # 基础表：任务/证据/事件时间线
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

