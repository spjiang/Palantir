<template>
  <div class="l2">
    <div class="l2-header">
      <div>
        <div class="title">关系预览 / 校验</div>
        <div class="subtitle">导入业务方案 → 自动抽取本体与关系 → 图谱可视化与编辑</div>
      </div>
      <div class="actions">
        <input class="file" type="file" @change="onFile" accept=".md,.txt" />
        <button class="btn" :disabled="!file || loading" @click="upload">上传并抽取</button>
        <button class="btn secondary" :disabled="loading" @click="refreshAll">刷新</button>
        <button class="btn" :disabled="!draft || loading" @click="commitDraft">确认入库</button>
        <button class="btn secondary" :disabled="!draft || loading" @click="cancelDraft">取消草稿</button>
      </div>
    </div>

    <div v-if="draft" class="toast ok">
      已生成草稿：节点 {{ draft.nodes.length }}，关系 {{ draft.edges.length }}。请在右侧编辑后点击“确认入库”。
      <span class="mono">draft_id={{ draft.draft_id }}</span>
    </div>
    <div v-if="importResult" class="toast ok">
      入库成功：节点 {{ importResult.created_nodes }}，关系 {{ importResult.created_edges }}。
    </div>
    <div v-if="errorText" class="toast err">{{ errorText }}</div>

    <div class="l2-body">
      <!-- Left: list -->
      <div class="panel left">
        <div class="panel-title">本体数据</div>
        <div class="tabs">
          <button class="tab" :class="{ active: listMode === 'entities' }" @click="listMode = 'entities'">实体</button>
          <button class="tab" :class="{ active: listMode === 'relations' }" @click="listMode = 'relations'">关系</button>
        </div>
        <input class="search" v-model="kw" placeholder="搜索名称/类型…" @keydown.enter="refreshAll" />

        <div class="list">
          <template v-if="listMode === 'entities'">
            <div
              v-for="n in filteredEntities"
              :key="n.id"
              class="rowitem"
              :class="{ selected: selected?.kind === 'node' && selected.id === n.id }"
              @click="selectNodeById(n.id)"
            >
              <div class="row-title">{{ n.name }}</div>
              <div class="row-sub">{{ n.label }} · {{ n.id }}</div>
            </div>
          </template>
          <template v-else>
            <div
              v-for="e in filteredRelations"
              :key="e.id"
              class="rowitem"
              :class="{ selected: selected?.kind === 'edge' && selected.id === e.id }"
              @click="selectEdgeById(e.id)"
            >
              <div class="row-title">{{ e.type }}</div>
              <div class="row-sub">{{ e.src }} → {{ e.dst }}</div>
            </div>
          </template>
        </div>

        <div class="panel-footer">
          <button class="btn secondary" :disabled="loading" @click="openCreateEntity">新建实体</button>
          <button class="btn secondary" :disabled="loading" @click="toggleLinkMode">
            {{ linkMode ? '退出创建关系' : '创建关系' }}
          </button>
        </div>
      </div>

      <!-- Center: graph -->
      <div class="panel center">
        <div class="toolbar">
          <div class="hint" v-if="linkMode">
            创建关系模式：先点“源节点”，再点“目标节点”。
            <span v-if="linkDraft.src">源：{{ linkDraft.src }}</span>
            <span v-if="linkDraft.dst"> 目标：{{ linkDraft.dst }}</span>
          </div>
          <div class="toolbtns">
            <button class="btn secondary" :disabled="!cy" @click="relayout">重新布局</button>
            <button class="btn secondary" :disabled="!cy" @click="fit">适配视图</button>
          </div>
        </div>
        <div ref="cyEl" class="graph"></div>
      </div>

      <!-- Right: inspector -->
      <div class="panel right">
        <div class="panel-title">属性编辑</div>

        <div v-if="!selected" class="empty">
          点击左侧列表或图谱中的节点/关系进行编辑。
        </div>

        <template v-else-if="selected.kind === 'node'">
          <div class="kv">
            <div class="k">ID</div>
            <div class="v mono">{{ selected.id }}</div>
          </div>
          <label>名称</label>
          <input v-model="editNode.name" />
          <label>标签</label>
          <input v-model="editNode.label" />
          <label>Props（JSON）</label>
          <textarea v-model="editNode.propsText" rows="10" class="mono"></textarea>
          <div class="btnrow">
            <button class="btn" :disabled="loading" @click="saveNode">保存</button>
            <button class="btn danger" :disabled="loading" @click="deleteNode">删除</button>
          </div>
        </template>

        <template v-else>
          <div class="kv">
            <div class="k">ID</div>
            <div class="v mono">{{ selected.id }}</div>
          </div>
          <label>关系类型</label>
          <input v-model="editEdge.type" />
          <label>源节点</label>
          <select v-model="editEdge.src">
            <option v-for="n in entities" :key="n.id" :value="n.id">{{ n.name }} ({{ n.id }})</option>
          </select>
          <label>目标节点</label>
          <select v-model="editEdge.dst">
            <option v-for="n in entities" :key="n.id" :value="n.id">{{ n.name }} ({{ n.id }})</option>
          </select>
          <label>Props（JSON）</label>
          <textarea v-model="editEdge.propsText" rows="10" class="mono"></textarea>
          <div class="btnrow">
            <button class="btn" :disabled="loading" @click="saveEdge">保存</button>
            <button class="btn danger" :disabled="loading" @click="deleteEdge">删除</button>
          </div>
        </template>

        <div v-if="linkMode && linkDraft.src && linkDraft.dst" class="card-mini">
          <div class="panel-title">创建关系</div>
          <label>关系类型</label>
          <input v-model="linkDraft.type" />
          <label>Props（JSON）</label>
          <textarea v-model="linkDraft.propsText" rows="6" class="mono"></textarea>
          <button class="btn" :disabled="loading" @click="createLink">创建该关系</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import cytoscape from "cytoscape";
