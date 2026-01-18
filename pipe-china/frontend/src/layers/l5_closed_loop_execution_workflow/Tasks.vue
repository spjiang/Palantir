<template>
  <div class="card">
    <h2>L5 · 任务列表</h2>
    <p class="sub">真实任务管理：创建任务 → 绑定草稿图谱（targets/has_evidence）→ 状态流转 → 证据回传。</p>

    <div class="row">
      <div class="card">
        <h3>创建任务</h3>
        <div class="grid">
          <div>
            <label>标题</label>
            <input v-model="form.title" placeholder="例如：巡检运维任务" />
          </div>
          <div>
            <label>类型</label>
            <input v-model="form.task_type" placeholder="例如：巡检/处置/复核" />
          </div>
          <div>
            <label>绑定草稿图谱 draftId（可选）</label>
            <input v-model="form.draft_id" class="mono" placeholder="draft-xxxx" />
            <div class="hint">
              当前草稿：<span class="mono">{{ currentDraftId || "（无）" }}</span>
              <button class="btn secondary mini" :disabled="!currentDraftId" @click="useCurrentDraft">使用当前草稿</button>
            </div>
          </div>
          <div>
            <label>目标对象（可选，绑定 targets）</label>
            <select v-model="form.target_entity_id">
              <option value="">（不绑定）</option>
              <option v-for="n in targetCandidates" :key="n.id" :value="n.id">
                {{ n.name }}（{{ n.label }} · {{ n.id }}）
              </option>
            </select>
          </div>
          <div>
            <label>来源行为（可选）</label>
            <input v-model="form.source_behavior" placeholder="例如：处置决策（DecideResponseAction）" />
          </div>
        </div>
        <div class="actions">
          <button class="btn" :disabled="loading || !form.title.trim()" @click="createTask">创建</button>
          <button class="btn secondary" :disabled="loading" @click="refresh">刷新</button>
        </div>
      </div>

      <div class="card">
        <h3>任务列表</h3>
        <div class="hint">
          过滤 draftId：<span class="mono">{{ listDraftId || "（全部）" }}</span>
          <button class="btn secondary mini" :disabled="loading" @click="setListDraft(currentDraftId)">仅看当前草稿</button>
          <button class="btn secondary mini" :disabled="loading" @click="setListDraft('')">查看全部</button>
        </div>

        <div v-if="err" class="err">{{ err }}</div>
        <div v-if="loading" class="hint">加载中…</div>

        <div class="list" v-else>
          <div
            v-for="t in tasks"
            :key="t.id"
            class="rowitem"
            :class="{ selected: selectedTask?.id === t.id }"
            @click="selectTask(t)"
          >
            <div class="row-title">{{ t.title }}</div>
            <div class="row-sub">
              <span class="mono">{{ t.id }}</span>
              · type={{ t.task_type }} · status={{ t.status }}
            </div>
            <div class="row-sub" v-if="t.draft_id">
              draft: <span class="mono">{{ t.draft_id }}</span>
            </div>
            <div class="row-sub" v-if="t.target_entity_id">
              targets: <span class="mono">{{ t.target_entity_id }}</span>
            </div>
            <div class="row-actions">
              <button class="btn secondary mini" :disabled="loading" @click.stop="setStatus(t, 'accepted')">接受</button>
              <button class="btn secondary mini" :disabled="loading" @click.stop="setStatus(t, 'in_progress')">执行中</button>
              <button class="btn secondary mini" :disabled="loading" @click.stop="setStatus(t, 'done')">完成</button>
              <button class="btn secondary mini" :disabled="loading" @click.stop="setStatus(t, 'rejected')">驳回</button>
            </div>
          </div>
          <div v-if="!tasks.length" class="hint">暂无任务</div>
        </div>
      </div>
    </div>

    <div class="card" v-if="selectedTask">
      <h3>任务详情 · {{ selectedTask.title }}</h3>
      <div class="row">
        <div class="card">
          <h4>证据</h4>
          <div class="grid">
            <div>
              <label>证据类型</label>
              <input v-model="eForm.evidence_type" placeholder="例如：定位信息/现场照片" />
            </div>
            <div>
              <label>内容（URL/文本）</label>
              <input v-model="eForm.content" placeholder="例如：https://... 或 简要描述" />
            </div>
            <div>
              <label>绑定草稿（可选，写入 has_evidence）</label>
              <input v-model="eForm.draft_id" class="mono" placeholder="draft-xxxx" />
              <div class="hint">
                <button class="btn secondary mini" :disabled="!currentDraftId" @click="eForm.draft_id = currentDraftId">使用当前草稿</button>
              </div>
            </div>
          </div>
          <div class="actions">
            <button class="btn" :disabled="loading || !eForm.evidence_type.trim() || !eForm.content.trim()" @click="addEvidence">
              添加证据
            </button>
            <button class="btn secondary" :disabled="loading" @click="loadEvidence">刷新证据</button>
          </div>
          <ul class="ul">
            <li v-for="e in evidence" :key="e.id">
              <span class="mono">{{ e.id }}</span> · {{ e.evidence_type }} · {{ e.content }}
            </li>
            <li v-if="!evidence.length" class="hint">暂无证据</li>
          </ul>
        </div>

    <div class="card">
          <h4>时间线</h4>
          <button class="btn secondary" :disabled="loading" @click="loadTimeline">刷新时间线</button>
          <ul class="ul">
            <li v-for="ev in timeline" :key="ev.id">
              <span class="mono">{{ ev.ts }}</span> · {{ ev.event_type }} · {{ ev.message }}
            </li>
            <li v-if="!timeline.length" class="hint">暂无事件</li>
      </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";

