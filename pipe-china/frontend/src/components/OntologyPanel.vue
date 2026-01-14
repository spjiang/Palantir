<template>
  <div class="panel-wrap">
    <div class="panel-header">
      <div>
        <div class="title">{{ title }}</div>
        <div class="subtitle">{{ subtitle }}</div>
      </div>

      <div class="actions">
        <template v-if="scope === 'draft'">
          <input class="file" type="file" @change="onFile" accept=".md,.txt" />
          <button class="btn" :disabled="!file || loading" @click="extract">上传并抽取</button>
          <button class="btn secondary" :disabled="loading" @click="refresh">刷新草稿</button>
          <button class="btn" :disabled="!draftId || loading" @click="commitDraft">确认入库</button>
          <button class="btn secondary" :disabled="!draftId || loading" @click="cancelDraft">取消草稿</button>
        </template>
        <template v-else>
          <button class="btn secondary" :disabled="loading" @click="refresh">刷新正式库</button>
          <button class="btn danger" :disabled="loading" @click="purgeAll">一键清空图数据库</button>
        </template>
      </div>
    </div>

    <div v-if="toastOk" class="toast ok">{{ toastOk }}</div>
    <div v-if="toastErr" class="toast err">{{ toastErr }}</div>

    <div class="body">
      <!-- left -->
      <div class="panel left">
        <div class="panel-title">本体数据</div>
        <div class="tabs">
          <button class="tab" :class="{ active: nodeTab === 'behaviors' }" @click="nodeTab = 'behaviors'">行为</button>
          <button class="tab" :class="{ active: nodeTab === 'rules' }" @click="nodeTab = 'rules'">规则</button>
          <button class="tab" :class="{ active: nodeTab === 'states' }" @click="nodeTab = 'states'">状态</button>
          <button class="tab" :class="{ active: nodeTab === 'objects' }" @click="nodeTab = 'objects'">对象</button>
          <button class="tab" :class="{ active: nodeTab === 'relations' }" @click="nodeTab = 'relations'">关系</button>
        </div>
        <input class="search" v-model="kw" placeholder="搜索名称/类型…" />

        <div class="list">
          <template v-if="nodeTab !== 'relations'">
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
          <button class="btn secondary" :disabled="loading || (scope==='draft' && !draftId) || nodeTab==='relations'" @click="openCreateEntity">
            {{ createBtnText }}
          </button>
          <button class="btn secondary" :disabled="loading || (scope==='draft' && !draftId)" @click="toggleLinkMode">
            {{ linkMode ? '退出创建关系' : '创建关系' }}
          </button>
        </div>
      </div>

      <!-- center -->
      <div class="panel center">
        <div class="toolbar">
          <div class="query">
            <input class="q" v-model="query.root_id" placeholder="root_id（可空）" />
            <input class="q" type="number" min="1" max="4" v-model.number="query.depth" />
            <button class="btn secondary" :disabled="loading || (scope==='draft' && !draftId)" @click="runQuery">图查询</button>
          </div>
          <div class="toolbtns">
            <button class="btn secondary" :disabled="!cy" @click="relayout">重新布局</button>
            <button class="btn secondary" :disabled="!cy" @click="fit">适配视图</button>
            <div class="legend" title="颜色图例">
              <span class="lg-item"><i class="dot behavior"></i>行为</span>
              <span class="lg-item"><i class="dot rule"></i>规则</span>
              <span class="lg-item"><i class="dot state"></i>状态</span>
              <span class="lg-item"><i class="dot evidence"></i>证据/产物</span>
              <span class="lg-item"><i class="dot concept"></i>对象</span>
            </div>
          </div>
        </div>

        <div class="hint" v-if="linkMode">
          创建关系模式：先点“源节点”，再点“目标节点”。
          <span v-if="linkDraft.src">源：{{ linkDraft.src }}</span>
          <span v-if="linkDraft.dst"> 目标：{{ linkDraft.dst }}</span>
        </div>

        <div ref="cyEl" class="graph"></div>
      </div>

      <!-- right -->
      <div class="panel right">
        <div class="panel-title">属性编辑</div>

        <div v-if="!selected" class="empty">点击左侧列表或图谱中的节点/关系进行编辑。</div>

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
  scope: { type: String, required: true }, // 'draft' | 'formal'
  title: { type: String, required: true },
  subtitle: { type: String, required: true },
  draftId: { type: String, default: "" },
});

