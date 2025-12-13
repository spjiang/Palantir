from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# LangChain 用于“工具调用式智能体”编排（演示级：无 Key 时仍可用规则式策略）
from langchain_core.tools import tool


API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000").rstrip("/")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")


app = FastAPI(title="Flood Demo Agent Service", version="0.1.0")


class ChatRequest(BaseModel):
    incident_id: str | None = None
    area_id: str = "A-001"
    message: str


class ChatResponse(BaseModel):
    summary: str
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    risk_controls: dict[str, Any] = Field(default_factory=dict)


async def api_get(path: str, params: dict[str, Any] | None = None) -> Any:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{API_BASE_URL}{path}", params=params)
        r.raise_for_status()
        return r.json()


async def api_post(path: str, payload: dict[str, Any]) -> Any:
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(f"{API_BASE_URL}{path}", json=payload)
        r.raise_for_status()
        return r.json()


# -----------------------
# 工具：对齐 V7 的 tool calling
# -----------------------


@tool
async def query_risk_topn(area_id: str, n: int = 5) -> dict:
    """查询 TopN 风险点位（含风险/置信度/解释因子）。"""
    data = await api_get("/risk/topn", {"area_id": area_id, "n": n})
    return data


@tool
async def get_object_state(object_id: str) -> dict:
    """获取对象状态快照。"""
    data = await api_get(f"/objects/{object_id}")
    return data


@tool
async def create_task_pack(incident_id: str, tasks: list[dict]) -> dict:
    """把建议转换为可派单任务包（演示级：直接透传结构）。"""
    return {"incident_id": incident_id, "tasks": tasks}


@tool
async def trigger_workflow(incident_id: str, task_pack: dict) -> dict:
    """触发工作流派单（演示级：直接创建任务）。"""
    data = await api_post(f"/workflow/incidents/{incident_id}/tasks", {"incident_id": incident_id, "tasks": task_pack.get("tasks", [])})
    return data


def _rule_based_plan(topn: dict, incident_id: str) -> ChatResponse:
    items = topn.get("items", [])
    if not items:
        return ChatResponse(summary="当前无风险对象。")
    top = items[0]
    risk_level = top.get("risk_level")
    target_id = top.get("target_id")
    explain = top.get("explain_factors", [])

    need_approval = True if risk_level in ("红", "橙") else False
    tasks = [
        {
            "task_type": "现场巡查",
            "target_object_id": target_id,
            "owner_org": "区排水",
            "sla_minutes": 30,
            "required_evidence": ["定位", "照片"],
            "need_approval": False,
            "title": "巡查积水与排水口",
            "detail": f"对 {target_id} 巡查积水深度、排水口是否堵塞，回传证据。",
        },
        {
            "task_type": "封控准备",
            "target_object_id": target_id,
            "owner_org": "交警",
            "sla_minutes": 20,
            "required_evidence": ["定位", "照片"],
            "need_approval": need_approval,
            "title": "封控/绕行准备",
            "detail": "根据现场积水与通行情况，准备封控与绕行引导。",
        },
    ]

    return ChatResponse(
        summary=f"建议优先关注 {target_id}（风险{risk_level}），原因：{'; '.join(explain[:3])}",
        recommendations=[
            {"action": "优先处置", "target_id": target_id, "risk_level": risk_level, "reason": explain[:3], "preconditions": ["人审确认"] if need_approval else []}
        ],
        tasks=tasks,
        evidence=[{"type": "model", "ref": top.get("model_version"), "explain_factors": explain, "confidence": top.get("confidence")}],
        risk_controls={"need_approval_actions": ["封控准备"] if need_approval else [], "missing_inputs": ["现场积水深度核验"]},
    )


async def _call_deepseek(prompt: str) -> str:
    """
    演示级 DeepSeek 调用：如果没有 key 则不调用。
    这里不依赖 OpenAI SDK，直接 HTTP。
    """
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("no deepseek api key")
    url = f"{DEEPSEEK_BASE_URL}/v1/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    async with httpx.AsyncClient(timeout=25.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]


@app.get("/health")
def health():
    return {"ok": True, "deepseek_enabled": bool(DEEPSEEK_API_KEY)}


@app.post("/agent/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    演示级智能体：
    - 先调用工具 query_risk_topn 拿到 TopN
    - 无 DeepSeek：走规则式编排（可稳定演示闭环）
    - 有 DeepSeek：用大模型生成摘要（仍输出结构化 tasks，保持可控）
    """
    # 若没有 incident，自动创建
    incident_id = req.incident_id
    if not incident_id:
        inc = await api_post("/workflow/incidents", {"area_id": req.area_id, "title": "城市暴雨内涝处置事件（演示）"})
        incident_id = inc["incident_id"]

    topn = await query_risk_topn.ainvoke({"area_id": req.area_id, "n": 5})
    base = _rule_based_plan(topn, incident_id)

    # 可选：用 DeepSeek 生成更自然的 summary（保持结构化不变）
    if DEEPSEEK_API_KEY:
        prompt = (
            "你是应急指挥参谋，请根据以下TopN风险清单，生成一段不超过120字的研判摘要，"
            "必须提到最高风险点位、风险等级、主要原因（3条以内），不要编造证据。\n\n"
            f"TopN={topn}\n"
        )
        try:
            summary = await _call_deepseek(prompt)
            base.summary = summary.strip()
        except Exception:
            # 回退
            pass

    # 一句话：如果用户发“下发/派单”等，自动触发工作流
    if any(k in req.message for k in ["下发", "派单", "生成任务", "一键"]):
        pack = await create_task_pack.ainvoke({"incident_id": incident_id, "tasks": base.tasks})
        await trigger_workflow.ainvoke({"incident_id": incident_id, "task_pack": pack})
    return base