const props = defineProps({
  apiBase: { type: String, required: true },
});

const loading = ref(false);
const err = ref("");

const DRAFT_ID_STORAGE_KEY = "pipe-china:draftId";
const currentDraftId = ref("");

const listDraftId = ref("");
const tasks = ref([]);
const selectedTask = ref(null);

const evidence = ref([]);
const timeline = ref([]);

const targetCandidates = ref([]);

const form = ref({
  title: "",
  task_type: "巡检",
  draft_id: "",
  target_entity_id: "",
  source_behavior: "",
});

const eForm = ref({ evidence_type: "现场照片", content: "", draft_id: "" });

function useCurrentDraft() {
  if (!currentDraftId.value) return;
  form.value.draft_id = currentDraftId.value;
}
function setListDraft(v) {
  listDraftId.value = v || "";
  refresh();
  if (v) loadDraftEntities(v);
}

async function loadDraftEntities(draftId) {
  if (!draftId) {
    targetCandidates.value = [];
    return;
  }
  try {
    const en = await fetch(`${props.apiBase}/ontology/drafts/${encodeURIComponent(draftId)}/entities`).then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.statusText))));
    // 优先提供 PipelineSegment / 管段 等对象作为 targets 候选
    const filtered = (en || []).filter((x) => {
      const label = String(x.label || "");
      return label === "PipelineSegment" || label === "Concept" || label === "管段";
    });
    targetCandidates.value = filtered.length ? filtered : en;
  } catch {
    targetCandidates.value = [];
  }
}

async function refresh() {
  loading.value = true;
  err.value = "";
  try {
    const q = listDraftId.value ? `?draft_id=${encodeURIComponent(listDraftId.value)}` : "";
    const data = await fetch(`${props.apiBase}/workflow/tasks${q}`).then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.statusText))));
    tasks.value = data.items || [];
  } catch (e) {
    err.value = String(e);
  } finally {
    loading.value = false;
  }
}