const emit = defineEmits(["draft-created", "draft-cleared", "committed", "purged"]);

const file = ref(null);
const loading = ref(false);
const toastOk = ref("");
const toastErr = ref("");

const entities = ref([]);
const relations = ref([]);
const nodeTab = ref("behaviors"); // behaviors | rules | states | objects | relations
const kw = ref("");
const query = ref({ root_id: "", depth: 3 });

const cyEl = ref(null);
const cy = ref(null);

const selected = ref(null); // {kind:'node'|'edge', id}
const editNode = ref({ id: "", name: "", label: "Concept", propsText: "{}" });
const editEdge = ref({ id: "", type: "RELATED_TO", src: "", dst: "", propsText: "{}" });

const linkMode = ref(false);
const linkDraft = ref({ src: "", dst: "", type: "RELATED_TO", propsText: "{}" });

function toastError(msg) {
  toastErr.value = msg;
  setTimeout(() => {
    if (toastErr.value === msg) toastErr.value = "";
  }, 6500);
}
function toastSuccess(msg) {
  toastOk.value = msg;
  setTimeout(() => {
    if (toastOk.value === msg) toastOk.value = "";
  }, 4500);
}

function safeParseJson(text) {
  try {
    return JSON.parse(text || "{}");
  } catch {
    throw new Error("Props 不是合法 JSON");
  }
}

const filteredEntities = computed(() => {
  const k = kw.value.trim();
  const base = entities.value.filter((n) => {
    const label = (n.label || "Concept").toString();
    if (nodeTab.value === "behaviors") return label === "Behavior";
    if (nodeTab.value === "rules") return label === "Rule";
    if (nodeTab.value === "states") return label === "State";
    if (nodeTab.value === "objects") return !["Behavior", "Rule", "State"].includes(label);
    return true;
  });
  if (!k) return base;
  return base.filter((n) => (n.name || "").includes(k) || (n.label || "").includes(k) || (n.id || "").includes(k));
});
const filteredRelations = computed(() => {
  const k = kw.value.trim();
  if (!k) return relations.value;
  return relations.value.filter((e) => (e.type || "").includes(k) || (e.id || "").includes(k) || (e.src || "").includes(k) || (e.dst || "").includes(k));
});

const onFile = (e) => (file.value = e.target.files?.[0] || null);

function clearSelection() {
  selected.value = null;
  highlightSelected();
}

function highlightSelected() {
  if (!cy.value) return;
  cy.value.elements().removeClass("selected");
  if (!selected.value) return;
  const ele = cy.value.getElementById(selected.value.id);
  if (ele) ele.addClass("selected");
}

