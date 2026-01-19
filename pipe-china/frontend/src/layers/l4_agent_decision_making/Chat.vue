<template>
  <div class="card">
    <h2>L4 · 智能体决策（基于 L2 行为/规则）</h2>
    <p>这里先做一个“可跑通闭环”的确定性智能体：读取 L3 最新风险事件 + L2 草稿行为定义，生成 L5 任务并写回草稿图谱。</p>

    <div class="grid2">
      <div class="card subcard">
        <h3>输入</h3>
        <label>草稿 draft_id</label>
        <input v-model="draftId" class="mono" placeholder="draft-xxxx" />
        <label>segment_id（L1）</label>
        <input v-model="segmentId" class="mono" placeholder="seg-xxx" />
        <div class="row">
          <label>任务类型</label>
          <select v-model="taskType">
            <option value="巡检">巡检</option>
            <option value="处置">处置</option>
            <option value="复核">复核</option>
          </select>
        </div>
        <div class="btnrow">
          <button class="btn secondary" @click="loadDraftIdFromSession">读取当前 draftId</button>
          <button class="btn" :disabled="loading || !draftId || !segmentId" @click="decide">一键生成任务</button>
        </div>
        <div class="muted small">提示：请先在 L3 对该管段执行一次“评估并回写”，否则没有 risk_event。</div>
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
import { ref } from "vue";

const props = defineProps({
  apiBase: { type: String, required: true },
});

const draftId = ref("");
const segmentId = ref("");
const taskType = ref("巡检");
const resp = ref(null);
const loading = ref(false);

function loadDraftIdFromSession() {
  try {
    draftId.value = sessionStorage.getItem("pipe-china:draftId") || "";
  } catch {
    draftId.value = "";
  }
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