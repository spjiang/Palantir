from __future__ import annotations

import math
import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from openai import OpenAI

from ...deps import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, pg, store

router = APIRouter(tags=["L3-RiskReasoningModels"])


def _require_pg():
    if not pg:
        raise HTTPException(500, "PG_DSN not configured")
    try:
        pg.connect()
    except Exception as e:
        raise HTTPException(500, f"Postgres not ready: {e}")


def _safe_float(v) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _risk_state_from_score(score: float) -> str:
    if score >= 0.85:
        return "高风险"
    if score >= 0.6:
        return "异常"
    if score >= 0.35:
        return "波动"
    return "正常"


def _extract_json_obj(text: str) -> dict[str, Any]:
    """
    兼容模型输出 ```json ...``` / 纯 JSON / 夹杂解释文本的情况，尽量提取出一个 JSON 对象。
    """
    t = (text or "").strip()
    if not t:
        raise ValueError("empty llm output")
    # 去掉 code fence
    if "```" in t:
        # 取第一个 fence 内的内容
        parts = t.split("```")
        # 形如: ["", "json\n{...}", ""] 或 ["", "{...}", ""]
        for p in parts:
            pp = p.strip()
            if not pp:
                continue
            if pp.lower().startswith("json"):
                pp = pp[4:].strip()
            if pp.startswith("{") and pp.endswith("}"):
                return json.loads(pp)
        # fallback：继续走下方花括号提取
        t = t.replace("```json", "").replace("```", "").strip()
    # 花括号截取（取第一段完整对象）
    l = t.find("{")
    r = t.rfind("}")
    if l >= 0 and r > l:
        return json.loads(t[l : r + 1])
    return json.loads(t)


