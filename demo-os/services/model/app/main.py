from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel, Field
from sklearn.linear_model import Ridge


app = FastAPI(title="Flood Demo Model Service", version="0.1.0")


SEED = int(os.getenv("MODEL_SEED", "42"))
rng = np.random.default_rng(SEED)


@dataclass
class Trained:
    model: Ridge
    feature_names: list[str]
    version: str


def train_synthetic() -> Trained:
    """
    演示级开源小模型：
    用合成数据训练一个 Ridge 回归，输出 risk_score 并给出 explain_factors（按权重贡献排序）。
    """
    feature_names = [
        "rain_now_mmph",
        "rain_1h_mm",
        "water_level_m",
        "elevation_m",
        "drainage_capacity",
        "pump_fault",
        "traffic_index",
    ]
    n = 2000
    X = rng.normal(size=(n, len(feature_names)))
    # 让特征更像真实量纲（粗略）
    X[:, 0] = np.clip(30 + 15 * X[:, 0], 0, 120)  # rain_now
    X[:, 1] = np.clip(20 + 10 * X[:, 1], 0, 80)  # rain_1h
    X[:, 2] = np.clip(2.0 + 0.8 * X[:, 2], 0, 6)  # water_level
    X[:, 3] = np.clip(3.0 + 1.2 * X[:, 3], -1, 10)  # elevation (低更危险)
    X[:, 4] = np.clip(1.0 + 0.5 * X[:, 4], 0.1, 3.0)  # drainage
    X[:, 5] = (rng.random(n) < 0.2).astype(float)  # pump_fault
    X[:, 6] = np.clip(0.4 + 0.2 * X[:, 6], 0, 1)  # traffic_index

    # 构造风险函数：雨更大、水位更高、低洼、更差排水、泵故障、拥堵更危险
    y = (
        0.03 * X[:, 0]
        + 0.02 * X[:, 1]
        + 0.25 * X[:, 2]
        + 0.15 * (3.0 - X[:, 3])  # elevation 越低越高风险
        + 0.20 * (1.5 - X[:, 4])
        + 1.0 * X[:, 5]
        + 0.6 * X[:, 6]
    )
    y = np.clip(y + rng.normal(scale=0.3, size=n), 0, 10)

    model = Ridge(alpha=1.0, random_state=SEED)
    model.fit(X, y)
    return Trained(model=model, feature_names=feature_names, version="open-model-ridge-v1")


trained = train_synthetic()


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


def _vectorize(features: dict[str, Any]) -> np.ndarray:
    # 特征缺失时使用安全缺省（演示）
    rain_now = float(features.get("rain_now_mmph", 0.0))
    rain_1h = float(features.get("rain_1h_mm", 0.0))
    water_level = float(features.get("water_level_m", 0.0))
    elevation = float(features.get("elevation_m", 3.0))
    drainage = float(features.get("drainage_capacity", 1.0))
    pump_status = str(features.get("pump_status", "running"))
    pump_fault = 1.0 if pump_status.lower() in {"fault", "down", "offline"} else 0.0
    traffic_index = float(features.get("traffic_index", 0.0))
    return np.array([rain_now, rain_1h, water_level, elevation, drainage, pump_fault, traffic_index], dtype=float)


def _explain(x: np.ndarray, score: float) -> list[str]:
    # 简单解释：按 |w_i * x_i| 排序（演示）
    w = trained.model.coef_
    contrib = np.abs(w * x)
    idx = np.argsort(contrib)[::-1][:4]
    mapping = {
        "rain_now_mmph": "雨强",
        "rain_1h_mm": "累计雨量",
        "water_level_m": "水位",
        "elevation_m": "低洼度",
        "drainage_capacity": "排水能力不足",
        "pump_fault": "泵站故障",
        "traffic_index": "道路拥堵",
    }
    factors = []
    for i in idx:
        name = trained.feature_names[i]
        factors.append(mapping.get(name, name))
    # 补一个总分解释
    factors.append(f"风险分={score:.2f}")
    return factors


@app.get("/health")
def health():
    return {"ok": True, "model_version": trained.version}


@app.post("/infer/topn", response_model=InferTopNResponse)
def infer_topn(req: InferTopNRequest):
    items: list[InferItem] = []
    for t in req.targets:
        x = _vectorize(t.features)
        score = float(trained.model.predict(x.reshape(1, -1))[0])
        score = float(np.clip(score, 0, 10))
        # 置信度（演示）：雨量缺失或 pump_status unknown 降低
        confidence = 0.8
        if "rain_now_mmph" not in t.features:
            confidence -= 0.2
        if "pump_status" not in t.features:
            confidence -= 0.1
        confidence = float(np.clip(confidence, 0.1, 0.95))
        items.append(
            InferItem(
                target_id=t.target_id,
                risk_score=score,
                risk_level=_risk_level(score),
                confidence=confidence,
                explain_factors=_explain(x, score),
                model_version=trained.version,
            )
        )
    items.sort(key=lambda it: it.risk_score, reverse=True)
    return InferTopNResponse(items=items)