function buildCy(nodes, edges) {
  const elements = [
    ...nodes.map((n) => ({ data: { id: n.id, name: n.name, label: n.label, props: n.props || {} } })),
    ...edges.map((e) => ({ data: { id: e.id, source: e.src, target: e.dst, type: e.type, props: e.props || {} } })),
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
          style: { "background-color": "#f59e0b" },
        },
        {
          selector: 'node[label = "Behavior"]',
          style: { "background-color": "#22c55e" },
        },
        {
          selector: 'node[label = "State"]',
          style: { "background-color": "#38bdf8" },
        },
        {
          selector: 'node[label = "Evidence"], node[label = "Artifact"]',
          style: { "background-color": "#a855f7" },
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

function relayout() {
  if (!cy.value) return;
  cy.value.layout({ name: "fcose", quality: "default", animate: true }).run();
}
function fit() {
  if (!cy.value) return;
  cy.value.fit(undefined, 30);
}

function selectNodeById(id) {
  let n = entities.value.find((x) => x.id === id);
  // 兜底：如果左侧列表没加载到该节点（例如 list limit / 只查询子图），从画布节点取数据
  if (!n && cy.value) {
    const ele = cy.value.getElementById(id);
    if (ele && ele.isNode && ele.isNode()) {
      const d = ele.data() || {};
      n = { id, name: d.name || "", label: d.label || "Concept", props: d.props || {} };
    }
  }
  if (!n) return;
  selected.value = { kind: "node", id };
  editNode.value = { id, name: n.name || "", label: n.label || "Concept", propsText: JSON.stringify(n.props || {}, null, 2) };
  highlightSelected();
}
function selectEdgeById(id) {
  let e = relations.value.find((x) => x.id === id);
  // 兜底：从画布关系取数据
  if (!e && cy.value) {
    const ele = cy.value.getElementById(id);
    if (ele && ele.isEdge && ele.isEdge()) {
      const d = ele.data() || {};
      e = { id, type: d.type || "RELATED_TO", src: d.source, dst: d.target, props: d.props || {} };
    }
  }
  if (!e) return;
  selected.value = { kind: "edge", id };
  editEdge.value = { id, type: e.type || "RELATED_TO", src: e.src, dst: e.dst, propsText: JSON.stringify(e.props || {}, null, 2) };
  highlightSelected();
}

function toggleLinkMode() {
  linkMode.value = !linkMode.value;
  linkDraft.value = { src: "", dst: "", type: "RELATED_TO", propsText: "{}" };
}

async function refresh() {
  loading.value = true;
  try {
    if (props.scope === "draft") {
      if (!props.draftId) {
        entities.value = [];
        relations.value = [];
        buildCy([], []);
        return;
      }
      const [en, re] = await Promise.all([
        fetch(`${props.apiBase}/ontology/drafts/${encodeURIComponent(props.draftId)}/entities`).then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.statusText)))),
        fetch(`${props.apiBase}/ontology/drafts/${encodeURIComponent(props.draftId)}/relations`).then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.statusText)))),
      ]);
      entities.value = en;
      relations.value = re;
      await runQuery();
      return;
    }

    const [en, re] = await Promise.all([
      fetch(`${props.apiBase}/ontology/entities`).then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.statusText)))),
      fetch(`${props.apiBase}/ontology/relations`).then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.statusText)))),
    ]);
    entities.value = en;
    relations.value = re;
    await runQuery();
  } catch (e) {
    toastError(`刷新失败: ${e}`);
  } finally {
    loading.value = false;
  }
}

async function runQuery() {
  const body = { root_id: query.value.root_id || null, depth: query.value.depth || 3 };
  if (props.scope === "draft") {
    if (!props.draftId) return;
    const res = await fetch(`${props.apiBase}/ontology/drafts/${encodeURIComponent(props.draftId)}/graph`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(await res.text());
    const g = await res.json();
    buildCy(g.nodes, g.edges);
    return;
  }

  const res = await fetch(`${props.apiBase}/ontology/graph`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  const g = await res.json();
  buildCy(g.nodes, g.edges);
}

async function extract() {
  if (!file.value) return;
  loading.value = true;
  const fd = new FormData();
  fd.append("file", file.value);
  try {
    const res = await fetch(`${props.apiBase}/ontology/extract`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    emit("draft-created", data.draft_id);
    toastSuccess(`草稿已生成：节点 ${data.nodes.length}，关系 ${data.edges.length}。`);
  } catch (e) {
    toastError(`抽取失败: ${e}`);
  } finally {
    loading.value = false;
  }
}

async function commitDraft() {
  if (!props.draftId) return;
  const ok = confirm("确认将草稿入库到正式图数据库吗？");
  if (!ok) return;
  loading.value = true;
  try {
    const res = await fetch(`${props.apiBase}/ontology/drafts/${encodeURIComponent(props.draftId)}/commit`, { method: "POST" });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    toastSuccess(`入库成功：节点 ${data.created_nodes}，关系 ${data.created_edges}`);
    emit("committed");
    emit("draft-cleared");
  } catch (e) {
    toastError(`入库失败: ${e}`);
  } finally {
    loading.value = false;
  }
}

async function cancelDraft() {
  if (!props.draftId) return;
  const ok = confirm("确认取消草稿？将删除临时图谱数据。");
  if (!ok) return;
  loading.value = true;
  try {
    const res = await fetch(`${props.apiBase}/ontology/drafts/${encodeURIComponent(props.draftId)}`, { method: "DELETE" });
    if (!res.ok) throw new Error(await res.text());
    toastSuccess("草稿已取消并清理");
    emit("draft-cleared");
  } catch (e) {
    toastError(`取消失败: ${e}`);
  } finally {
    loading.value = false;
  }
}

async function openCreateEntity() {
  const label =
    nodeTab.value === "behaviors"
      ? "Behavior"
      : nodeTab.value === "rules"
        ? "Rule"
        : nodeTab.value === "states"
          ? "State"
          : "Concept";
  const name = prompt(`请输入${label === "Concept" ? "对象" : label === "Behavior" ? "行为" : label === "Rule" ? "规则" : "状态"}名称：`);
  if (!name) return;
  loading.value = true;
  try {
    const url =
      props.scope === "draft"
        ? `${props.apiBase}/ontology/drafts/${encodeURIComponent(props.draftId)}/entities`
        : `${props.apiBase}/ontology/entities`;
    const propsTemplate =
      label === "Behavior"
        ? { source: "manual", preconditions: [], effects: [], inputs: [], outputs: [], version: "v1" }
        : label === "Rule"
          ? { source: "manual", trigger: "", action: "", approval_required: false, required_evidence: [] }
          : label === "State"
            ? { source: "manual", domain: "RiskState", meaning: "" }
            : { source: "manual", desc: "" };
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, label, props: propsTemplate }),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    await refresh();
    selectNodeById(data.id);
  } catch (e) {
    toastError(`新建实体失败: ${e}`);
  } finally {
    loading.value = false;
  }
}

const createBtnText = computed(() => {
  if (nodeTab.value === "behaviors") return "新建行为";
  if (nodeTab.value === "rules") return "新建规则";
  if (nodeTab.value === "states") return "新建状态";
  if (nodeTab.value === "objects") return "新建对象";
  return "新建";
});

async function createLink() {
  if (!linkDraft.value.src || !linkDraft.value.dst) return;
  const propsObj = safeParseJson(linkDraft.value.propsText);
  loading.value = true;
  try {
    const url =
      props.scope === "draft"
        ? `${props.apiBase}/ontology/drafts/${encodeURIComponent(props.draftId)}/relations`
        : `${props.apiBase}/ontology/relations`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ src: linkDraft.value.src, dst: linkDraft.value.dst, type: linkDraft.value.type || "RELATED_TO", props: propsObj }),
    });
    if (!res.ok) throw new Error(await res.text());
    await refresh();
    toggleLinkMode();
  } catch (e) {
    toastError(`创建关系失败: ${e}`);
  } finally {
    loading.value = false;
  }
}

