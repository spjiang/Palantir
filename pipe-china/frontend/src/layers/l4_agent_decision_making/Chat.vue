<template>
  <div class="card">
    <h2>L4 · 智能体决策（基于 L2 行为/规则）</h2>
    <p>这里先做一个“可跑通闭环”的确定性智能体：读取 L3 最新风险事件 + L2 临时本体库行为定义，生成 L5 任务并写回临时本体库。</p>

    <div class="grid2">
      <div class="card subcard">
        <h3>输入</h3>
        <label>草稿 draft_id</label>
        <select v-model="draftId" class="mono">
          <option value="">选择草稿…</option>
          <option v-for="d in draftOptions" :key="d" :value="d">{{ d }}</option>
        </select>
        <div class="btnrow" style="margin-top: 8px">
          <button class="btn secondary" :disabled="loading" @click="refreshDrafts">刷新草稿列表</button>
          <button class="btn secondary" :disabled="loading" @click="loadDraftIdFromSession">读取当前 draftId</button>
        </div>

        <div class="card subcard" style="margin-top: 12px">
          <h4>从 TopN 选择数据（推荐）</h4>
          <label>TopN 数据源</label>
          <select v-model="topnSource">
            <option value="alerts">预警 TopN（L3 产出，优先）</option>
            <option value="segments">管段风险 TopN（L3 评分）</option>
          </select>
          <div class="btnrow" style="margin-top: 8px">
            <button class="btn secondary" :disabled="loading" @click="refreshTopN">刷新 TopN</button>
          </div>
          <label style="margin-top: 10px">选择一条 TopN</label>
          <select v-model="selectedTopNKey" class="mono">
            <option value="">请选择…</option>
            <option v-for="it in topnItems" :key="it.__k" :value="it.__k">{{ it.__label }}</option>
          </select>
          <div v-if="selectedTopN" class="muted small" style="margin-top: 8px">
            <div><b>管段</b>：{{ selectedTopN.segment_name || "-" }} <span class="mono">({{ selectedTopN.segment_id || "-" }})</span></div>
            <div v-if="selectedTopN.sensor_name || selectedTopN.sensor_id"><b>传感器</b>：{{ selectedTopN.sensor_name || "-" }} <span class="mono">({{ selectedTopN.sensor_id || "-" }})</span></div>
            <div v-if="selectedTopN.alarm_type"><b>预警</b>：{{ selectedTopN.alarm_type }} ({{ selectedTopN.severity }})</div>
            <div v-if="selectedTopN.risk_state"><b>风险</b>：{{ selectedTopN.risk_state }} score={{ selectedTopN.risk_score }}</div>
          </div>
          <div class="btnrow" style="margin-top: 10px">
            <button class="btn" :disabled="loading || !draftId || !selectedTopN" @click="decideFromTopN">一键生成任务（基于 TopN）</button>
          </div>
          <div class="muted small" style="margin-top: 8px">
            说明：L4 会使用所选 TopN 的 <b>管段属性（segment_id）</b> 去临时本体库查询行为；若是“预警 TopN”，还会携带 rule_id→Behavior 约束关系，决策更精准。
          </div>
        </div>

        <label>segment_id（L1）</label>
        <select v-model="segmentId" class="mono">
          <option value="">选择管段（L1）…</option>
          <option v-for="s in segments" :key="s.id" :value="s.id">{{ s.name }} ({{ s.id }})</option>
        </select>
        <div class="btnrow" style="margin-top: 8px">
          <button class="btn secondary" :disabled="loading" @click="refreshSegments">刷新管段列表</button>
        </div>
        <div class="row">
          <label>任务类型</label>
          <select v-model="taskType">
            <option value="巡检">巡检</option>
            <option value="处置">处置</option>
            <option value="复核">复核</option>
          </select>
        </div>
        <div class="btnrow">
          <button class="btn" :disabled="loading || !draftId || !segmentId" @click="decide">一键生成任务</button>
        </div>
        <div class="muted small">
          说明：
          <div> - <b>segment_id（L1）</b> 是 L1 层“管段（PipelineSegment）”的 ID（形如 seg-xxx）。</div>
          <div> - 如果下拉里没有管段，先去 L1「手动写入/数据模拟」创建管段/传感器并写入读数。</div>
          <div> - 再去 L3 对该管段执行一次“评估并回写”，生成 risk_event 后，L4 才能派单。</div>
        </div>
      </div>

      <div class="card subcard">
        <h3>输出</h3>
        <div v-if="resp" class="mono pre">{{ JSON.stringify(resp, null, 2) }}</div>
        <div v-else class="muted">暂无输出</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";

const props = defineProps({
  apiBase: { type: String, required: true },
});

const draftId = ref("");
const segmentId = ref("");
const taskType = ref("巡检");
const resp = ref(null);
const loading = ref(false);
const draftOptions = ref([]);
const segments = ref([]);
const topnSource = ref("alerts"); // alerts | segments
const topnItems = ref([]);
const selectedTopNKey = ref("");

