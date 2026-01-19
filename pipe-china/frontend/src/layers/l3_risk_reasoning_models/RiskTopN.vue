<template>
  <div class="card">
    <h2>L3 · 风险 TopN</h2>
    <p>
      基于 L1 感知数据（读数/原始告警）+ L2 草稿本体（行为/规则/状态）进行风险推理。
      页面会明确展示：<b>读取了哪些草稿建模数据</b>，以及 <b>命中哪些规则并生成哪些预警</b>。
    </p>

    <div class="row">
      <div class="card subcard">
        <h3>参数</h3>
        <label>草稿 draft_id（可选）</label>
        <input v-model="draftId" class="mono" placeholder="draft-xxxx（留空则仅用 L1 告警启发式评分）" />
        <label style="margin-top: 10px">TopN 推理模式</label>
        <select v-model="topnReasoningMode">
          <option value="rule_engine">规则引擎（快速/稳定，默认）</option>
          <option value="deepseek">DeepSeek（仅对 TopK 调用，成本更高）</option>
        </select>
        <div class="btnrow">
          <button class="btn secondary" @click="loadDraftIdFromSession">读取当前 draftId</button>
          <button class="btn" :disabled="loading" @click="fetchTopN">刷新 TopN</button>
          <button class="btn danger" :disabled="loading" @click="purgeTopNData">清空 TopN 数据</button>
        </div>
      </div>

      <div class="card subcard">
        <h3>单管段评估（回写草稿状态）</h3>
        <label>segment_id（L1）</label>
        <input v-model="segmentId" class="mono" placeholder="seg-xxx" />
        <label style="margin-top: 10px">评估推理模式</label>
        <select v-model="evalReasoningMode">
          <option value="auto">auto（有 DeepSeek key 则用模型，否则规则引擎）</option>
          <option value="deepseek">DeepSeek（大模型推理）</option>
          <option value="rule_engine">规则引擎（确定性兜底）</option>
        </select>
        <div class="btnrow">
          <button class="btn" :disabled="loading || !segmentId" @click="evaluateOne">评估并回写</button>
          <button class="btn secondary" :disabled="loading || !segmentId" @click="agentDecide">L4 生成任务</button>
        </div>
        <div v-if="evaluateResp" class="card subcard" style="margin-top: 10px">
          <h4>推理结果</h4>
          <div class="kv">
            <div class="k">reasoning_mode</div><div class="v mono">{{ evaluateResp.reasoning_mode || "-" }}</div>
            <div class="k">risk_state</div><div class="v"><span class="pill" :class="`st-${evaluateResp.risk_state}`">{{ evaluateResp.risk_state }}</span></div>
            <div class="k">risk_score</div><div class="v mono">{{ evaluateResp.risk_score }}</div>
            <div class="k">explain</div><div class="v">{{ evaluateResp.explain }}</div>
          </div>

          <h4 style="margin-top: 10px">命中规则（来自草稿）</h4>
          <div v-if="(evaluateResp.matched_rules || []).length === 0" class="muted">暂无规则命中</div>
          <div v-else class="list">
            <div v-for="r in evaluateResp.matched_rules" :key="r.id" class="rowitem">
              <div class="row-title">{{ r.name }}</div>
              <div class="row-sub mono">{{ r.metric }} {{ r.op }} {{ r.threshold }}（当前 {{ r.current_value }}） weight={{ r.weight }} severity={{ r.severity }}</div>
            </div>
          </div>

          <h4 style="margin-top: 10px">生成预警（告警结论，L3 输出）</h4>
          <div v-if="(evaluateResp.derived_alarms || []).length === 0" class="muted">未生成预警</div>
          <table v-else class="tbl" style="margin-top: 8px">
            <thead>
              <tr>
                <th>时间</th>
                <th>类型</th>
                <th>级别</th>
                <th>消息</th>
                <th>操作</th>
                <th>ID</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="a in evaluateResp.derived_alarms" :key="a.id">
                <td class="mono small">{{ fmt(a.ts) }}</td>
                <td>{{ a.alarm_type }}</td>
                <td class="mono">{{ a.severity }}</td>
                <td>{{ a.message }}</td>
                <td>
                  <button class="btn mini secondary" :disabled="loading || !draftId" @click="pushAlertToL4(a.id)">推送到 L4 生成任务</button>
                </td>
                <td class="mono small">{{ a.id }}</td>
              </tr>
            </tbody>
          </table>

          <details style="margin-top: 10px">
            <summary class="mono small">查看原始响应 JSON</summary>
            <div class="mono small pre">{{ JSON.stringify(evaluateResp, null, 2) }}</div>
          </details>
        </div>
      </div>
    </div>

    <div class="card subcard">
      <h3>从草稿 draft_id 读取到的“行为建模数据”</h3>
      <div v-if="!draftId" class="muted">draft_id 为空：不读取草稿本体（规则/行为/状态），仅做退化版评估。</div>
      <div v-else-if="draftLoading" class="muted">加载中...</div>
      <div v-else>
        <div class="kv">
          <div class="k">Behaviors</div><div class="v mono">{{ draftBehaviors.length }}</div>
          <div class="k">Rules</div><div class="v mono">{{ draftRules.length }}</div>
          <div class="k">States</div><div class="v mono">{{ draftStates.length }}</div>
        </div>
        <div class="grid3" style="margin-top: 10px">
          <div class="card subcard">
            <h4>规则（Rule.props 可执行字段）</h4>
            <div v-if="draftRules.length === 0" class="muted">暂无规则</div>
            <div v-else class="list">
              <div v-for="r in draftRules" :key="r.id" class="rowitem">
                <div class="row-title">{{ r.name }}</div>
                <div class="row-sub mono">
                  metric={{ r.props?.metric }} op={{ r.props?.op }} threshold={{ r.props?.threshold }} weight={{ r.props?.weight }} severity={{ r.props?.severity }}
                </div>
              </div>
            </div>
          </div>
          <div class="card subcard">
            <h4>行为（Behavior）</h4>
            <div v-if="draftBehaviors.length === 0" class="muted">暂无行为</div>
            <div v-else class="list">
              <div v-for="b in draftBehaviors" :key="b.id" class="rowitem">
                <div class="row-title">{{ b.name }}</div>
                <div class="row-sub">{{ b.props?.effects || b.props?.explain || "" }}</div>
              </div>
            </div>
          </div>
          <div class="card subcard">
            <h4>状态（RiskState/State）</h4>
            <div v-if="draftStates.length === 0" class="muted">暂无状态</div>
            <div v-else class="list">
              <div v-for="s in draftStates" :key="s.id" class="rowitem">
                <div class="row-title">{{ s.name }}</div>
                <div class="row-sub mono">{{ s.label }} · {{ s.id }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="card subcard">
      <h3>TopN 列表</h3>
      <div class="btnrow" style="margin-top: 8px">
        <button class="btn secondary" :disabled="loading" @click="topnView = 'segments'">管段风险 TopN</button>
        <button class="btn secondary" :disabled="loading" @click="topnView = 'alerts'">预警 TopN（L3 产出）</button>
      </div>

      <div v-if="topnView === 'alerts'" style="margin-top: 10px">
        <div class="muted">说明：这里展示的是 <b>L3 推理生成的告警结论</b>（raw.source=l3）。要看到数据，请先对管段执行一次“评估并回写”。</div>
        <div v-if="alertItems.length === 0" class="muted" style="margin-top: 10px">暂无预警（L3 还未生成告警结论）</div>
        <table v-else class="tbl">
          <thead>
            <tr>
              <th>时间</th>
              <th>管段</th>
              <th>传感器</th>
              <th>类型</th>
              <th>级别</th>
              <th>消息</th>
              <th>操作</th>
              <th>ID</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in alertItems" :key="a.id" class="clickable" @click="selectSegmentFromAlert(a)">
              <td class="mono small">{{ fmt(a.ts) }}</td>
              <td>{{ a.segment_name || a.segment_id || "-" }}</td>
              <td>{{ a.sensor_name || a.sensor_id || "-" }}</td>
              <td>{{ a.alarm_type }}</td>
              <td class="mono">{{ a.severity }}</td>
              <td>{{ a.message }}</td>
              <td>
                <button class="btn mini secondary" :disabled="loading || !draftId" @click="pushAlertToL4(a.id)">推送到 L4</button>
              </td>
              <td class="mono small">{{ a.id }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="items.length === 0" class="muted">暂无数据（先去 L1 写入/模拟一些读数与告警）</div>
      <table v-else-if="topnView === 'segments'" class="tbl">
        <thead>
          <tr>
            <th>管段</th>
            <th>score</th>
            <th>state</th>
            <th>传感器</th>
            <th>告警</th>
            <th>latest(p/f)</th>
            <th>latest 传感器(p/f)</th>
            <th>解释</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="it in items"
            :key="it.segment_id"
            @click="selectSegmentFromTopN(it)"
            class="clickable"
          >
            <td>{{ it.segment_name }} <span class="mono small">({{ it.segment_id }})</span></td>
            <td class="mono">{{ it.risk_score }}</td>
            <td><span class="pill" :class="`st-${it.risk_state}`">{{ it.risk_state }}</span></td>
            <td class="mono">{{ it.sensor_count }}</td>
            <td class="mono">{{ it.alarm_count }}</td>
            <td class="mono">{{ it.latest_pressure ?? "-" }} / {{ it.latest_flow ?? "-" }}</td>
            <td class="mono small">{{ it.latest_pressure_sensor_name || "-" }} / {{ it.latest_flow_sensor_name || "-" }}</td>
            <td>{{ it.explain }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from "vue";

const props = defineProps({
  apiBase: { type: String, required: true },
});

const loading = ref(false);
const items = ref([]);
const alertItems = ref([]);
const draftId = ref("");
const segmentId = ref("");
const evaluateResp = ref(null);
const topnReasoningMode = ref("deepseek");
const evalReasoningMode = ref("deepseek");
const topnView = ref("segments"); // segments | alerts
function selectSegmentFromTopN(it) {
  segmentId.value = it.segment_id;
  // 选中管段后，自动切到“预警 TopN”并按该管段筛选，方便互相查看
  topnView.value = "alerts";
  fetchAlertTopN();
}

function selectSegmentFromAlert(a) {
  if (a?.segment_id) segmentId.value = a.segment_id;
  topnView.value = "segments";
}
const draftLoading = ref(false);
const draftEntities = ref([]);
const draftRules = ref([]);
const draftBehaviors = ref([]);
const draftStates = ref([]);
const l4Resp = ref(null);

function fmt(ts) {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts || "";
  }
}

async function purgeTopNData() {
  const seg = (segmentId.value || "").trim();
  const msg = seg
    ? "确认清空【该管段】的感知数据(读数)与预警数据(告警/风险事件)吗？\n这会导致 TopN 立刻变空/归零。\n注意：不会删除管段/传感器。"
    : "segment_id 为空，将清空【全局】感知数据(读数)与预警数据(告警/风险事件)。\n这会导致 TopN 立刻变空/归零。\n确认继续吗？";
  if (!confirm(msg)) return;
  loading.value = true;
  try {
    const qs = new URLSearchParams({ confirm: "YES" });
    if (seg) qs.set("segment_id", seg);
    await api(`/l1/purge?${qs.toString()}`, { method: "POST" });
    evaluateResp.value = null;
    await fetchTopN();
  } catch (e) {
    console.error(e);
    alert(`清空失败：${e.message}`);
  } finally {
    loading.value = false;
  }
}

function api(path, init) {
  return fetch(`${props.apiBase}${path}`, init).then(async (r) => {
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  });
}

function loadDraftIdFromSession() {
  try {
    draftId.value = sessionStorage.getItem("pipe-china:draftId") || "";
    topnReasoningMode.value = sessionStorage.getItem("pipe-china:l3TopnReasoningMode") || "deepseek";
    evalReasoningMode.value = sessionStorage.getItem("pipe-china:l3EvalReasoningMode") || "deepseek";
  } catch {
    draftId.value = "";
    topnReasoningMode.value = "deepseek";
    evalReasoningMode.value = "deepseek";
  }
}

watch(
  () => topnReasoningMode.value,
  () => {
    try {
      sessionStorage.setItem("pipe-china:l3TopnReasoningMode", topnReasoningMode.value || "deepseek");
    } catch {
      // ignore
    }
  }
);

watch(
  () => evalReasoningMode.value,
  () => {
    try {
      sessionStorage.setItem("pipe-china:l3EvalReasoningMode", evalReasoningMode.value || "deepseek");
    } catch {
      // ignore
    }
  }
);

async function fetchTopN() {
  loading.value = true;
  try {
    const qs = new URLSearchParams();
    if (draftId.value) qs.set("draft_id", draftId.value);
    if (topnReasoningMode.value) qs.set("reasoning_mode", topnReasoningMode.value);
    const q = qs.toString() ? `?${qs.toString()}` : "";
    const data = await api(`/risk/topn${q}`);
    items.value = data.items || [];
    if (topnView.value === "alerts") {
      await fetchAlertTopN();
    }
  } catch (e) {
    console.error(e);
    alert(`获取 TopN 失败：${e.message}`);
  } finally {
    loading.value = false;
  }
}

async function fetchAlertTopN() {
  try {
    const seg = (segmentId.value || "").trim();
    const qs = new URLSearchParams();
    qs.set("limit", "20");
    if (seg) qs.set("segment_id", seg);
    const data = await api(`/risk/alerts/topn?${qs.toString()}`);
    alertItems.value = data.items || [];
  } catch (e) {
    console.error(e);
    alert(`获取预警 TopN 失败：${e.message}`);
  }
}

async function fetchDraftModel() {
  if (!draftId.value) {
    draftEntities.value = [];
    draftRules.value = [];
    draftBehaviors.value = [];
    draftStates.value = [];
    return;
  }
  draftLoading.value = true;
  try {
    const en = await api(`/ontology/drafts/${encodeURIComponent(draftId.value)}/entities`);
    draftEntities.value = en || [];
    draftRules.value = (en || []).filter((x) => x.label === "Rule");
    draftBehaviors.value = (en || []).filter((x) => x.label === "Behavior");
    draftStates.value = (en || []).filter((x) => x.label === "RiskState" || x.label === "State");
  } catch (e) {
    console.error(e);
    alert(`读取草稿本体失败：${e.message}`);
  } finally {
    draftLoading.value = false;
  }
}

async function evaluateOne() {
  loading.value = true;
  try {
    const data = await api("/risk/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        draft_id: draftId.value || null,
        segment_id: segmentId.value,
        write_back_to_draft: true,
        reasoning_mode: evalReasoningMode.value || "auto",
      }),
    });
    evaluateResp.value = data;
    // 同步更新草稿模型展示（有时用户刚初始化）
    await fetchDraftModel();
    await fetchTopN();
    // 评估后往往会生成 L3 告警结论，顺便刷新预警 TopN
    await fetchAlertTopN();
  } catch (e) {
    console.error(e);
    alert(`评估失败：${e.message}`);
  } finally {
    loading.value = false;
  }
}