async function saveNode() {
  const propsObj = safeParseJson(editNode.value.propsText);
  loading.value = true;
  try {
    const url =
      props.scope === "draft"
        ? `${props.apiBase}/ontology/drafts/${encodeURIComponent(props.draftId)}/entities/${encodeURIComponent(editNode.value.id)}`
        : `${props.apiBase}/ontology/entities/${encodeURIComponent(editNode.value.id)}`;
    const method = props.scope === "draft" ? "PUT" : "PUT";
    const res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: editNode.value.name, label: editNode.value.label, props: propsObj }),
    });
    if (!res.ok) throw new Error(await res.text());
    await refresh();
    selectNodeById(editNode.value.id);
    toastSuccess("保存成功");
  } catch (e) {
    toastError(`保存失败: ${e}`);
  } finally {
    loading.value = false;
  }
}

async function deleteNode() {
  const ok = confirm("确认删除该实体？相关关系也会被删除。");
  if (!ok) return;
  loading.value = true;
  try {
    const url =
      props.scope === "draft"
        ? `${props.apiBase}/ontology/drafts/${encodeURIComponent(props.draftId)}/entities/${encodeURIComponent(editNode.value.id)}`
        : `${props.apiBase}/ontology/entities/${encodeURIComponent(editNode.value.id)}`;
    const res = await fetch(url, { method: "DELETE" });
    if (!res.ok) throw new Error(await res.text());
    clearSelection();
    await refresh();
    toastSuccess("删除成功");
  } catch (e) {
    toastError(`删除失败: ${e}`);
  } finally {
    loading.value = false;
  }
}

async function saveEdge() {
  const propsObj = safeParseJson(editEdge.value.propsText);
  loading.value = true;
  try {
    const url =
      props.scope === "draft"
        ? `${props.apiBase}/ontology/drafts/${encodeURIComponent(props.draftId)}/relations/${encodeURIComponent(editEdge.value.id)}`
        : `${props.apiBase}/ontology/relations/${encodeURIComponent(editEdge.value.id)}`;
    const res = await fetch(url, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: editEdge.value.type, src: editEdge.value.src, dst: editEdge.value.dst, props: propsObj }),
    });
    if (!res.ok) throw new Error(await res.text());
    await refresh();
    selectEdgeById(editEdge.value.id);
    toastSuccess("保存成功");
  } catch (e) {
    toastError(`保存失败: ${e}`);
  } finally {
    loading.value = false;
  }
}

