from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field


app = FastAPI(title="Flood Demo Model Service", version="0.1.0")


SEED = int(os.getenv("MODEL_SEED", "42"))

# 纯 Python “开源小模型”（演示级）：
# 为了避免 scipy/numpy 等编译依赖导致的容器构建失败，这里用可解释的线性/规则打分模型。
MODEL_VERSION = f"open-rule-linear-v1-seed-{SEED}"
FEATURE_NAMES = [
    "rain_now_mmph",
    "rain_1h_mm",
    "water_level_m",
    "elevation_m",
    "drainage_capacity",
    "pump_fault",
    "traffic_index",
]


class InferTarget(BaseModel):
    target_id: str
    features: dict[str, Any] = Field(default_factory=dict)


class InferTopNRequest(BaseModel):
    time: str
    area_id: str
    targets: list[InferTarget]


class InferItem(BaseModel):
    target_id: str
    target_type: str = "road_segment"
    risk_score: float
    risk_level: str
    confidence: float
    explain_factors: list[str]
    model_version: str


class InferTopNResponse(BaseModel):
    items: list[InferItem]


def _risk_level(score: float) -> str:
    if score >= 7.0:
        return "红"
    if score >= 5.0:
        return "橙"
    if score >= 3.5:
        return "黄"
    return "蓝"


def _safe_float(v: Any, default: float) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _compute(features: dict[str, Any]) -> tuple[float, float, list[str]]:
    """
    返回：(risk_score, confidence, explain_factors)
    - risk_score：0~10
    - confidence：0.1~0.95
    - explain_factors：Top 3 贡献因子 + 风险分
    """
    rain_now = _safe_float(features.get("rain_now_mmph"), 0.0)  # 当前雨强
    rain_1h = _safe_float(features.get("rain_1h_mm"), 0.0)  # 1h 累计雨量
    water_level = _safe_float(features.get("water_level_m"), 0.0)  # 水位
    elevation = _safe_float(features.get("elevation_m"), 3.0)  # 海拔（低洼更危险）
    drainage = _safe_float(features.get("drainage_capacity"), 1.0)  # 排水能力
    pump_status = str(features.get("pump_status", "running"))
    pump_fault = 1.0 if pump_status.lower() in {"fault", "down", "offline"} else 0.0
    traffic_index = _safe_float(features.get("traffic_index"), 0.0)

    # 可解释线性/规则打分（演示级、非生产）
    # 雨更大、水位更高、低洼、排水更差、泵故障、拥堵更危险
    score = 0.0
    contrib: list[tuple[str, float]] = []

    c = 0.03 * rain_now
    score += c
    contrib.append(("雨强", abs(c)))

    c = 0.02 * rain_1h
    score += c
    contrib.append(("累计雨量", abs(c)))

    c = 0.90 * water_level
    score += c
    contrib.append(("水位", abs(c)))

    lowland = max(0.0, 3.0 - elevation)
    c = 0.60 * lowland
    score += c
    contrib.append(("低洼度", abs(c)))

    lack_drainage = max(0.0, 1.5 - drainage)
    c = 0.80 * lack_drainage
    score += c
    contrib.append(("排水能力不足", abs(c)))

    c = 1.50 * pump_fault
    score += c
    contrib.append(("泵站故障", abs(c)))

    c = 0.80 * traffic_index
    score += c
    contrib.append(("道路拥堵", abs(c)))

    # 归一到 0~10
    if score < 0:
        score = 0.0
    if score > 10:
        score = 10.0

    # 置信度（演示）：关键字段缺失会降低
    confidence = 0.85
    if "rain_now_mmph" not in features:
        confidence -= 0.20
    if "water_level_m" not in features:
        confidence -= 0.20
    if "pump_status" not in features:
        confidence -= 0.10
    if confidence < 0.1:
        confidence = 0.1
    if confidence > 0.95:
        confidence = 0.95

    contrib.sort(key=lambda x: x[1], reverse=True)
    explain = [name for name, _ in contrib[:3]]
    explain.append(f"风险分={score:.2f}")
    return score, confidence, explain


@app.get("/health")
def health():
    return {"ok": True, "model_version": MODEL_VERSION}


@app.post("/infer/topn", response_model=InferTopNResponse)
def infer_topn(req: InferTopNRequest):
    items: list[InferItem] = []
    for t in req.targets:
        score, confidence, explain_factors = _compute(t.features)
        items.append(
            InferItem(
                target_id=t.target_id,
                risk_score=score,
                risk_level=_risk_level(score),
                confidence=confidence,
                explain_factors=explain_factors,
                model_version=MODEL_VERSION,
            )
        )
    items.sort(key=lambda it: it.risk_score, reverse=True)
    return InferTopNResponse(items=items)


