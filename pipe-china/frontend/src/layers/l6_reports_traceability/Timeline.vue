<template>
  <div class="card">
    <h2>L6 · 时间线</h2>
    <p>聚合展示：L1 读数/告警、L3 风险评估、L5 任务/证据/事件，形成可追溯闭环。</p>

    <div class="card subcard">
      <h3>筛选</h3>
      <div class="grid">
        <div>
          <label>draft_id（可选）</label>
          <input v-model="draftId" class="mono" placeholder="draft-xxxx" />
        </div>
        <div>
          <label>segment_id（可选）</label>
          <input v-model="segmentId" class="mono" placeholder="seg-xxx" />
        </div>
        <div>
          <label>limit</label>
          <input v-model.number="limit" type="number" min="1" max="1000" />
        </div>
      </div>
      <div class="btnrow">
        <button class="btn secondary" @click="loadDraftIdFromSession">读取当前 draftId</button>
        <button class="btn" :disabled="loading" @click="fetchTimeline">刷新</button>
      </div>
    </div>

    <div class="card subcard">
      <h3>事件列表（最近 {{ items.length }} 条）</h3>
      <div v-if="items.length === 0" class="muted">暂无数据</div>
      <table v-else class="tbl">
        <thead>
          <tr>
            <th>时间</th>
            <th>类型</th>
            <th>标题</th>
            <th>详情</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="it in items" :key="it.ts + it.kind + it.title">
            <td class="mono small">{{ fmt(it.ts) }}</td>
            <td><span class="pill">{{ it.kind }}</span></td>
            <td>{{ it.title }}</td>
            <td class="mono small">{{ JSON.stringify(it.detail) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";

const props = defineProps({
  apiBase: { type: String, required: true },
});

const loading = ref(false);
const items = ref([]);
const draftId = ref("");
const segmentId = ref("");
const limit = ref(200);

function loadDraftIdFromSession() {
  try {
    draftId.value = sessionStorage.getItem("pipe-china:draftId") || "";
  } catch {
    draftId.value = "";
  }
}

function fmt(ts) {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts || "";
  }
}

async function fetchTimeline() {
  loading.value = true;
  try {
    const qs = new URLSearchParams();
    if (draftId.value) qs.set("draft_id", draftId.value);
    if (segmentId.value) qs.set("segment_id", segmentId.value);
    qs.set("limit", String(limit.value || 200));
    const res = await fetch(`${props.apiBase}/timeline?${qs.toString()}`);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    items.value = data.items || [];
  } catch (e) {
    console.error(e);
    alert(`获取时间线失败：${e.message}`);
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadDraftIdFromSession();
  fetchTimeline();
});
</script>

<style scoped>
.subcard {
  margin-top: 14px;
}
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr 160px;
  gap: 12px;
}
@media (max-width: 980px) {
  .grid {
    grid-template-columns: 1fr;
  }
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
label {
  display: block;
  margin-bottom: 6px;
  color: rgba(226, 232, 240, 0.8);
  font-size: 13px;
}
</style>