import fcose from "cytoscape-fcose";

cytoscape.use(fcose);

const props = defineProps({
  apiBase: { type: String, required: true },
});

const file = ref(null);
const loading = ref(false);
const importResult = ref(null);
const draft = ref(null); // { draft_id, nodes, edges }
const errorText = ref("");

const entities = ref([]);
const relations = ref([]);
const listMode = ref("entities");
const kw = ref("");

const cyEl = ref(null);
const cy = ref(null);

const selected = ref(null); // {kind:'node'|'edge', id}
const editNode = ref({ id: "", name: "", label: "Concept", propsText: "{}" });
const editEdge = ref({ id: "", type: "RELATED_TO", src: "", dst: "", propsText: "{}" });

const linkMode = ref(false);
const linkDraft = ref({ src: "", dst: "", type: "RELATED_TO", propsText: "{}" });

const onFile = (e) => {
  file.value = e.target.files?.[0] || null;
};

const filteredEntities = computed(() => {
  const k = kw.value.trim();
  if (!k) return entities.value;
  return entities.value.filter((n) => (n.name || "").includes(k) || (n.label || "").includes(k) || (n.id || "").includes(k));
});
const filteredRelations = computed(() => {
  const k = kw.value.trim();
  if (!k) return relations.value;
  return relations.value.filter((e) => (e.type || "").includes(k) || (e.id || "").includes(k) || (e.src || "").includes(k) || (e.dst || "").includes(k));
});

function toastErr(msg) {
  errorText.value = msg;
  setTimeout(() => {
    if (errorText.value === msg) errorText.value = "";
  }, 6000);
}

function safeParseJson(text) {
  try {
    return JSON.parse(text || "{}");
  } catch (e) {
    throw new Error("Props 不是合法 JSON");
  }
}

const upload = async () => {
  if (!file.value) return;
  loading.value = true;
  const fd = new FormData();
  fd.append("file", file.value);
  try {
    const res = await fetch(`${props.apiBase}/ontology/extract`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    draft.value = data;
    importResult.value = null;
    entities.value = data.nodes;
    relations.value = data.edges;
    buildCy(entities.value, relations.value);
  } catch (err) {
    toastErr(`导入失败: ${err}`);
  } finally {
    loading.value = false;
  }
};

const refreshAll = async () => {
  loading.value = true;
  try {
    const [en, re] = await Promise.all([
      fetch(`${props.apiBase}/ontology/entities`).then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.statusText)))),
      fetch(`${props.apiBase}/ontology/relations`).then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.statusText)))),
    ]);
    entities.value = en;
    relations.value = re;
    draft.value = null;
    await refreshGraph();
  } catch (err) {
    toastErr(`刷新失败: ${err}`);
  } finally {
    loading.value = false;
  }
};

const refreshGraph = async () => {
  const res = await fetch(`${props.apiBase}/ontology/graph`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ root_id: null, depth: 3 }),
  });
  if (!res.ok) throw new Error(await res.text());
  const g = await res.json();
  buildCy(g.nodes, g.edges);
};

