from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import psycopg2

from ...deps import pg

router = APIRouter(tags=["L1-DataIngestionGovernance"])


class SegmentCreate(BaseModel):
    name: str = Field(..., description="管段名称，例如：管段A")
    latitude: float | None = Field(default=None, description="可选：纬度，例如 40.05")
    longitude: float | None = Field(default=None, description="可选：经度，例如 116.30")
    ontology_class: str | None = Field(default="管段", description="可选：本体类名称（用于 L3 沿 instance_of 找规则/行为），默认=管段")

class SegmentUpdate(BaseModel):
    name: str = Field(..., description="新的管段名称，例如：管段B")
    latitude: float | None = Field(default=None, description="可选：纬度（不填则保留原值）")
    longitude: float | None = Field(default=None, description="可选：经度（不填则保留原值）")
    ontology_class: str | None = Field(default=None, description="可选：本体类名称（不填则保留原值）")


class SensorCreate(BaseModel):
    segment_id: str = Field(..., description="管段ID（seg-xxx）")
    name: str = Field(..., description="传感器名称，例如：压力传感器-1")
    sensor_type: str = Field(default="压力/流量", description="传感器类型，例如：压力/流量")

class SensorUpdate(BaseModel):
    name: str | None = Field(default=None)
    sensor_type: str | None = Field(default=None)
    segment_id: str | None = Field(default=None)


class ReadingCreate(BaseModel):
    sensor_id: str = Field(..., description="传感器ID（sen-xxx）")
    pressure: float | None = Field(default=None, description="压力")
    flow: float | None = Field(default=None, description="流量")
    # 简化：可把任意扩展字段写进 raw
    raw: dict = Field(default_factory=dict)


class AlarmIngest(BaseModel):
    """
    原始告警信号接入（L1 只负责接收与存储，不做推理）。
    若设备/上游系统本来就产生告警，在这里落库即可。
    """

    alarm_type: str = Field(..., description="告警类型，例如：压力异常/设备故障")
    severity: str = Field(default="medium", description="low/medium/high")
    message: str = Field(..., description="告警描述")
    sensor_id: str | None = Field(default=None, description="可选：传感器ID")
    segment_id: str | None = Field(default=None, description="可选：管段ID")
    reading_id: str | None = Field(default=None, description="可选：关联读数ID")
    raw: dict = Field(default_factory=dict, description="可选：原始告警 payload")


def _require_pg():
    if not pg:
        raise HTTPException(500, "PG_DSN not configured")
    try:
        pg.connect()
    except Exception as e:
        raise HTTPException(500, f"Postgres not ready: {e}")


@router.get("/l1/segments")
def list_segments():
    _require_pg()
    return {"items": pg.list_segments()}


@router.post("/l1/segments")
def create_segment(payload: SegmentCreate):
    _require_pg()
    try:
        return pg.create_segment(name=payload.name, latitude=payload.latitude, longitude=payload.longitude, ontology_class=payload.ontology_class)
    except psycopg2.Error as e:
        raise HTTPException(400, f"创建管段失败：{e.pgerror or str(e)}")


@router.put("/l1/segments/{segment_id}")
def update_segment(segment_id: str, payload: SegmentUpdate):
    _require_pg()
    try:
        row = pg.update_segment(
            segment_id=segment_id,
            name=payload.name,
            latitude=payload.latitude,
            longitude=payload.longitude,
            ontology_class=payload.ontology_class,
        )
        if not row:
            raise HTTPException(404, "管段不存在")
        return row
    except psycopg2.Error as e:
        raise HTTPException(400, f"修改管段失败：{e.pgerror or str(e)}")


@router.delete("/l1/segments/{segment_id}")
def delete_segment(segment_id: str):
    _require_pg()
    try:
        ok = pg.delete_segment(segment_id=segment_id)
        if not ok:
            raise HTTPException(404, "管段不存在")
        return {"ok": True}
    except psycopg2.Error as e:
        raise HTTPException(400, f"删除管段失败：{e.pgerror or str(e)}")