def _llm_risk_infer(
    *,
    segment: dict[str, Any],
    latest: dict[str, Any],
    l1_alarms: list[dict[str, Any]],
    rules: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    使用 DeepSeek 做 L3 风险推理：
    - 输入：管段信息 + 最新读数/告警 + 草稿规则（结构化）
    - 输出：严格 JSON（risk_score/risk_state/matched_rules/generated_alarms/explain）
    没有 key 或调用失败则返回 None，由规则引擎兜底。
    """
    if not DEEPSEEK_API_KEY:
        return None
    try:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        # 提示词：要求只输出 JSON，避免模型啰嗦导致解析失败
        prompt = {
            "role": "user",
            "content": (
                "你是油气管网运维系统的 L3 风险推理模块。\n"
                "任务：根据【本体规则】+【最新传感器读数】+【L1 原始告警信号】推理出【预警/风险结论】。\n"
                "要求：只输出严格 JSON（不要输出任何解释文字、不要 markdown）。\n"
                "JSON Schema：\n"
                "{\n"
                '  "risk_score": number,  // 0~1\n'
                '  "risk_state": "正常|波动|异常|高风险",\n'
                '  "explain": string,\n'
                '  "matched_rules": [\n'
                "    {\n"
                '      "rule_id": string,\n'
                '      "name": string,\n'
                '      "metric": "pressure|flow",\n'
                '      "op": ">|<|>=|<=",\n'
                '      "threshold": number,\n'
                '      "weight": number,\n'
                '      "severity": "low|medium|high",\n'
                '      "current_value": number,\n'
                '      "reason": string\n'
                "    }\n"
                "  ],\n"
                '  "generated_alarms": [\n'
                "    {\n"
                '      "rule_id": string,\n'
                '      "alarm_type": string,\n'
                '      "severity": "low|medium|high",\n'
                '      "message": string,\n'
                '      "metric": "pressure|flow",\n'
                '      "op": ">|<|>=|<=",\n'
                '      "threshold": number,\n'
                '      "current_value": number\n'
                "    }\n"
                "  ]\n"
                "}\n\n"
                f"管段（segment）：{segment}\n\n"
                f"最新读数（latest）：{latest}\n\n"
                f"L1 原始告警（l1_alarms，最多10条）：{l1_alarms[:10]}\n\n"
                "本体规则（rules）：下列规则是唯一可用规则来源，你可以选择命中0~多条；如命中请把 rule_id 原样带回。\n"
                f"{rules}\n"
            ),
        }
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL or "deepseek-chat",
            messages=[prompt],
            temperature=0.1,
        )
        text = (resp.choices[0].message.content or "").strip()
        out = _extract_json_obj(text)
        return out if isinstance(out, dict) else None
    except Exception:
        return None

def _segment_node_id(segment_id: str) -> str:
    return f"ent-l1-{segment_id}"


def _sensor_node_id(sensor_id: str) -> str:
    return f"ent-l1-{sensor_id}"


def _state_node_id(state_name: str) -> str:
    # 让同名状态稳定复用（草稿内）
    key = state_name.strip()
    return f"ent-state-{abs(hash(key)) % (10**10)}"


def _ensure_l1_objects_in_draft(draft_id: str, segment: dict[str, Any], sensors: list[dict[str, Any]]) -> None:
    seg_ent = store.upsert_draft_entity_by_id(
        draft_id,
        _segment_node_id(segment["id"]),
        name=segment["name"],
        label="PipelineSegment",
        props={"source": "l1", "pg_id": segment["id"]},
    )

    # 语义关联：segment 实例 -> 本体“管段”类（behavior_model 初始化的那个）
    try:
        ents = store.list_draft_entities(draft_id, limit=5000)
        oc_name = (segment.get("ontology_class") or "管段").strip() or "管段"
        seg_class = next(
            (
                e
                for e in ents
                if (e.label or "") == "PipelineSegment"
                and (e.name or "") == oc_name
                and (e.props or {}).get("source") == "behavior_model"
            ),
            None,
        )
        if seg_class:
            store.upsert_draft_relation_by_id(
                draft_id,
                f"rel-inst-instance_of-{segment['id']}",
                src=seg_ent.id,
                dst=seg_class.id,
                rel_type="instance_of",
                props={"source": "l3"},
            )
    except Exception:
        # 语义边失败不影响主流程
        pass
    for s in sensors:
        sen_ent = store.upsert_draft_entity_by_id(
            draft_id,
            _sensor_node_id(s["id"]),
            name=s["name"],
            label="Sensor",
            props={"source": "l1", "pg_id": s["id"], "sensor_type": s.get("sensor_type")},
        )
        # has_sensor
        rel_id = f"rel-l1-has_sensor-{segment['id']}-{s['id']}"
        store.upsert_draft_relation_by_id(
            draft_id,
            rel_id,
            src=seg_ent.id,
            dst=sen_ent.id,
            rel_type="has_sensor",
            props={"source": "l1"},
        )


def _extract_structured_rules_from_draft(draft_id: str, *, class_name: str = "管段") -> list[dict[str, Any]]:
    """
    约定：在 L2 里（手工或抽取后编辑）把 Rule.props 写成结构化形式：
      {
        "metric": "pressure" | "flow",
        "op": ">" | "<" | ">=" | "<=",
        "threshold": 8.5,
        "weight": 0.5,
        "severity": "high" | "medium" | "low"
      }
    若没有这些字段，L3 会退化为仅基于 L1 alarms 的启发式评分。
    """
    ents = store.list_draft_entities(draft_id, limit=5000)
    rels = store.list_draft_relations(draft_id, limit=20000)

    # 若存在 “本体类” 节点，则只选择“涉及 -> 本体类”的规则（更贴近你的“按本体关联取规则”）
    cls = (class_name or "管段").strip() or "管段"
    seg_class_id = None
    for e in ents:
        if (e.label or "") == "PipelineSegment" and (e.name or "") == cls and (e.props or {}).get("source") == "behavior_model":
            seg_class_id = e.id
            break
    involved_rule_ids: set[str] | None = None
    if seg_class_id:
        involved_rule_ids = {r.src for r in rels if (r.type or "") == "涉及" and r.dst == seg_class_id}

    rules = []
    for e in ents:
        if (e.label or "") != "Rule":
            continue
        if involved_rule_ids is not None and e.id not in involved_rule_ids:
            continue
        p = e.props or {}
        metric = p.get("metric")
        op = p.get("op")
        thr = _safe_float(p.get("threshold"))
        if metric in {"pressure", "flow"} and op in {">", "<", ">=", "<="} and thr is not None:
            rules.append(
                {
                    "id": e.id,
                    "name": e.name,
                    "metric": metric,
                    "op": op,
                    "threshold": thr,
                    "weight": _safe_float(p.get("weight")) or 0.5,
                    "severity": p.get("severity") or "medium",
                }
            )
    return rules


def _rule_to_behaviors(draft_id: str) -> dict[str, list[dict[str, Any]]]:
    ents = store.list_draft_entities(draft_id, limit=5000)
    rels = store.list_draft_relations(draft_id, limit=20000)
    id_to_ent = {e.id: e for e in ents}
    out: dict[str, list[dict[str, Any]]] = {}
    for r in rels:
        if (r.type or "") != "约束":
            continue
        rule = id_to_ent.get(r.src)
        beh = id_to_ent.get(r.dst)
        if not rule or not beh:
            continue
        if (rule.label or "") != "Rule" or (beh.label or "") != "Behavior":
            continue
        out.setdefault(rule.id, []).append({"id": beh.id, "name": beh.name, "props": beh.props or {}})
    return out


def _apply_rules(rules: list[dict[str, Any]], latest: dict[str, float]) -> tuple[float, list[str]]:
    if not rules:
        return 0.0, []
    score = 0.0
    reasons: list[str] = []
    for r in rules:
        v = latest.get(r["metric"])
        if v is None:
            continue
        ok = False
        if r["op"] == ">" and v > r["threshold"]:
            ok = True
        elif r["op"] == "<" and v < r["threshold"]:
            ok = True
        elif r["op"] == ">=" and v >= r["threshold"]:
            ok = True
        elif r["op"] == "<=" and v <= r["threshold"]:
            ok = True
        if ok:
            score += float(r["weight"])
            reasons.append(f"{r['name'] or r['id']}: {r['metric']} {r['op']} {r['threshold']}（当前 {v}）")
    return min(1.0, max(0.0, score)), reasons


def _is_l3_alarm(a: dict[str, Any]) -> bool:
    raw = a.get("raw")
    if isinstance(raw, dict):
        return (raw.get("source") or "").lower() == "l3"
    # raw 可能是字符串/None，保守认为不是 l3
    return False


def _ensure_l3_alarm(
    *,
    segment_id: str,
    sensor_id: str | None,
    reading_id: str | None,
    rule: dict[str, Any],
    message: str,
) -> str:
    """
    L3 生成“预警/告警结论”：
    - 写入 PG alarms（source=l3, rule_id）
    - 幂等去重：同一 reading_id + rule_id 只写一次
    """
    rule_id = str(rule.get("id") or "")
    if reading_id and rule_id:
        exists = pg.fetchone("SELECT id FROM alarms WHERE reading_id=%s AND raw->>'rule_id'=%s LIMIT 1;", (reading_id, rule_id))
        if exists and exists.get("id"):
            return exists["id"]
    a = pg.create_alarm(
        alarm_type=rule.get("name") or "规则命中",
        severity=(rule.get("severity") or "medium"),
        message=message,
        sensor_id=sensor_id,
        segment_id=segment_id,
        reading_id=reading_id,
        raw={"source": "l3", "rule_id": rule_id, "metric": rule.get("metric"), "op": rule.get("op"), "threshold": rule.get("threshold")},
    )
    return a["id"]


class RiskEvaluateRequest(BaseModel):
    draft_id: str | None = Field(default=None, description="可选：使用草稿本体规则/行为（draft_id）")
    segment_id: str = Field(..., description="L1 管段ID（seg-xxx）")
    write_back_to_draft: bool = Field(default=True, description="是否把风险状态回写到 L2 草稿图谱")
    reasoning_mode: str = Field(default="auto", description="auto|rule_engine|deepseek；auto=有 DEEPSEEK key 则 deepseek 否则 rule_engine")


@router.get("/risk/topn")
def risk_topn(
    draft_id: str | None = None,
    limit: int = 10,
    include_empty: bool = False,
    reasoning_mode: str = "rule_engine",
):
    """
    TopN 风险：按 L1 感知数据（读数/原始告警）+（可选）L2 结构化规则 对管段评分。
    - 默认 include_empty=false：没有任何读数/告警的管段不返回（清空后列表会变空）
    - include_empty=true：即使没有数据也返回（用于展示全量管段概览）
    """
    _require_pg()
    mode = (reasoning_mode or "rule_engine").strip().lower()
    if mode == "deepseek" and not DEEPSEEK_API_KEY:
        raise HTTPException(400, "reasoning_mode=deepseek but DEEPSEEK_API_KEY is empty")
    segs = pg.list_segments()
    items = []
    for seg in segs:
        sensors = pg.list_sensors(segment_id=seg["id"])
        alarms_all = pg.list_alarms(segment_id=seg["id"], limit=200)
        # L1 输入告警：排除 L3 生成的“告警结论”，避免反馈回路
        alarms = [a for a in alarms_all if not _is_l3_alarm(a)]
        readings = pg.list_readings(segment_id=seg["id"], limit=20)
        if not include_empty and not readings and not alarms:
            continue

        latest_pressure = None
        latest_flow = None
        for r in readings:
            if latest_pressure is None and r.get("pressure") is not None:
                latest_pressure = _safe_float(r.get("pressure"))
            if latest_flow is None and r.get("flow") is not None:
                latest_flow = _safe_float(r.get("flow"))
        base = 0.0
        # alarms 启发：high=0.25, medium=0.15, low=0.08
        for a in alarms[:10]:
            sev = (a.get("severity") or "").lower()
            base += 0.25 if sev == "high" else 0.15 if sev == "medium" else 0.08
        base = min(0.8, base)

        rules = _extract_structured_rules_from_draft(draft_id, class_name=(seg.get("ontology_class") or "管段")) if draft_id else []
        # 先用“规则引擎”做一个便宜的预排序分数（用于 deepseek 时限制调用次数）
        rule_score, reasons = _apply_rules(rules, {"pressure": latest_pressure, "flow": latest_flow})
        pre_score = min(1.0, base + rule_score)
        pre_state = _risk_state_from_score(pre_score)
        pre_explain = "；".join(reasons) if reasons else ("基于近10条告警启发式评分" if alarms else "暂无告警/规则命中")

        items.append(
            {
                "segment_id": seg["id"],
                "segment_name": seg["name"],
                "latitude": seg.get("latitude"),
                "longitude": seg.get("longitude"),
                "sensor_count": len(sensors),
                "alarm_count": len(alarms),
                "latest_pressure": latest_pressure,
                "latest_flow": latest_flow,
                "risk_score": round(pre_score, 3),
                "risk_state": pre_state,
                "explain": pre_explain,
                "_draft_rules_used": rules,
            }
        )

    items.sort(key=lambda x: x["risk_score"], reverse=True)
    # deepseek：只对预排序 TopK 进行大模型推理，避免“全量管段逐个调用”带来成本与延迟
    if mode == "deepseek":
        top_k = max(1, min(int(limit or 10), 10))
        for it in items[:top_k]:
            seg_id = it.get("segment_id")
            seg = next((s for s in segs if s.get("id") == seg_id), None)
            if not seg:
                continue
            llm = _llm_risk_infer(
                segment=seg,
                latest={"pressure": it.get("latest_pressure"), "flow": it.get("latest_flow")},
                l1_alarms=pg.list_alarms(segment_id=seg_id, limit=50)[:10],
                rules=it.get("_draft_rules_used") or [],
            )
            if not llm:
                continue
            score = float(llm.get("risk_score") or it.get("risk_score") or 0.0)
            score = max(0.0, min(1.0, score))
            state = (llm.get("risk_state") or "").strip() or _risk_state_from_score(score)
            if state not in {"正常", "波动", "异常", "高风险"}:
                state = _risk_state_from_score(score)
            it["risk_score"] = round(score, 3)
            it["risk_state"] = state
            it["explain"] = (llm.get("explain") or "").strip() or "DeepSeek 推理"
        items.sort(key=lambda x: x["risk_score"], reverse=True)
    for it in items:
        if "_draft_rules_used" in it:
            del it["_draft_rules_used"]
    return {"items": items[: max(1, min(limit, 100))]}


@router.post("/risk/evaluate")
def risk_evaluate(payload: RiskEvaluateRequest):
    """
    评估单个管段风险，并（可选）回写到 L2 草稿图谱：
    - 创建/更新 PipelineSegment/Sensor 节点（来源 L1）
    - 维护 has_sensor
    - 维护 in_state
    同时写入 Postgres risk_events，供 L6 追溯。
    """
    _require_pg()
    seg = pg.fetchone("SELECT * FROM pipeline_segments WHERE id=%s;", (payload.segment_id,))
    if not seg:
        raise HTTPException(404, "segment not found")
    sensors = pg.list_sensors(segment_id=payload.segment_id)
    # L1 原始告警（若有）；L3 会在本次评估中生成“告警结论”并写入同一表
    alarms_all = pg.list_alarms(segment_id=payload.segment_id, limit=200)
    # L1 输入告警：排除 L3 生成的“告警结论”，避免反馈回路
    alarms = [a for a in alarms_all if not _is_l3_alarm(a)]
    readings = pg.list_readings(segment_id=payload.segment_id, limit=50)

    latest_pressure = None
    latest_flow = None
    latest_reading_id_by_metric: dict[str, str | None] = {"pressure": None, "flow": None}
    latest_sensor_id_by_metric: dict[str, str | None] = {"pressure": None, "flow": None}
    for r in readings:
        if latest_pressure is None and r.get("pressure") is not None:
            latest_pressure = _safe_float(r.get("pressure"))
            latest_reading_id_by_metric["pressure"] = r.get("id")
            latest_sensor_id_by_metric["pressure"] = r.get("sensor_id")
        if latest_flow is None and r.get("flow") is not None:
            latest_flow = _safe_float(r.get("flow"))
            latest_reading_id_by_metric["flow"] = r.get("id")
            latest_sensor_id_by_metric["flow"] = r.get("sensor_id")

    rules = _extract_structured_rules_from_draft(payload.draft_id, class_name=(seg.get("ontology_class") or "管段")) if payload.draft_id else []
    rule2behs = _rule_to_behaviors(payload.draft_id) if payload.draft_id else {}
    base = 0.0
    for a in alarms[:10]:
        sev = (a.get("severity") or "").lower()
        base += 0.25 if sev == "high" else 0.15 if sev == "medium" else 0.08
    base = min(0.8, base)
    # 规则引擎（兜底）/ DeepSeek（优先）
    requested_mode = (payload.reasoning_mode or "auto").strip().lower()
    mode = requested_mode
    if requested_mode == "auto":
        mode = "deepseek" if DEEPSEEK_API_KEY else "rule_engine"

    llm_out: dict[str, Any] | None = None
    if mode == "deepseek":
        llm_out = _llm_risk_infer(
            segment=seg,
            latest={
                "pressure": latest_pressure,
                "flow": latest_flow,
                "latest_reading_id_by_metric": latest_reading_id_by_metric,
                "latest_sensor_id_by_metric": latest_sensor_id_by_metric,
            },
            l1_alarms=alarms[:10],
            rules=rules,
        )
        if not llm_out:
            mode = "rule_engine"

    if mode == "deepseek" and llm_out:
        score = float(llm_out.get("risk_score") or 0.0)
        score = max(0.0, min(1.0, score))
        state = (llm_out.get("risk_state") or "").strip() or _risk_state_from_score(score)
        if state not in {"正常", "波动", "异常", "高风险"}:
            state = _risk_state_from_score(score)
        explain = (llm_out.get("explain") or "").strip() or "DeepSeek 推理"
    else:
        # 规则评分 + 规则命中原因
        rule_score, reasons = _apply_rules(rules, {"pressure": latest_pressure, "flow": latest_flow})
        score = min(1.0, base + rule_score)
        state = _risk_state_from_score(score)
        explain = "；".join(reasons) if reasons else ("基于近10条告警启发式评分" if alarms else "暂无告警/规则命中")

    # L3 生成“预警/告警结论”（写入 alarms），只在规则命中时生成
    derived_alarm_ids: list[str] = []
    matched_rules: list[dict[str, Any]] = []
    # 规则命中/预警结论：DeepSeek 优先，否则规则引擎
    if mode == "deepseek" and llm_out:
        # matched_rules
        mr = llm_out.get("matched_rules") or []
        if isinstance(mr, list):
            for it in mr:
                if not isinstance(it, dict):
                    continue
                rid = str(it.get("rule_id") or "").strip()
                metric = it.get("metric")
                current_value = _safe_float(it.get("current_value"))
                # 绑定 Behavior（供 L4 可视化）
                matched_rules.append(
                    {
                        "id": rid,
                        "name": it.get("name"),
                        "metric": metric,
                        "op": it.get("op"),
                        "threshold": _safe_float(it.get("threshold")),
                        "weight": _safe_float(it.get("weight")) or 0.5,
                        "severity": it.get("severity") or "medium",
                        "current_value": current_value,
                        "reason": it.get("reason"),
                        "behaviors": rule2behs.get(rid, []),
                    }
                )
        # generated_alarms -> 写入 PG alarms（source=l3）
        ga = llm_out.get("generated_alarms") or []
        if isinstance(ga, list):
            for a in ga:
                if not isinstance(a, dict):
                    continue
                rid = str(a.get("rule_id") or "").strip()
                metric = a.get("metric")
                if metric not in {"pressure", "flow"}:
                    metric = None
                reading_id = latest_reading_id_by_metric.get(metric) if metric else None
                sensor_id = latest_sensor_id_by_metric.get(metric) if metric else None
                # 从 rules 列表里找到 rule（保证 _ensure_l3_alarm raw 字段一致）
                rule_obj = next((r for r in rules if str(r.get("id") or "") == rid), None) or {
                    "id": rid,
                    "name": a.get("alarm_type") or "规则命中",
                    "metric": a.get("metric"),
                    "op": a.get("op"),
                    "threshold": a.get("threshold"),
                    "severity": a.get("severity") or "medium",
                }
                msg = (a.get("message") or "").strip() or f"{rule_obj.get('name')}: 命中规则（DeepSeek）"
                try:
                    aid = _ensure_l3_alarm(segment_id=seg["id"], sensor_id=sensor_id, reading_id=reading_id, rule=rule_obj, message=msg)
                    derived_alarm_ids.append(aid)
                except Exception:
                    pass
    else:
        if rules:
            for r in rules:
                metric = r.get("metric")
                if metric not in {"pressure", "flow"}:
                    continue
                v = {"pressure": latest_pressure, "flow": latest_flow}.get(metric)
                if v is None:
                    continue
                op = r.get("op")
                thr = r.get("threshold")
                hit = False
                if op == ">" and v > thr:
                    hit = True
                elif op == "<" and v < thr:
                    hit = True
                elif op == ">=" and v >= thr:
                    hit = True
                elif op == "<=" and v <= thr:
                    hit = True
                if hit:
                    matched_rules.append({**r, "current_value": v, "behaviors": rule2behs.get(str(r.get("id") or ""), [])})
                    rid = latest_reading_id_by_metric.get(metric)
                    sid = latest_sensor_id_by_metric.get(metric)
                    msg = f"{r.get('name') or r.get('id')}: {metric} {op} {thr}（当前 {v}）"
                    try:
                        aid = _ensure_l3_alarm(segment_id=seg["id"], sensor_id=sid, reading_id=rid, rule=r, message=msg)
                        derived_alarm_ids.append(aid)
                    except Exception:
                        # 告警结论写入失败不影响风险结论主体
                        pass

    # 写入风险事件（L6 追溯）
    ev = pg.add_risk_event(
        draft_id=payload.draft_id,
        segment_id=seg["id"],
        segment_name=seg["name"],
        risk_score=float(score),
        risk_state=state,
        explain=explain,
        evidence={
            "alarms": list({*(a.get("id") for a in alarms[:20] if a.get("id")), *derived_alarm_ids}),
            "readings": [r.get("id") for r in readings[:20]],
        },
    )

    # 回写草稿图谱（让 L2/L4 可视化“当前状态”）
    if payload.draft_id and payload.write_back_to_draft:
        try:
            _ensure_l1_objects_in_draft(payload.draft_id, seg, sensors)
            st_id = _state_node_id(state)
            st_ent = store.upsert_draft_entity_by_id(
                payload.draft_id,
                st_id,
                name=state,
                label="RiskState",
                props={"source": "l3"},
            )
            rel_id = f"rel-l3-in_state-{seg['id']}"
            store.upsert_draft_relation_by_id(
                payload.draft_id,
                rel_id,
                src=_segment_node_id(seg["id"]),
                dst=st_ent.id,
                rel_type="in_state",
                props={"source": "l3", "risk_score": round(score, 3), "risk_event_id": ev["id"]},
            )
        except Exception as e:
            raise HTTPException(500, f"risk evaluated but failed to write back to draft graph: {e}")

    return {
        "reasoning_mode": mode,
        "requested_mode": requested_mode,
        "segment_id": seg["id"],
        "segment_name": seg["name"],
        "risk_score": round(score, 3),
        "risk_state": state,
        "explain": explain,
        "latest_pressure": latest_pressure,
        "latest_flow": latest_flow,
        "alarm_count": len(alarms),  # L1 输入告警数量（不含 L3 生成）
        "sensor_count": len(sensors),
        "draft_rules_used": rules,
        "matched_rules": matched_rules,
        "derived_alarm_ids": derived_alarm_ids,
        "derived_alarms": [a for a in (pg.list_alarms(segment_id=seg["id"], limit=400) or []) if a.get("id") in set(derived_alarm_ids)],
        "risk_event": ev,
    }