async function deleteEdge() {
  const ok = confirm("确认删除该关系？");
  if (!ok) return;
  loading.value = true;
  try {
    const url =
      props.scope === "draft"
        ? `${props.apiBase}/ontology/drafts/${encodeURIComponent(props.draftId)}/relations/${encodeURIComponent(editEdge.value.id)}`
        : `${props.apiBase}/ontology/relations/${encodeURIComponent(editEdge.value.id)}`;
    const res = await fetch(url, { method: "DELETE" });
    if (!res.ok) throw new Error(await res.text());
    clearSelection();
    await refresh();
    toastSuccess("删除成功");
  } catch (e) {
    toastError(`删除失败: ${e}`);
  } finally {
    loading.value = false;
  }
}

async function purgeAll() {
  const ok1 = confirm("危险操作：将清空【正式图谱 + 草稿图谱】的所有节点与关系，且不可恢复。确认继续？");
  if (!ok1) return;
  const ok2 = confirm("再次确认：你确定要清空整个图数据库吗？（不可恢复）");
  if (!ok2) return;
  loading.value = true;
  try {
    const res = await fetch(`${props.apiBase}/ontology/admin/purge?confirm=YES`, { method: "POST" });
    if (!res.ok) throw new Error(await res.text());
    toastSuccess("已清空图数据库");
    emit("purged");
  } catch (e) {
    toastError(`清空失败: ${e}`);
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  await refresh();
});

watch(
  () => props.draftId,
  async () => {
    if (props.scope === "draft") await refresh();
  }
);
watch(selected, () => highlightSelected());
</script>

<style scoped>
.panel-wrap {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.panel-header {
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
  font-weight: 900;
  font-size: 16px;
}
.subtitle {
  color: rgba(226, 232, 240, 0.7);
  font-size: 12px;
  margin-top: 2px;
}
.actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
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
  font-weight: 700;
}
.toast.ok {
  background: rgba(34, 211, 238, 0.12);
  border-color: rgba(34, 211, 238, 0.5);
  color: #ffffff;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.55);
}
.toast.err {
  background: rgba(239, 68, 68, 0.12);
  border-color: rgba(239, 68, 68, 0.5);
  color: #ffffff;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.55);
}

.body {
  display: grid;
  grid-template-columns: 320px 1fr 360px;
  gap: 12px;
  min-height: 520px;
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
  font-weight: 900;
}
.tabs {
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
  font-weight: 800;
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
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.25);
  gap: 10px;
}
.query {
  display: flex;
  gap: 8px;
  align-items: center;
}
.q {
  width: 180px;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(2, 6, 23, 0.35);
  color: #e2e8f0;
}
.q[type="number"] {
  width: 72px;
}
.toolbtns {
  display: flex;
  gap: 8px;
  align-items: center;
}
.legend {
  display: inline-flex;
  gap: 10px;
  padding-left: 6px;
  margin-left: 2px;
  border-left: 1px solid rgba(148, 163, 184, 0.25);
  color: rgba(226, 232, 240, 0.75);
  font-size: 12px;
  white-space: nowrap;
}
.lg-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  display: inline-block;
  box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.25);
}
.dot.behavior {
  background: #22c55e;
}
.dot.rule {
  background: #f59e0b;
}
.dot.state {
  background: #38bdf8;
}
.dot.evidence {
  background: #a855f7;
}
.dot.concept {
  background: #6366f1;
}
.hint {
  padding: 8px 12px;
  color: rgba(226, 232, 240, 0.65);
  font-size: 12px;
}
.graph {
  flex: 1;
  min-height: 440px;
  background:
    radial-gradient(1200px 600px at 50% 0%, rgba(99, 102, 241, 0.12), transparent 60%),
    radial-gradient(900px 500px at 20% 20%, rgba(34, 211, 238, 0.10), transparent 55%),
    linear-gradient(180deg, rgba(2, 6, 23, 0.85), rgba(2, 6, 23, 0.95));
}
.right label {
  display: block;
  font-weight: 800;
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