async function createTask() {
  loading.value = true;
  err.value = "";
  try {
    const draftId = form.value.draft_id.trim() || null;
    const targetId = form.value.target_entity_id || null;
    const payload = {
      title: form.value.title,
      task_type: form.value.task_type || "巡检",
      draft_id: draftId,
      target_entity_id: targetId,
      target_entity_name: null,
      source_behavior: form.value.source_behavior || null,
    };
    const res = await fetch(`${props.apiBase}/workflow/tasks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await res.text());
    const created = await res.json();
    form.value.title = "";
    await refresh();
    selectTask(created);
    if (draftId) await loadDraftEntities(draftId);
  } catch (e) {
    err.value = String(e);
  } finally {
    loading.value = false;
  }
}

async function setStatus(t, status) {
  loading.value = true;
  err.value = "";
  try {
    const res = await fetch(`${props.apiBase}/workflow/tasks/${encodeURIComponent(t.id)}/status`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    if (!res.ok) throw new Error(await res.text());
    const updated = await res.json();
    await refresh();
    if (selectedTask.value?.id === updated.id) selectedTask.value = updated;
  } catch (e) {
    err.value = String(e);
  } finally {
    loading.value = false;
  }
}

function selectTask(t) {
  selectedTask.value = t;
  evidence.value = [];
  timeline.value = [];
  loadEvidence();
  loadTimeline();
}

async function loadEvidence() {
  if (!selectedTask.value) return;
  loading.value = true;
  err.value = "";
  try {
    const data = await fetch(`${props.apiBase}/workflow/tasks/${encodeURIComponent(selectedTask.value.id)}/evidence`).then((r) =>
      r.ok ? r.json() : Promise.reject(new Error(r.statusText))
    );
    evidence.value = data.items || [];
  } catch (e) {
    err.value = String(e);
  } finally {
    loading.value = false;
  }
}

async function addEvidence() {
  if (!selectedTask.value) return;
  loading.value = true;
  err.value = "";
  try {
    const payload = {
      evidence_type: eForm.value.evidence_type,
      content: eForm.value.content,
      draft_id: eForm.value.draft_id.trim() || null,
    };
    const res = await fetch(`${props.apiBase}/workflow/tasks/${encodeURIComponent(selectedTask.value.id)}/evidence`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await res.text());
    eForm.value.content = "";
    await loadEvidence();
    await loadTimeline();
  } catch (e) {
    err.value = String(e);
  } finally {
    loading.value = false;
  }
}

async function loadTimeline() {
  if (!selectedTask.value) return;
  loading.value = true;
  err.value = "";
  try {
    const data = await fetch(`${props.apiBase}/workflow/tasks/${encodeURIComponent(selectedTask.value.id)}/timeline`).then((r) =>
      r.ok ? r.json() : Promise.reject(new Error(r.statusText))
    );
    timeline.value = data.events || [];
  } catch (e) {
    err.value = String(e);
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  try {
    currentDraftId.value = sessionStorage.getItem(DRAFT_ID_STORAGE_KEY) || "";
  } catch {
    currentDraftId.value = "";
  }
  if (currentDraftId.value) {
    form.value.draft_id = currentDraftId.value;
    listDraftId.value = currentDraftId.value;
    await loadDraftEntities(currentDraftId.value);
  }
  await refresh();
});
</script>

<style scoped>
.sub {
  color: rgba(226, 232, 240, 0.7);
  margin-bottom: 10px;
}
.row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
label {
  display: block;
  font-weight: 800;
  margin: 8px 0 6px;
}
input,
select {
  width: 100%;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(2, 6, 23, 0.35);
  color: #e2e8f0;
  box-sizing: border-box;
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}
.hint {
  font-size: 12px;
  color: rgba(226, 232, 240, 0.65);
  margin-top: 6px;
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}
.btn {
  padding: 9px 10px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(90deg, rgba(34, 211, 238, 0.92), rgba(99, 102, 241, 0.88));
  color: #08101f;
  cursor: pointer;
  font-weight: 900;
}
.btn.secondary {
  background: rgba(148, 163, 184, 0.12);
  color: #e2e8f0;
  border: 1px solid rgba(148, 163, 184, 0.35);
}
.btn.mini {
  padding: 6px 9px;
  font-size: 12px;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.list {
  margin-top: 10px;
  display: grid;
  gap: 8px;
}
.rowitem {
  padding: 10px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(2, 6, 23, 0.35);
  cursor: pointer;
}
.rowitem.selected {
  border-color: #22c55e;
  box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.15);
}
.row-title {
  font-weight: 900;
}
.row-sub {
  font-size: 12px;
  color: rgba(226, 232, 240, 0.65);
  margin-top: 2px;
  word-break: break-all;
}
.row-actions {
  margin-top: 8px;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.err {
  padding: 10px;
  border: 1px solid rgba(239, 68, 68, 0.45);
  background: rgba(239, 68, 68, 0.12);
  border-radius: 10px;
  color: #fff;
  font-weight: 700;
  margin-top: 10px;
}
.ul {
  margin: 10px 0 0;
  padding-left: 18px;
}
@media (max-width: 1100px) {
  .row {
    grid-template-columns: 1fr;
  }
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>