async function agentDecide() {
  if (!draftId.value) {
    alert("请先填写/读取 draftId（L4 需要在草稿图谱中写回任务 targets）。");
    return;
  }
  loading.value = true;
  try {
    const data = await api("/agent/decide", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ draft_id: draftId.value, segment_id: segmentId.value, min_risk_state: "异常", task_type: "巡检" }),
    });
    evaluateResp.value = data;
    alert(data.created ? "任务已生成（可到 L5 查看）" : (data.reason || "未生成任务"));
  } catch (e) {
    console.error(e);
    alert(`L4 决策失败：${e.message}`);
  } finally {
    loading.value = false;
  }
}

async function pushAlertToL4(alarmId) {
  if (!draftId.value) {
    alert("请先填写/读取 draftId（用于查询行为本体并回写任务到草稿图谱）。");
    return;
  }
  loading.value = true;
  try {
    const data = await api("/agent/decide_from_alert", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ draft_id: draftId.value, alarm_id: alarmId, task_type: "巡检" }),
    });
    l4Resp.value = data;
    alert("已推送到 L4，并生成任务（去 L5 查看）");
  } catch (e) {
    console.error(e);
    alert(`推送到 L4 失败：${e.message}`);
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadDraftIdFromSession();
  fetchTopN();
  fetchDraftModel();
  fetchAlertTopN();
});