@router.get("/l1/sensors")
def list_sensors(segment_id: str | None = None):
    _require_pg()
    return {"items": pg.list_sensors(segment_id=segment_id)}


@router.post("/l1/sensors")
def create_sensor(payload: SensorCreate):
    _require_pg()
    try:
        return pg.create_sensor(name=payload.name, sensor_type=payload.sensor_type, segment_id=payload.segment_id)
    except psycopg2.Error as e:
        raise HTTPException(400, f"创建传感器失败：{e.pgerror or str(e)}")


@router.put("/l1/sensors/{sensor_id}")
def update_sensor(sensor_id: str, payload: SensorUpdate):
    _require_pg()
    try:
        row = pg.update_sensor(sensor_id=sensor_id, name=payload.name, sensor_type=payload.sensor_type, segment_id=payload.segment_id)
        if not row:
            raise HTTPException(404, "传感器不存在")
        return row
    except psycopg2.Error as e:
        raise HTTPException(400, f"修改传感器失败：{e.pgerror or str(e)}")


@router.delete("/l1/sensors/{sensor_id}")
def delete_sensor(sensor_id: str):
    _require_pg()
    try:
        ok = pg.delete_sensor(sensor_id=sensor_id)
        if not ok:
            raise HTTPException(404, "传感器不存在")
        return {"ok": True}
    except psycopg2.Error as e:
        raise HTTPException(400, f"删除传感器失败：{e.pgerror or str(e)}")


@router.get("/l1/readings")
def list_readings(segment_id: str | None = None, limit: int = 200):
    _require_pg()
    return {"items": pg.list_readings(segment_id=segment_id, limit=limit)}


@router.get("/l1/alarms")
def list_alarms(segment_id: str | None = None, limit: int = 200):
    _require_pg()
    return {"items": pg.list_alarms(segment_id=segment_id, limit=limit)}


@router.post("/l1/readings")
def add_reading(payload: ReadingCreate):
    _require_pg()
    reading = pg.add_reading(sensor_id=payload.sensor_id, pressure=payload.pressure, flow=payload.flow, raw=payload.raw or {})
    return {"reading": reading}


@router.post("/l1/alarms")
def ingest_alarm(payload: AlarmIngest):
    _require_pg()
    try:
        seg_id = payload.segment_id
        if not seg_id and payload.sensor_id:
            s = pg.fetchone("SELECT * FROM sensors WHERE id=%s;", (payload.sensor_id,))
            seg_id = s.get("segment_id") if s else None
        if not seg_id and not payload.sensor_id:
            raise HTTPException(400, "sensor_id 与 segment_id 至少提供一个")
        row = pg.create_alarm(
            alarm_type=payload.alarm_type,
            severity=payload.severity,
            message=payload.message,
            sensor_id=payload.sensor_id,
            segment_id=seg_id,
            reading_id=payload.reading_id,
            raw={**(payload.raw or {}), "source": "l1"},
        )
        return row
    except HTTPException:
        raise
    except psycopg2.Error as e:
        raise HTTPException(400, f"写入原始告警失败：{e.pgerror or str(e)}")


@router.post("/l1/purge")
def purge_sensing_and_alerts(confirm: str = "", segment_id: str | None = None):
    """
    清空“感知数据 + 预警数据”：
    - 感知数据：sensor_readings
    - 预警数据：alarms（含 L1 原始告警、L3 告警结论）、risk_events
    默认不删除管段/传感器。
    """
    _require_pg()
    if (confirm or "").strip().upper() != "YES":
        raise HTTPException(400, "missing confirm=YES")
    try:
        return {"ok": True, "segment_id": segment_id, "deleted": pg.purge_sensing_and_alerts(segment_id=segment_id)}
    except psycopg2.Error as e:
        raise HTTPException(400, f"清空失败：{e.pgerror or str(e)}")