const selectedTopN = computed(() => topnItems.value.find((x) => x.__k === selectedTopNKey.value) || null);

function api(path, init) {
  return fetch(`${props.apiBase}${path}`, init).then(async (r) => {
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  });
}

function loadDraftIdFromSession() {
  try {
    draftId.value = sessionStorage.getItem("pipe-china:draftId") || "";
  } catch {
    draftId.value = "";
  }
}

async function refreshDrafts() {
  try {
    const data = await api(`/ontology/drafts?limit=50`);
    draftOptions.value = data.items || [];
  } catch (e) {
    console.error(e);
    alert(`刷新草稿列表失败：${e.message}`);
  }
}

async function refreshSegments() {
  try {
    const data = await api(`/l1/segments`);
    segments.value = data.items || [];
  } catch (e) {
    console.error(e);
    alert(`刷新管段列表失败：${e.message}`);
  }
}

async function refreshTopN() {
  try {
    if (topnSource.value === "alerts") {
      const qs = new URLSearchParams();
      qs.set("limit", "50");
      if (draftId.value) qs.set("draft_id", draftId.value);
      const data = await api(`/risk/alerts/topn?${qs.toString()}`);
      const items = (data.items || []).map((a) => ({
        ...a,
        __k: a.id,
        __label: `${a.segment_name || a.segment_id || "-"} · ${a.alarm_type}(${a.severity}) · ${a.id}`,
      }));
      topnItems.value = items;
    } else {
      // segments topn：用于“按管段风险事件派单”
      const qs = new URLSearchParams();
      qs.set("limit", "20");
      if (draftId.value) qs.set("draft_id", draftId.value);
      qs.set("reasoning_mode", "deepseek");
      const data = await api(`/risk/topn?${qs.toString()}`);
      const items = (data.items || []).map((it) => ({
        ...it,
        __k: it.segment_id,
        __label: `${it.segment_name || "-"} · ${it.risk_state}(${it.risk_score}) · ${it.segment_id}`,
      }));
      topnItems.value = items;
    }
  } catch (e) {
    console.error(e);
    alert(`刷新 TopN 失败：${e.message}`);
  }
}

watch(
  () => selectedTopN.value,
  (it) => {
    if (!it) return;
    // 选择 TopN 后，自动回填 segmentId（“管道属性”）
    if (it.segment_id) segmentId.value = it.segment_id;
  }
);

async function decideFromTopN() {
  if (!selectedTopN.value) return;
  // 优先：预警 TopN -> decide_from_alert（可通过 rule_id 精确匹配行为）
  if (topnSource.value === "alerts") {
    const alarmId = selectedTopN.value.id;
    loading.value = true;
    try {
      const data = await api("/agent/decide_from_alert", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ draft_id: draftId.value, alarm_id: alarmId, task_type: taskType.value }),
      });
      resp.value = data;
      alert("已基于预警 TopN 生成任务（去 L5 查看）");
    } catch (e) {
      console.error(e);
      alert(`基于预警生成任务失败：${e.message}`);
    } finally {
      loading.value = false;
    }
    return;
  }
  // 其次：管段风险 TopN -> decide（依赖 risk_event；若无则提示先去 L3 评估）
  await decide();
}

async function decide() {
  loading.value = true;
  try {
    const res = await fetch(`${props.apiBase}/agent/decide`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ draft_id: draftId.value, segment_id: segmentId.value, min_risk_state: "异常", task_type: taskType.value }),
    });
    if (!res.ok) throw new Error(await res.text());
    resp.value = await res.json();
    alert(resp.value.created ? "任务已生成（去 L5 查看）" : (resp.value.reason || "未生成任务"));
  } catch (e) {
    console.error(e);
    alert(`决策失败：${e.message}`);
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadDraftIdFromSession();
  refreshDrafts();
  refreshSegments();
  refreshTopN();
});

watch(
  () => draftId.value,
  () => {
    // 切换草稿后，TopN 下拉也随之按 draft_id 过滤
    selectedTopNKey.value = "";
    refreshTopN();
  }
);
</script>

<style scoped>
.grid2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
@media (max-width: 980px) {
  .grid2 {
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
input,
select {
  width: 100%;
  background: rgba(15, 23, 42, 0.55);
  border: 1px solid rgba(148, 163, 184, 0.22);
  color: rgba(226, 232, 240, 0.92);
  border-radius: 10px;
  padding: 10px 12px;
  outline: none;
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}
.muted {
  color: rgba(226, 232, 240, 0.65);
}
.small {
  font-size: 12px;
}
.pre {
  white-space: pre-wrap;
  background: rgba(148, 163, 184, 0.06);
  border: 1px solid rgba(148, 163, 184, 0.16);
  padding: 10px;
  border-radius: 10px;
  margin-top: 10px;
}
.row {
  margin-top: 10px;
}
</style>