<template>
  <div class="card">
    <h2>正式本体库（全量）</h2>
    <p class="sub">支持版本发布/回滚（MVP）：每次“临时本体库确认入正式本体库”都会生成一个 release，可在此回滚。</p>

    <div class="row">
      <button class="btn secondary" :disabled="loading" @click="loadReleases">刷新版本列表</button>
    </div>
    <div v-if="err" class="err">{{ err }}</div>

    <div v-if="releases.length === 0" class="muted">暂无 release（先在临时本体库点击“确认入正式本体库”发布一次）</div>
    <table v-else class="tbl">
      <thead>
        <tr>
          <th>时间</th>
          <th>release_id</th>
          <th>draft_id</th>
          <th>说明</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in releases" :key="r.id">
          <td class="mono small">{{ fmt(r.ts) }}</td>
          <td class="mono">{{ r.id }}</td>
          <td class="mono">{{ r.draft_id || "-" }}</td>
          <td>{{ r.note || "-" }}</td>
          <td>
            <button class="btn danger mini" :disabled="loading" @click="rollback(r.id)">回滚到此版本</button>
          </td>
        </tr>
      </tbody>
    </table>

    <div style="margin-top: 14px">
      <OntologyPanel
        :api-base="apiBase"
        scope="formal"
        title="正式本体库画布"
        subtitle="展示与维护正式本体库的全量数据，支持查询/编辑"
      />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import OntologyPanel from "../../components/OntologyPanel.vue";

const props = defineProps({ apiBase: { type: String, required: true } });
const apiBase = props.apiBase;

const releases = ref([]);
const loading = ref(false);
const err = ref("");

function fmt(ts) {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts || "";
  }
}

async function api(path, init) {
  const r = await fetch(`${apiBase}${path}`, init);
  if (!r.ok) throw new Error(await r.text());
  return await r.json();
}

async function loadReleases() {
  loading.value = true;
  err.value = "";
  try {
    const data = await api("/ontology/releases?limit=50");
    releases.value = data.items || [];
  } catch (e) {
    err.value = String(e?.message || e);
  } finally {
    loading.value = false;
  }
}

async function rollback(id) {
  const ok = confirm(`确认回滚到版本 ${id} 吗？\n这会替换当前正式本体库。`);
  if (!ok) return;
  loading.value = true;
  err.value = "";
  try {
    await api(`/ontology/releases/${encodeURIComponent(id)}/rollback`, { method: "POST" });
    alert("回滚完成。请稍等片刻，画布刷新后生效。");
    await loadReleases();
  } catch (e) {
    err.value = String(e?.message || e);
  } finally {
    loading.value = false;
  }
}

onMounted(loadReleases);
</script>

<style scoped>
.sub {
  color: rgba(226, 232, 240, 0.7);
}
.row {
  display: flex;
  gap: 10px;
  margin: 10px 0;
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
.btn.danger {
  background: rgba(239, 68, 68, 0.18);
  border-color: rgba(239, 68, 68, 0.35);
}
.btn.mini {
  padding: 6px 10px;
  font-size: 12px;
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.tbl {
  width: 100%;
  border-collapse: collapse;
  margin-top: 8px;
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
.err {
  color: #fecaca;
  margin-top: 8px;
}
</style>