async function commitDraft() {
  if (!draft.value) return;
  loading.value = true;
  try {
    const res = await fetch(`${props.apiBase}/ontology/commit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        draft_id: draft.value.draft_id,
        nodes: entities.value,
        edges: relations.value,
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    importResult.value = await res.json();
    draft.value = null;
    clearSelection();
    await refreshAll();
  } catch (e) {
    toastErr(`入库失败: ${e}`);
  } finally {
    loading.value = false;
  }
}

function cancelDraft() {
  if (!draft.value) return;
  if (!confirm("确认取消草稿？未入库的修改将丢失。")) return;
  draft.value = null;
  importResult.value = null;
  clearSelection();
  refreshAll();
}

function buildCy(nodes, edges) {
  const elements = [
    ...nodes.map((n) => ({ data: { id: n.id, name: n.name, label: n.label } })),
    ...edges.map((e) => ({ data: { id: e.id, source: e.src, target: e.dst, type: e.type } })),
  ];

  if (!cy.value) {
    cy.value = cytoscape({
      container: cyEl.value,
      elements,
      style: [
        {
          selector: "node",
          style: {
            "background-color": "#6366f1",
            label: "data(name)",
            color: "#e2e8f0",
            "text-outline-color": "#0b1220",
            "text-outline-width": 3,
            "font-size": 12,
            "text-valign": "center",
            "text-halign": "center",
            width: 42,
            height: 42,
            "border-width": 1,
            "border-color": "rgba(148,163,184,0.35)",
          },
        },
        {
          selector: 'node[label = "Rule"]',
          style: {
            "background-color": "#f59e0b",
          },
        },
        {
          selector: "edge",
          style: {
            width: 2,
            "line-color": "rgba(148,163,184,0.65)",
            "target-arrow-color": "rgba(148,163,184,0.75)",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: "data(type)",
            "font-size": 10,
            color: "#e2e8f0",
            "text-outline-color": "#0b1220",
            "text-outline-width": 3,
          },
        },
        { selector: ".selected", style: { "border-width": 3, "border-color": "#22c55e" } },
        { selector: "edge.selected", style: { "line-color": "#22c55e", "target-arrow-color": "#22c55e", width: 3 } },
      ],
      layout: { name: "fcose", quality: "default", animate: true },
    });

    cy.value.on("tap", "node", (evt) => {
      const id = evt.target.id();
      if (linkMode.value) {
        if (!linkDraft.value.src) linkDraft.value.src = id;
        else if (!linkDraft.value.dst) linkDraft.value.dst = id;
        else {
          linkDraft.value.src = id;
          linkDraft.value.dst = "";
        }
      } else {
        selectNodeById(id);
      }
    });
    cy.value.on("tap", "edge", (evt) => {
      if (linkMode.value) return;
      selectEdgeById(evt.target.id());
    });
    cy.value.on("tap", (evt) => {
      if (evt.target === cy.value && !linkMode.value) clearSelection();
    });
  } else {
    cy.value.elements().remove();
    cy.value.add(elements);
    relayout();
  }

  highlightSelected();
}

function highlightSelected() {
  if (!cy.value) return;
  cy.value.elements().removeClass("selected");
  if (!selected.value) return;
  const ele = cy.value.getElementById(selected.value.id);
  if (ele) ele.addClass("selected");
}

function clearSelection() {
  selected.value = null;
  highlightSelected();
}

function selectNodeById(id) {
  const n = entities.value.find((x) => x.id === id);
  if (!n) return;
  selected.value = { kind: "node", id };
  editNode.value = {
    id,
    name: n.name || "",
    label: n.label || "Concept",
    propsText: JSON.stringify(n.props || {}, null, 2),
  };
  highlightSelected();
  fit();
}

function selectEdgeById(id) {
  const e = relations.value.find((x) => x.id === id);
  if (!e) return;
  selected.value = { kind: "edge", id };
  editEdge.value = {
    id,
    type: e.type || "RELATED_TO",
    src: e.src,
    dst: e.dst,
    propsText: JSON.stringify(e.props || {}, null, 2),
  };
  highlightSelected();
  fit();
}

function relayout() {
  if (!cy.value) return;
  cy.value.layout({ name: "fcose", quality: "default", animate: true }).run();
}

function fit() {
  if (!cy.value) return;
  cy.value.fit(undefined, 30);
}

function toggleLinkMode() {
  linkMode.value = !linkMode.value;
  linkDraft.value = { src: "", dst: "", type: "RELATED_TO", propsText: "{}" };
}

async function createLink() {
  if (!linkDraft.value.src || !linkDraft.value.dst) return;
  const propsObj = safeParseJson(linkDraft.value.propsText);

  // 草稿态：只改本地数据
  if (draft.value) {
    const rid = `rel-manual-${Date.now()}`;
    relations.value = [
      ...relations.value,
      {
        id: rid,
        type: linkDraft.value.type || "RELATED_TO",
        src: linkDraft.value.src,
        dst: linkDraft.value.dst,
        props: propsObj,
      },
    ];
    buildCy(entities.value, relations.value);
    toggleLinkMode();
    return;
  }

  loading.value = true;
  try {
    const res = await fetch(`${props.apiBase}/ontology/relations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        src: linkDraft.value.src,
        dst: linkDraft.value.dst,
        type: linkDraft.value.type || "RELATED_TO",
        props: propsObj,
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    await refreshAll();
    toggleLinkMode();
  } catch (e) {
    toastErr(`创建关系失败: ${e}`);
  } finally {
    loading.value = false;
  }
}

async function saveNode() {
  const propsObj = safeParseJson(editNode.value.propsText);

  if (draft.value) {
    const idx = entities.value.findIndex((x) => x.id === editNode.value.id);
    if (idx >= 0) {
      entities.value[idx] = { ...entities.value[idx], name: editNode.value.name, label: editNode.value.label, props: propsObj };
      buildCy(entities.value, relations.value);
      selectNodeById(editNode.value.id);
    }
    return;
  }

  loading.value = true;
  try {
    const res = await fetch(`${props.apiBase}/ontology/entities/${encodeURIComponent(editNode.value.id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: editNode.value.name, label: editNode.value.label, props: propsObj }),
    });
    if (!res.ok) throw new Error(await res.text());
    await refreshAll();
    selectNodeById(editNode.value.id);
  } catch (e) {
    toastErr(`保存失败: ${e}`);
  } finally {
    loading.value = false;
  }
}

async function deleteNode() {
  if (!confirm("确认删除该实体？相关关系也会被删除。")) return;
  if (draft.value) {
    const id = editNode.value.id;
    entities.value = entities.value.filter((n) => n.id !== id);
    relations.value = relations.value.filter((e) => e.src !== id && e.dst !== id);
    clearSelection();
    buildCy(entities.value, relations.value);
    return;
  }
  loading.value = true;
  try {
    const res = await fetch(`${props.apiBase}/ontology/entities/${encodeURIComponent(editNode.value.id)}`, { method: "DELETE" });
    if (!res.ok) throw new Error(await res.text());
    clearSelection();
    await refreshAll();
  } catch (e) {
    toastErr(`删除失败: ${e}`);
  } finally {
    loading.value = false;
  }
}

async function saveEdge() {
  const propsObj = safeParseJson(editEdge.value.propsText);
  if (draft.value) {
    const idx = relations.value.findIndex((x) => x.id === editEdge.value.id);
    if (idx >= 0) {
      relations.value[idx] = {
        ...relations.value[idx],
        type: editEdge.value.type,
        src: editEdge.value.src,
        dst: editEdge.value.dst,
        props: propsObj,
      };
      buildCy(entities.value, relations.value);
      selectEdgeById(editEdge.value.id);
    }
    return;
  }

  loading.value = true;
  try {
    const res = await fetch(`${props.apiBase}/ontology/relations/${encodeURIComponent(editEdge.value.id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        type: editEdge.value.type,
        src: editEdge.value.src,
        dst: editEdge.value.dst,
        props: propsObj,
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    await refreshAll();
    selectEdgeById(editEdge.value.id);
  } catch (e) {
    toastErr(`保存失败: ${e}`);
  } finally {
    loading.value = false;
  }
}

async function deleteEdge() {
  if (!confirm("确认删除该关系？")) return;
  if (draft.value) {
    const id = editEdge.value.id;
    relations.value = relations.value.filter((e) => e.id !== id);
    clearSelection();
    buildCy(entities.value, relations.value);
    return;
  }
  loading.value = true;
  try {
    const res = await fetch(`${props.apiBase}/ontology/relations/${encodeURIComponent(editEdge.value.id)}`, { method: "DELETE" });
    if (!res.ok) throw new Error(await res.text());
    clearSelection();
    await refreshAll();
  } catch (e) {
    toastErr(`删除失败: ${e}`);
  } finally {
    loading.value = false;
  }
}

async function openCreateEntity() {
  const name = prompt("请输入实体名称：");
  if (!name) return;
  if (draft.value) {
    const id = `ent-manual-${Date.now()}`;
    entities.value = [...entities.value, { id, name, label: "Concept", props: { source: "manual" } }];
    buildCy(entities.value, relations.value);
    selectNodeById(id);
    return;
  }
  loading.value = true;
  try {
    const res = await fetch(`${props.apiBase}/ontology/entities`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, label: "Concept", props: { source: "manual" } }),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    await refreshAll();
    selectNodeById(data.id);
  } catch (e) {
    toastErr(`新建实体失败: ${e}`);
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  await refreshAll();
});

watch(selected, () => highlightSelected());
</script>

<style scoped>
.l2 {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.l2-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.92), rgba(2, 6, 23, 0.92));
  color: #e2e8f0;
}
.title {
  font-weight: 800;
  font-size: 18px;
}
.subtitle {
  color: rgba(226, 232, 240, 0.7);
  font-size: 13px;
  margin-top: 2px;
}
.actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.file {
  width: 260px;
}
.btn {
  padding: 10px 12px;
  border-radius: 10px;
  border: none;
  background: #0ea5e9;
  color: #fff;
  cursor: pointer;
}
.btn.secondary {
  background: rgba(148, 163, 184, 0.18);
  color: #e2e8f0;
  border: 1px solid rgba(148, 163, 184, 0.35);
}
.btn.danger {
  background: #ef4444;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.toast {
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid;
}
.toast.ok {
  background: rgba(34, 211, 238, 0.12);
  border-color: rgba(34, 211, 238, 0.5);
  color: #e2e8f0;
}
.toast.err {
  background: rgba(239, 68, 68, 0.12);
  border-color: rgba(239, 68, 68, 0.5);
  color: #fee2e2;
}
.l2-body {
  display: grid;
  grid-template-columns: 320px 1fr 360px;
  gap: 12px;
  min-height: 640px;
}
.panel {
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.92), rgba(2, 6, 23, 0.92));
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  color: #e2e8f0;
}
.panel-title {
  padding: 12px 12px 8px;
  font-weight: 800;
}
.left .tabs {
  display: flex;
  gap: 8px;
  padding: 0 12px 8px;
}
.tab {
  flex: 1;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(148, 163, 184, 0.12);
  padding: 8px 10px;
  border-radius: 10px;
  cursor: pointer;
  color: #e2e8f0;
}
.tab.active {
  background: #0ea5e9;
  border-color: #0ea5e9;
  color: #fff;
}
.search {
  margin: 0 12px 10px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(2, 6, 23, 0.35);
  color: #e2e8f0;
}
.list {
  padding: 0 6px 6px;
  overflow: auto;
}
.rowitem {
  padding: 10px 10px;
  margin: 6px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  cursor: pointer;
  background: rgba(2, 6, 23, 0.35);
}
.rowitem:hover {
  border-color: rgba(147, 197, 253, 0.8);
}
.rowitem.selected {
  border-color: #22c55e;
  box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.15);
}
.row-title {
  font-weight: 700;
}
.row-sub {
  font-size: 12px;
  color: rgba(226, 232, 240, 0.65);
  margin-top: 2px;
  word-break: break-all;
}
.panel-footer {
  padding: 10px 12px 12px;
  display: flex;
  gap: 8px;
}
.center .toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.25);
}
.hint {
  font-size: 12px;
  color: rgba(226, 232, 240, 0.65);
}
.toolbtns {
  display: flex;
  gap: 8px;
}
.graph {
  flex: 1;
  min-height: 520px;
  background:
    radial-gradient(1200px 600px at 50% 0%, rgba(99, 102, 241, 0.12), transparent 60%),
    radial-gradient(900px 500px at 20% 20%, rgba(34, 211, 238, 0.10), transparent 55%),
    linear-gradient(180deg, rgba(2, 6, 23, 0.85), rgba(2, 6, 23, 0.95));
}
.right {
  padding-bottom: 12px;
}
.right label {
  display: block;
  font-weight: 700;
  margin: 10px 12px 6px;
}
.right input,
.right select,
.right textarea {
  margin: 0 12px;
  width: calc(100% - 24px);
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
.kv {
  display: grid;
  grid-template-columns: 54px 1fr;
  gap: 8px;
  padding: 0 12px;
  color: rgba(226, 232, 240, 0.9);
  font-size: 13px;
}
.kv .k {
  color: rgba(226, 232, 240, 0.65);
}
.btnrow {
  display: flex;
  gap: 8px;
  padding: 12px;
}
.empty {
  padding: 12px;
  color: rgba(226, 232, 240, 0.65);
  font-size: 13px;
}
.card-mini {
  margin: 0 12px;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(2, 6, 23, 0.25);
}
</style>