watch(
  () => draftId.value,
  () => {
    fetchDraftModel();
    fetchTopN();
  }
);
</script>

<style scoped>
.row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
@media (max-width: 980px) {
  .row {
    grid-template-columns: 1fr;
  }
}
.subcard {
  margin-top: 14px;
}
.btnrow {
  display: flex;
  gap: 10px;
  margin-top: 10px;
}
.btn {
  padding: 9px 12px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(14, 165, 233, 0.22);
  color: rgba(226, 232, 240, 0.95);
  cursor: pointer;
  white-space: nowrap;
}
.btn.secondary {
  background: rgba(148, 163, 184, 0.12);
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
input {
  width: 100%;
  background: rgba(15, 23, 42, 0.55);
  border: 1px solid rgba(148, 163, 184, 0.22);
  color: rgba(226, 232, 240, 0.92);
  border-radius: 10px;
  padding: 10px 12px;
  outline: none;
}
.tbl {
  width: 100%;
  border-collapse: collapse;
  margin-top: 10px;
}
.tbl th,
.tbl td {
  border-bottom: 1px solid rgba(148, 163, 184, 0.14);
  padding: 8px 6px;
  text-align: left;
  font-size: 13px;
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}
.small {
  font-size: 12px;
}
.muted {
  color: rgba(226, 232, 240, 0.65);
}
.pill {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(148, 163, 184, 0.12);
  font-size: 12px;
  font-weight: 700;
}
.pill.st-高风险 {
  border-color: rgba(239, 68, 68, 0.45);
  background: rgba(239, 68, 68, 0.16);
}
.pill.st-异常 {
  border-color: rgba(245, 158, 11, 0.45);
  background: rgba(245, 158, 11, 0.14);
}
.pill.st-波动 {
  border-color: rgba(56, 189, 248, 0.45);
  background: rgba(56, 189, 248, 0.14);
}
.pill.st-正常 {
  border-color: rgba(34, 197, 94, 0.45);
  background: rgba(34, 197, 94, 0.14);
}
.pre {
  white-space: pre-wrap;
  background: rgba(148, 163, 184, 0.06);
  border: 1px solid rgba(148, 163, 184, 0.16);
  padding: 10px;
  border-radius: 10px;
  margin-top: 10px;
}
.clickable {
  cursor: pointer;
}
.kv {
  display: grid;
  grid-template-columns: 110px 1fr;
  gap: 8px;
  margin-top: 8px;
  font-size: 13px;
}
.kv .k {
  color: rgba(226, 232, 240, 0.65);
}
.kv .v {
  color: rgba(226, 232, 240, 0.92);
}
.grid3 {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 14px;
}
@media (max-width: 980px) {
  .grid3 {
    grid-template-columns: 1fr;
  }
}
.list {
  margin-top: 8px;
  display: grid;
  gap: 8px;
  max-height: 280px;
  overflow: auto;
}
.rowitem {
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(148, 163, 184, 0.06);
  border-radius: 10px;
  padding: 10px;
}
.row-title {
  font-weight: 800;
}
.row-sub {
  margin-top: 4px;
  color: rgba(226, 232, 240, 0.75);
  font-size: 12px;
  line-height: 1.35;
}
</style>

