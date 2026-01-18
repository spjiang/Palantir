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
          <button class="btn" :disabled="!draftId || loading" @click="commitDraft">确认入正式图谱</button>
        </template>
        <template v-else>
          <button class="btn secondary" :disabled="loading" @click="refresh">刷新正式库</button>
          <button class="btn danger" :disabled="loading" @click="purgeAll">一键清空图数据库</button>
        </template>
      </div>
    </div>

    <div v-if="toastOk" class="toast ok">{{ toastOk }}</div>
    <div v-if="toastErr" class="toast err">{{ toastErr }}</div>
    <div class="stats" v-if="stats.totalNodes || stats.relations">
      <span class="st">行为 {{ stats.behaviors }}</span>
      <span class="st">规则 {{ stats.rules }}</span>
      <span class="st">状态 {{ stats.states }}</span>
      <span class="st">对象 {{ stats.objects }}</span>
      <span class="st">关系 {{ stats.relations }}</span>
    </div>
    <!-- 抽取流式面板：始终显示（不隐藏） -->
    <div class="body">
      <!-- graph (main) -->
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
            <template v-if="scope === 'draft'">
              <button class="btn secondary" :disabled="loading || !draftId" @click="refresh">刷新图谱</button>
              <button class="btn secondary" :disabled="loading || !draftId" @click="cancelDraft">清空图谱</button>
            </template>
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

      <!-- sidebar (data + inspector) -->
      <div class="sidebar">
        <div class="panel left">
          <div class="panel-title">本体数据</div>
          <div class="tabs">
            <button class="tab" :class="{ active: nodeTab === 'objects' }" @click="nodeTab = 'objects'">对象</button>
            <button class="tab" :class="{ active: nodeTab === 'relations' }" @click="nodeTab = 'relations'">关系</button>
            <button class="tab" :class="{ active: nodeTab === 'behaviors' }" @click="nodeTab = 'behaviors'">行为</button>
            <button class="tab" :class="{ active: nodeTab === 'rules' }" @click="nodeTab = 'rules'">规则</button>
            <button class="tab" :class="{ active: nodeTab === 'states' }" @click="nodeTab = 'states'">状态</button>
          </div>
          <input class="search" v-model="kw" placeholder="搜索名称/类型…" />

          <div class="list">
            <template v-if="nodeTab !== 'relations' && nodeTab !== 'states'">
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
            <template v-else-if="nodeTab === 'relations'">
              <div
                v-for="e in filteredRelations"
                :key="e.id"
                class="rowitem"
                :class="{ selected: selected?.kind === 'edge' && selected.id === e.id }"
                @click="selectEdgeById(e.id)"
              >
                <div class="row-title">{{ e.type }}</div>
                <div class="row-sub">{{ (e.src_name || e.src) }} → {{ (e.dst_name || e.dst) }}</div>
              </div>
            </template>
            <template v-else>
              <div v-for="t in filteredStateTransitions" :key="t.id" class="rowitem">
                <div class="row-title">{{ t.via || "状态迁移" }}</div>
                <div class="row-sub">{{ t.from }} → {{ t.to }}（{{ t.object }}）</div>
              </div>
            </template>
          </div>

        <div class="panel-footer">
          <button class="btn secondary" :disabled="loading || (scope==='draft' && !draftId) || nodeTab==='relations'" @click="openCreateEntityModal">
            {{ createBtnText }}
          </button>
          <button class="btn secondary" :disabled="loading || (scope==='draft' && !draftId)" @click="openCreateRelationModal">
            创建关系
          </button>
          <button class="btn secondary" :disabled="loading || (scope==='draft' && !draftId)" @click="toggleLinkMode">
            {{ linkMode ? '退出连线' : '连线创建' }}
          </button>
          </div>
        </div>

        <!-- 放在“本体数据区域下”（面板外部）：JSON 实时预览 -->
        <div class="json-preview-outer">
          <div class="json-preview" v-if="jsonPreview.open">
            <div class="json-preview-head">
              <div class="json-preview-title">JSON 实时预览</div>
              <div class="json-preview-sub">{{ streamPanel.stage || "接收中" }} · {{ jsonPreviewLen }} chars</div>
              <button class="btn secondary mini" :disabled="!jsonPreviewText" @click="copyJsonPreview">复制</button>
              <button class="btn secondary mini" @click="jsonPreview.open = false">收起</button>
            </div>
            <pre class="json-preview-body mono">{{ jsonPreviewText }}</pre>
          </div>
          <div class="json-preview-collapsed" v-else>
            <div class="json-preview-title">JSON 实时预览</div>
            <div class="json-preview-sub">{{ streamPanel.stage || "接收中" }} · {{ jsonPreviewLen }} chars</div>
            <button class="btn secondary mini" :disabled="!jsonPreviewText" @click="copyJsonPreview">复制</button>
            <button class="btn secondary mini" @click="jsonPreview.open = true">展开</button>
          </div>
        </div>
      </div>
    </div>

    <!-- create entity modal -->
    <div v-if="createModal.open" class="modal-backdrop" @click.self="closeCreateModal">
      <div class="modal">
        <div class="modal-title">{{ createBtnText }}</div>
        <div class="modal-sub">建议填写一个有意义的 ID（例如：beh-xxx / rule-xxx / state-xxx / obj-xxx）。不填则系统自动生成。</div>

        <label>ID（可选）</label>
        <input v-model="createModal.form.id" class="mono" placeholder="例如 beh-detect-anomaly" />

        <label>名称（必填）</label>
        <input v-model="createModal.form.name" placeholder="请输入名称" />

        <label>类型（label）</label>
        <input v-model="createModal.form.label" class="mono" readonly />

        <label>Props（JSON）</label>
        <textarea v-model="createModal.form.propsText" rows="10" class="mono"></textarea>

        <div class="btnrow">
          <button class="btn secondary" :disabled="loading" @click="closeCreateModal">取消</button>
          <button class="btn" :disabled="loading || !createModal.form.name.trim()" @click="createEntityFromModal">创建</button>
        </div>
      </div>
    </div>

    <!-- create relation modal -->
    <div v-if="createRelModal.open" class="modal-backdrop" @click.self="closeCreateRelModal">
      <div class="modal">
        <div class="modal-title">创建关系</div>
        <div class="modal-sub">建议填写一个有意义的关系 ID（例如：rel-xxx）。不填则系统自动生成。</div>

        <label>ID（可选）</label>
        <input v-model="createRelModal.form.id" class="mono" placeholder="例如 rel-beh-acts-on-seg" />

        <label>关系类型</label>
        <input v-model="createRelModal.form.type" placeholder="例如：作用于 / 产生 / 约束 / 需要证据" />

        <label>源节点</label>
        <select v-model="createRelModal.form.src">
          <option value="" disabled>请选择源节点</option>
          <option v-for="n in entities" :key="n.id" :value="n.id">{{ n.name }}（{{ n.label }} · {{ n.id }}）</option>
        </select>

        <label>目标节点</label>
        <select v-model="createRelModal.form.dst">
          <option value="" disabled>请选择目标节点</option>
          <option v-for="n in entities" :key="n.id" :value="n.id">{{ n.name }}（{{ n.label }} · {{ n.id }}）</option>
        </select>

        <label>Props（JSON）</label>
        <textarea v-model="createRelModal.form.propsText" rows="10" class="mono"></textarea>

        <div class="btnrow">
          <button class="btn secondary" :disabled="loading" @click="closeCreateRelModal">取消</button>
          <button class="btn" :disabled="loading || !createRelModal.form.src || !createRelModal.form.dst" @click="createRelationFromModal">创建</button>
        </div>
      </div>
    </div>

    <!-- confirm danger modal -->
    <div v-if="confirmModal.open" class="modal-backdrop" @click.self="closeConfirmModal">
      <div class="modal danger">
        <div class="modal-title">{{ confirmModal.title }}</div>
        <div class="modal-sub">{{ confirmModal.message }}</div>
        <div class="btnrow">
          <button class="btn secondary" :disabled="loading" @click="closeConfirmModal">取消</button>
          <button class="btn danger" :disabled="loading" @click="runConfirmAction">确认</button>
        </div>
      </div>
    </div>

    <!-- info modal -->
    <div v-if="infoModal.open" class="modal-backdrop" @click.self="closeInfoModal">
      <div class="modal">
        <div class="modal-title">{{ infoModal.title }}</div>
        <div class="modal-sub mono" style="white-space: pre-wrap">{{ infoModal.message }}</div>
        <div class="btnrow">
          <button class="btn" @click="closeInfoModal">我知道了</button>
        </div>
      </div>
    </div>

    <!-- editor modal (large) -->
    <div v-if="editorModal.open" class="modal-backdrop" @click.self="closeEditorModal">
      <div class="modal large">
        <div class="modal-title">属性编辑</div>
        <div class="modal-sub">对节点/关系做产品级编辑：支持大文本框、完整 JSON props，并保持 ID 不变。</div>

        <template v-if="selected?.kind === 'node'">
          <div class="kv">
            <div class="k">ID</div>
            <div class="v mono">{{ selected.id }}</div>
          </div>
          <label>名称</label>
          <input v-model="editNode.name" />
          <label>标签</label>
          <input v-model="editNode.label" class="mono" />
          <label>Props（JSON）</label>
          <textarea v-model="editNode.propsText" rows="18" class="mono"></textarea>
          <div class="btnrow">
            <button class="btn secondary" :disabled="loading" @click="closeEditorModal">关闭</button>
            <button class="btn" :disabled="loading" @click="saveNodeAndClose">保存</button>
            <button class="btn danger" :disabled="loading" @click="confirmDanger('deleteNode')">删除</button>
          </div>
        </template>

        <template v-else-if="selected?.kind === 'edge'">
          <div class="kv">
            <div class="k">ID</div>
            <div class="v mono">{{ selected.id }}</div>
          </div>
          <label>关系类型</label>
          <input v-model="editEdge.type" />
          <label>源节点</label>
          <select v-model="editEdge.src">
            <option v-for="n in entities" :key="n.id" :value="n.id">{{ n.name }}（{{ n.label }} · {{ n.id }}）</option>
          </select>
          <label>目标节点</label>
          <select v-model="editEdge.dst">
            <option v-for="n in entities" :key="n.id" :value="n.id">{{ n.name }}（{{ n.label }} · {{ n.id }}）</option>
          </select>
          <label>Props（JSON）</label>
          <textarea v-model="editEdge.propsText" rows="18" class="mono"></textarea>
          <div class="btnrow">
            <button class="btn secondary" :disabled="loading" @click="closeEditorModal">关闭</button>
            <button class="btn" :disabled="loading" @click="saveEdgeAndClose">保存</button>
            <button class="btn danger" :disabled="loading" @click="confirmDanger('deleteEdge')">删除</button>
          </div>
        </template>
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
const streamPanel = ref({
  open: false,
  stage: "",
  text: "",
  done: false,
  hasEverOpened: false,
  draftId: "",
  json: null,
  edit: null,
  userEdited: false,
  parseError: "",
  showRaw: false,
  showGenerated: false,
  generatedJson: "",
  partial: null,
  seen: null,
  parser: null,
  pendingClear: false,
});

// JSON 实时预览：默认显示完整内容（不截断）
// 如后续觉得太大影响性能，可把 maxChars 改为一个正数启用截断
const jsonPreview = ref({ open: true, maxChars: 0 });
const jsonPreviewLen = computed(() => (streamPanel.value.text || "").length);
const jsonPreviewText = computed(() => {
  const raw = streamPanel.value.text || "";
  const cleaned = cleanStreamJson(raw);
  if (!cleaned) return "";
  const max = Number(jsonPreview.value.maxChars || 0);
  if (max > 0 && cleaned.length > max) return cleaned.slice(0, max);
  return cleaned;
});

async function copyJsonPreview() {
  const text = jsonPreviewText.value || "";
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    toastSuccess("已复制 JSON 到剪贴板");
  } catch (e) {
    // 兼容性 fallback
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      ta.style.top = "0";
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      if (ok) toastSuccess("已复制 JSON 到剪贴板");
      else toastError("复制失败：浏览器不允许访问剪贴板");
    } catch {
      toastError("复制失败：浏览器不允许访问剪贴板");
    }
  }
}

function collapseStream() {
  streamPanel.value.open = false;
  streamPanel.value.hasEverOpened = true;
}
function expandStream() {
  streamPanel.value.open = true;
  streamPanel.value.hasEverOpened = true;
}

function resetStreamPanel() {
  // 仅当"二次上传"开始时清理；在首个 token 到来前保留旧数据展示
  streamPanel.value.open = true;
  streamPanel.value.stage = "调用中";
  streamPanel.value.text = "";
  streamPanel.value.done = false;
  streamPanel.value.hasEverOpened = true;
  streamPanel.value.draftId = "";
  streamPanel.value.json = null;
  streamPanel.value.userEdited = false;
  streamPanel.value.parseError = "";
  streamPanel.value.showRaw = false;
  streamPanel.value.showGenerated = false;
  streamPanel.value.partial = {
    entities: { scanPos: 0 },
    relations: { scanPos: 0 },
    rules: { scanPos: 0 },
    behaviors: { scanPos: 0 },
    state_transitions: { scanPos: 0 },
  };
  streamPanel.value.seen = {
    entities: new Set(),
    relations: new Set(),
    rules: new Set(),
    behaviors: new Set(),
    state_transitions: new Set(),
  };
  streamPanel.value.edit = {
    entities: [],
    relations: [],
    rules: [],
    behaviors: [],
    state_transitions: [],
  };
  streamPanel.value.generatedJson = "";
  streamPanel.value.pendingClear = true;
  // 清空右侧列表，准备接收新的流式数据
  entities.value = [];
  relations.value = [];
  stateTransitions.value = [];
  // 清空流式画布映射（name -> id、边去重、节流定时器）
  try {
    if (streamGraph.value.layoutTimer) clearTimeout(streamGraph.value.layoutTimer);
  } catch {
    // ignore
  }
  streamGraph.value = { nameToId: new Map(), edgeSig: new Set(), layoutTimer: null };
  // 清空图谱画布
  if (cy.value) {
    cy.value.elements().remove();
  }
  initStreamParser();
}

function initStreamParser() {
  streamPanel.value.parser = {
    // pendingKey/activeKey 用于识别正在解析哪个一级数组
    pendingKey: "",
    activeKey: "",
    bracketDepth: 0,
    // 字符串转义状态机（用于忽略字符串内部的 {}[]）
    inString: false,
    esc: false,
    // 当前对象花括号深度与缓冲
    objDepth: 0,
    objBuf: "",
    // 顶层 key 名识别（跨 token）：遇到 "xxx" 时收集 xxx
    collectingKey: false,
    keyName: "",
    // pendingKey 后，等待 '[' 的容错计数（避免误匹配）
    pendingTicks: 0,
  };
}

function hashStr(s) {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h) ^ s.charCodeAt(i);
  return (h >>> 0).toString(16);
}

function scheduleStreamRelayout() {
  if (!cy.value) return;
  if (streamGraph.value.layoutTimer) return;
  streamGraph.value.layoutTimer = setTimeout(() => {
    streamGraph.value.layoutTimer = null;
    try {
      cy.value.layout({ name: "fcose", quality: "default", animate: true }).run();
    } catch {
      // ignore
    }
  }, 700);
}

function ensureCyReady() {
  if (cy.value) return;
  if (!cyEl.value) return;
  buildCy([], []);
}

function addNodeToCyIfMissing(node) {
  if (!node?.id) return;
  ensureCyReady();
  if (!cy.value) return;
  const existed = cy.value.getElementById(node.id);
  const displayName = (node.name || "").toString().trim() || node.id;
  if (existed?.length) {
    // 升级占位节点（比如 Concept -> Sensor），更新 label/name/displayName/props
    existed.data("name", node.name || "");
    existed.data("displayName", displayName);
    existed.data("label", node.label || "Concept");
    existed.data("props", node.props || {});
  } else {
    cy.value.add({
      data: { id: node.id, name: node.name || "", displayName, label: node.label || "Concept", props: node.props || {} },
    });
  }
  scheduleStreamRelayout();
}

function addEdgeToCyIfMissing(edge) {
  if (!edge?.id) return;
  ensureCyReady();
  if (!cy.value) return;
  if (cy.value.getElementById(edge.id)?.length) return;
  if (!cy.value.getElementById(edge.src)?.length) return;
  if (!cy.value.getElementById(edge.dst)?.length) return;
  cy.value.add({ data: { id: edge.id, source: edge.src, target: edge.dst, type: edge.type || "RELATED_TO", props: edge.props || {} } });
  scheduleStreamRelayout();
}

function ensureStreamNodeByName(name, label = "Concept", props = {}) {
  const nm = (name || "").toString().trim();
  if (!nm) return "";
  const existed = streamGraph.value.nameToId.get(nm);
  if (existed) return existed;
  // 关键：流式阶段同一个“名字”只能对应一个临时节点 id（不能把 label 参与进来，否则会出现 Concept 占位 + 实体真实 label 两条重复）
  const id = `tmp-n-${hashStr(nm)}`;
  streamGraph.value.nameToId.set(nm, id);
  const idx = entities.value.findIndex((e) => e.id === id || e.name === nm);
  if (idx >= 0) {
    // 更新占位节点（比如从 Concept 升级成 Sensor/PipelineSegment）
    entities.value[idx] = { ...entities.value[idx], id, name: nm, label: label || entities.value[idx].label, props: props || entities.value[idx].props || {} };
  } else {
    entities.value.push({ id, name: nm, label, props: props || {} });
  }
  addNodeToCyIfMissing({ id, name: nm, label, props: props || {} });
  return id;
}

function addStreamObjectToUI(sectionKey, obj, rawStr) {
  if (!obj || typeof obj !== "object") return;

  // entities：对象列表（直接用 name/label/props）
  if (sectionKey === "entities") {
    const name = (obj.name || "").toString().trim();
    if (!name) return;
    const label = (obj.label || "Concept").toString().trim() || "Concept";
    // 用 nameToId 做统一 id（保证不会重复）；如果之前因为 relation 占位创建过节点，这里只做“更新”
    const id = streamGraph.value.nameToId.get(name) || `tmp-n-${hashStr(name)}`;
    streamGraph.value.nameToId.set(name, id);
    const idx = entities.value.findIndex((e) => e.id === id || e.name === name);
    const next = { id, name, label, props: obj.props || {} };
    if (idx >= 0) entities.value[idx] = { ...entities.value[idx], ...next };
    else entities.value.push(next);
    addNodeToCyIfMissing(next);
    return;
  }

  // relations：关系列表（type/src/dst/props）
  if (sectionKey === "relations") {
    const type = (obj.type || "RELATED_TO").toString().trim() || "RELATED_TO";
    const srcName = (obj.src || "").toString().trim();
    const dstName = (obj.dst || "").toString().trim();
    if (!srcName || !dstName) return;
    const srcId = streamGraph.value.nameToId.get(srcName) || ensureStreamNodeByName(srcName, "Concept", { source: "stream" });
    const dstId = streamGraph.value.nameToId.get(dstName) || ensureStreamNodeByName(dstName, "Concept", { source: "stream" });
    if (!srcId || !dstId) return;
    const sig = `${type}::${srcId}::${dstId}`;
    if (streamGraph.value.edgeSig.has(sig)) return;
    streamGraph.value.edgeSig.add(sig);
    const id = `tmp-rel-${hashStr(sig)}`;
    if (!relations.value.some((r) => r.id === id)) {
      relations.value.push({ id, type, src: srcId, dst: dstId, src_name: srcName, dst_name: dstName, props: obj.props || {} });
    }
    addEdgeToCyIfMissing({ id, type, src: srcId, dst: dstId, props: obj.props || {} });
    return;
  }

  // behaviors：行为（作为“节点”展示，label=Behavior）
  if (sectionKey === "behaviors") {
    const name = (obj.name || "").toString().trim();
    if (!name) return;
    const id = `tmp-beh-${hashStr(name)}`;
    if (!entities.value.some((e) => e.id === id)) {
      entities.value.push({ id, name, label: "Behavior", props: obj });
    }
    addNodeToCyIfMissing({ id, name, label: "Behavior", props: obj });
    return;
  }

  // rules：规则（作为“节点”展示，label=Rule）
  if (sectionKey === "rules") {
    const name = (obj.name || "").toString().trim();
    if (!name) return;
    const id = `tmp-rule-${hashStr(name)}`;
    if (!entities.value.some((e) => e.id === id)) {
      entities.value.push({ id, name, label: "Rule", props: obj });
    }
    addNodeToCyIfMissing({ id, name, label: "Rule", props: obj });
    return;
  }

  // state_transitions：状态迁移（按你的定义：属于“状态”tab）
  if (sectionKey === "state_transitions") {
    const from = (obj.from || "").toString().trim();
    const to = (obj.to || "").toString().trim();
    const via = (obj.via || "").toString().trim();
    const object = (obj.object || "").toString().trim();
    if (!from || !to) return;
    const id = `tmp-st-${hashStr(`${object}::${from}::${to}::${via}`)}`;
    if (!stateTransitions.value.some((t) => t.id === id)) {
      stateTransitions.value.push({ id, object, from, to, via, raw: rawStr || "" });
    }
  }
}

function processStreamChunk(chunkText) {
  if (!chunkText) return;
  const p = streamPanel.value.parser;
  if (!p) return;
  const KEYS = new Set(["entities", "relations", "behaviors", "rules", "state_transitions"]);

  for (let idx = 0; idx < chunkText.length; idx++) {
    const ch = chunkText[idx];

    // A) 正在收集顶层 key 名（"entities" 这种）
    if (p.collectingKey) {
      if (p.esc) {
        p.esc = false;
        p.keyName += ch;
        continue;
      }
      if (ch === "\\") {
        p.esc = true;
        continue;
      }
      if (ch === '"') {
        // key 结束
        p.collectingKey = false;
        if (KEYS.has(p.keyName)) {
          p.pendingKey = p.keyName;
          p.pendingTicks = 0;
        }
        p.keyName = "";
        continue;
      }
      p.keyName += ch;
      // 防御：过长直接放弃
      if (p.keyName.length > 64) {
        p.collectingKey = false;
        p.keyName = "";
      }
      continue;
    }

    // B) 字符串状态（仅用于对象内部：忽略字符串里的 {}[]）
    if (p.inString) {
      if (p.objDepth > 0) p.objBuf += ch;
      if (p.esc) {
        p.esc = false;
        continue;
      }
      if (ch === "\\") {
        p.esc = true;
        continue;
      }
      if (ch === '"') p.inString = false;
      continue;
    }

    // C) 遇到引号：如果在对象内，进入字符串；如果在顶层且未进入数组，开始收集 key 名
    if (ch === '"') {
      if (p.objDepth > 0) {
        p.inString = true;
        p.objBuf += ch;
      } else if (!p.activeKey) {
        // 只在未进入一级数组时尝试识别 key
        p.collectingKey = true;
        p.keyName = "";
      } else {
        // 在数组但不在对象内（理论上不会出现字符串值；兜底处理）
        p.inString = true;
      }
      continue;
    }

    // 3) 进入/退出一级数组
    if (!p.activeKey && p.pendingKey) {
      p.pendingTicks += 1;
      if (ch === "[") {
        p.activeKey = p.pendingKey;
        p.pendingKey = "";
        p.bracketDepth = 1;
        p.objDepth = 0;
        p.objBuf = "";
        p.pendingTicks = 0;
        continue;
      }
      // 允许 : 和空白，其他字符太多则放弃 pendingKey
      if (!/\s/.test(ch) && ch !== ":") {
        p.pendingKey = "";
        p.pendingTicks = 0;
      } else if (p.pendingTicks > 220) {
        p.pendingKey = "";
        p.pendingTicks = 0;
      }
    } else if (p.activeKey && p.objDepth === 0) {
      if (ch === "[") p.bracketDepth += 1;
      else if (ch === "]") {
        p.bracketDepth -= 1;
        if (p.bracketDepth <= 0) {
          p.activeKey = "";
          p.bracketDepth = 0;
          p.objDepth = 0;
          p.objBuf = "";
        }
      }
    }

    // 4) 在一级数组内，用 {} 花括号配对抽取对象
    if (p.activeKey) {
      if (ch === "{") {
        p.objDepth += 1;
        p.objBuf += ch;
        continue;
      }
      if (p.objDepth > 0) {
        p.objBuf += ch;
        if (ch === '"') {
          // 对象内部进入字符串
          p.inString = true;
          continue;
        }
        if (ch === "}") {
          p.objDepth -= 1;
          if (p.objDepth === 0) {
            const rawStr = p.objBuf;
            p.objBuf = "";
            try {
              const obj = JSON.parse(rawStr);
              addStreamObjectToUI(p.activeKey, obj, rawStr);
              // 一条对象完成就应当立即展示（便于验证）
              // console.log("[stream] added", p.activeKey, obj?.name || obj?.type || obj?.from);
            } catch {
              // 解析失败（例如尾逗号/未完全合法 JSON），忽略；后续 token 形成合法对象时会再次被提取
            }
          }
        }
      }
    }
  }
}

function clearStreamEdits() {
  streamPanel.value.edit = {
    entities: [],
    relations: [],
    rules: [],
    behaviors: [],
    state_transitions: [],
  };
  streamPanel.value.generatedJson = "";
}

function cleanStreamJson(raw) {
  let r = (raw || "").trim();
  r = r.replace(/^```json\s*/i, "");
  r = r.replace(/^```\s*/i, "");
  r = r.replace(/\s*```$/i, "");
  return r.trim();
}

function normalizeEditablePayload(payload) {
  const sections = ["entities", "relations", "rules", "behaviors", "state_transitions"];
  const out = {};
  for (const key of sections) {
    const list = Array.isArray(payload?.[key]) ? payload[key] : [];
    out[key] = list.map((item, idx) => ({
      __id: item?.id || item?.name || `${key}-${idx + 1}`,
      __obj: JSON.parse(JSON.stringify(item || {})),
      __text: JSON.stringify(item || {}, null, 2),
      __newKey: "",
      __newVal: "",
      __editing: false,
      __editValues: JSON.parse(JSON.stringify(item || {})),
      __error: "",
    }));
  }
  return out;
}

function tryParseStreamJson() {
  const raw = cleanStreamJson(streamPanel.value.text || "");
  if (!raw) return;
  try {
    const parsed = JSON.parse(raw);
    streamPanel.value.json = parsed;
    streamPanel.value.parseError = "";
    if (!streamPanel.value.userEdited) {
      streamPanel.value.edit = normalizeEditablePayload(parsed);
      updateGeneratedJson();
    }
  } catch (e) {
    streamPanel.value.parseError = "JSON 还未完整，继续解析中…";
  }
}

function extractObjectsFromArray(raw, key, state) {
  const results = [];
  const keyIdx = raw.indexOf(`"${key}"`);
  if (keyIdx < 0) return results;
  const arrStart = raw.indexOf("[", keyIdx);
  if (arrStart < 0) return results;

  let i = Math.max(state.scanPos || (arrStart + 1), arrStart + 1);
  let inStr = false;
  let esc = false;
  let depth = 0;
  let objStart = -1;
  for (; i < raw.length; i++) {
    const ch = raw[i];
    if (inStr) {
      if (esc) {
        esc = false;
        continue;
      }
      if (ch === "\\") {
        esc = true;
        continue;
      }
      if (ch === '"') {
        inStr = false;
      }
      continue;
    }
    if (ch === '"') {
      inStr = true;
      continue;
    }
    if (ch === "{") {
      if (depth === 0) objStart = i;
      depth += 1;
      continue;
    }
    if (ch === "}") {
      depth -= 1;
      if (depth === 0 && objStart >= 0) {
        const objStr = raw.slice(objStart, i + 1);
        try {
          results.push({ obj: JSON.parse(objStr), raw: objStr });
        } catch {
          // ignore incomplete
        }
        objStart = -1;
      }
      continue;
    }
    if (ch === "]" && depth === 0) {
      break;
    }
  }
  state.scanPos = i;
  return results;
}

function appendStreamObjects(sectionKey, items) {
  if (!items?.length) return;
  console.log(`[appendStreamObjects] ${sectionKey}: adding ${items.length} items, current entities.value.length=${entities.value.length}`);
  const list = streamPanel.value.edit?.[sectionKey] || [];
  const seen = streamPanel.value.seen?.[sectionKey];
  let added = 0;
  let addedToEntities = 0;
  let addedToRelations = 0;
  for (const it of items) {
    const signature = it.raw || JSON.stringify(it.obj || {});
    if (seen && seen.has(signature)) {
      console.log(`[appendStreamObjects] ${sectionKey}: skipping duplicate`, signature.substring(0, 50));
      continue;
    }
    seen?.add(signature);
    const newItem = {
      __id: it.obj?.id || it.obj?.name || `${sectionKey}-${list.length + 1}`,
      __obj: JSON.parse(JSON.stringify(it.obj || {})),
      __text: JSON.stringify(it.obj || {}, null, 2),
      __newKey: "",
      __newVal: "",
      __editing: false,
      __editValues: JSON.parse(JSON.stringify(it.obj || {})),
      __error: "",
    };
    list.push(newItem);
    added++;
    console.log(`[appendStreamObjects] ${sectionKey}: added item to edit list`, newItem.__id, newItem.__obj);
    
    // 实时添加到右侧列表：当检测到完整的对象时，立即显示到图谱画布右边的对象列表中
    // 处理 entities、behaviors、rules、state_transitions 等节点类型
    if ((sectionKey === "entities" || sectionKey === "behaviors" || sectionKey === "rules" || sectionKey === "state_transitions") && it.obj) {
      // 使用与 newItem 相同的 id 生成逻辑
      const entityId = newItem.__id;
      // 检查是否已存在（通过 id 去重）
      const exists = entities.value.some((e) => e.id === entityId);
      if (!exists) {
        // 根据 sectionKey 确定默认 label
        let defaultLabel = it.obj.label || "Concept";
        if (!it.obj.label) {
          if (sectionKey === "behaviors") defaultLabel = "Behavior";
          else if (sectionKey === "rules") defaultLabel = "Rule";
          else if (sectionKey === "state_transitions") defaultLabel = "State";
        }
        const entity = {
          id: entityId,
          name: it.obj.name || "",
          label: defaultLabel,
          props: it.obj.props || {},
        };
        entities.value.push(entity);
        addedToEntities++;
        console.log(`[appendStreamObjects] ✅ 实时添加到 entities.value:`, entity, `当前总数: ${entities.value.length}`);
      } else {
        console.log(`[appendStreamObjects] ⏭️ 跳过重复的 entity:`, entityId);
      }
    }
    
    // 实时添加到关系列表
    if (sectionKey === "relations" && it.obj) {
      // 使用与 newItem 相同的 id 生成逻辑，但 relations 可能没有 id，需要特殊处理
      const relationId = it.obj.id || `rel-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      // 检查是否已存在（通过 id 去重，如果没有 id 则通过 src+dst+type 去重）
      const exists = relations.value.some((r) => {
        if (r.id && relationId) return r.id === relationId;
        return r.src === it.obj.src && r.dst === it.obj.dst && r.type === (it.obj.type || "RELATED_TO");
      });
      if (!exists) {
        const relation = {
          id: relationId,
          type: it.obj.type || "RELATED_TO",
          src: it.obj.src || "",
          dst: it.obj.dst || "",
          props: it.obj.props || {},
        };
        relations.value.push(relation);
        addedToRelations++;
        console.log(`[appendStreamObjects] ✅ 实时添加到 relations.value:`, relation, `当前总数: ${relations.value.length}`);
      } else {
        console.log(`[appendStreamObjects] ⏭️ 跳过重复的 relation:`, relationId);
      }
    }
  }
  streamPanel.value.edit[sectionKey] = list;
  console.log(`[appendStreamObjects] ${sectionKey}: edit列表总数=${list.length}, 新增=${added}, 实时添加到entities=${addedToEntities}, 实时添加到relations=${addedToRelations}`);
  updateGeneratedJson();
}

function processStreamIncremental() {
  const raw = cleanStreamJson(streamPanel.value.text || "");
  if (!raw || !streamPanel.value.partial) return;
  console.log("[processStreamIncremental] raw text length:", raw.length, "first 200 chars:", raw.substring(0, 200));
  const keys = ["entities", "relations", "rules", "behaviors", "state_transitions"];
  for (const key of keys) {
    const state = streamPanel.value.partial[key];
    const items = extractObjectsFromArray(raw, key, state);
    console.log(`[processStreamIncremental] key=${key}, found ${items.length} new objects, scanPos=${state.scanPos}`);
    if (items.length > 0) {
      console.log(`[processStreamIncremental] ${key} first item:`, JSON.stringify(items[0].obj, null, 2));
    }
    if (items.length > 0) {
      appendStreamObjects(key, items);
    }
  }
}

function updateItemTextFromObj(item) {
  item.__text = JSON.stringify(item.__obj || {}, null, 2);
  updateGeneratedJson();
}

function markStreamEdited(item) {
  streamPanel.value.userEdited = true;
  try {
    JSON.parse(item.__text || "{}");
    item.__error = "";
  } catch {
    item.__error = "JSON 格式错误";
  }
  updateGeneratedJson();
}

function isObjectValue(v) {
  return v && typeof v === "object";
}

function formatJsonValue(v) {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v ?? "");
  }
}

const streamSections = [
  { key: "entities", title: "对象列表如下" },
  { key: "relations", title: "关系列表如下" },
  { key: "behaviors", title: "行为列表如下" },
  { key: "rules", title: "规则列表如下" },
  { key: "state_transitions", title: "状态迁移列表如下" },
];

function getSectionColumns(sectionKey) {
  const list = streamPanel.value.edit?.[sectionKey] || [];
  const preferred = {
    entities: ["name", "label", "props"],
    relations: ["type", "src", "dst", "props"],
    behaviors: ["name", "preconditions", "affects", "state_from", "state_to", "produces", "inputs", "outputs", "effects", "desc"],
    rules: ["name", "behavior", "trigger", "action", "approval_required", "sla_minutes", "required_evidence", "forbids", "allows", "involves"],
    state_transitions: ["object", "from", "to", "via"],
  };
  const order = preferred[sectionKey] || [];
  const keys = new Set();
  for (const it of list) {
    Object.keys(it.__obj || {}).forEach((k) => keys.add(k));
  }
  const rest = [...keys].filter((k) => !order.includes(k));
  return [...order.filter((k) => keys.has(k)), ...rest];
}

function getColumnLabel(sectionKey, col) {
  const labels = {
    entities: { name: "名称", label: "标签", props: "属性" },
    relations: { type: "类型", src: "源", dst: "目标", props: "属性" },
  };
  return labels?.[sectionKey]?.[col] || col;
}

function formatCell(val) {
  if (val === null || val === undefined) return "";
  if (typeof val === "object") return JSON.stringify(val);
  return String(val);
}

function startEditRow(item) {
  item.__editing = true;
  item.__editValues = JSON.parse(JSON.stringify(item.__obj || {}));
}

function cancelEditRow(item) {
  item.__editing = false;
  item.__editValues = JSON.parse(JSON.stringify(item.__obj || {}));
}

function saveEditRow(item) {
  item.__obj = JSON.parse(JSON.stringify(item.__editValues || {}));
  item.__editing = false;
  item.__error = "";
  updateItemTextFromObj(item);
}

function updateRowField(item, key, rawVal) {
  const current = item.__editValues?.[key];
  let next = rawVal;
  if (typeof current === "number") {
    const num = Number(rawVal);
    next = Number.isNaN(num) ? rawVal : num;
  } else if (typeof current === "boolean") {
    next = rawVal === "true" || rawVal === true;
  }
  item.__editValues[key] = next;
}

function updateRowFieldJson(item, key, rawVal) {
  try {
    item.__editValues[key] = rawVal ? JSON.parse(rawVal) : {};
    item.__error = "";
  } catch {
    item.__error = "字段 JSON 格式错误";
  }
}

function updateStreamField(item, key, rawVal) {
  const current = item.__obj?.[key];
  let next = rawVal;
  if (typeof current === "number") {
    const num = Number(rawVal);
    next = Number.isNaN(num) ? rawVal : num;
  } else if (typeof current === "boolean") {
    next = rawVal === "true" || rawVal === true;
  }
  item.__obj[key] = next;
  item.__error = "";
  updateItemTextFromObj(item);
}

function updateStreamFieldJson(item, key, rawVal) {
  try {
    const parsed = rawVal ? JSON.parse(rawVal) : {};
    item.__obj[key] = parsed;
    item.__error = "";
    updateItemTextFromObj(item);
  } catch {
    item.__error = "字段 JSON 格式错误";
  }
}

function addStreamField(item) {
  const k = (item.__newKey || "").trim();
  if (!k) return;
  item.__obj[k] = item.__newVal || "";
  item.__newKey = "";
  item.__newVal = "";
  item.__error = "";
  updateItemTextFromObj(item);
}

function parseEditableSection(list) {
  const parsed = [];
  let hasError = false;
  for (const item of list || []) {
    try {
      const obj = JSON.parse(item.__text || "{}");
      parsed.push(obj);
      item.__error = "";
    } catch {
      item.__error = "JSON 格式错误";
      hasError = true;
    }
  }
  return { parsed, hasError };
}

function buildFullJsonFromEdits() {
  if (!streamPanel.value.edit) return {};
  const parseSection = (list) => {
    const arr = [];
    for (const item of list || []) {
      try {
        arr.push(JSON.parse(item.__text || "{}"));
      } catch {
        // ignore parse error here; validation happens before apply
      }
    }
    return arr;
  };
  return {
    entities: parseSection(streamPanel.value.edit.entities),
    relations: parseSection(streamPanel.value.edit.relations),
    rules: parseSection(streamPanel.value.edit.rules),
    behaviors: parseSection(streamPanel.value.edit.behaviors),
    state_transitions: parseSection(streamPanel.value.edit.state_transitions),
  };
}

function updateGeneratedJson() {
  const obj = buildFullJsonFromEdits();
  streamPanel.value.generatedJson = JSON.stringify(obj, null, 2);
}

function deleteStreamItem(sectionKey, item) {
  streamPanel.value.userEdited = true;
  const list = streamPanel.value.edit?.[sectionKey] || [];
  const idx = list.indexOf(item);
  if (idx >= 0) list.splice(idx, 1);
  updateGeneratedJson();
}

async function applyStreamEditsToDraft() {
  if (!streamPanel.value.edit) return;
  const draftId = streamPanel.value.draftId || props.draftId;
  if (!draftId) {
    toastError("未找到 draftId，无法同步编辑结果");
    return;
  }
  const entitiesSection = parseEditableSection(streamPanel.value.edit.entities);
  const relationsSection = parseEditableSection(streamPanel.value.edit.relations);
  if (entitiesSection.hasError || relationsSection.hasError) {
    toastError("存在 JSON 格式错误，请先修正后再同步");
    return;
  }

  loading.value = true;
  try {
    if (!props.draftId && streamPanel.value.draftId) {
      emit("draft-created", streamPanel.value.draftId);
    }
    const nodeRequests = (entitiesSection.parsed || []).map((n) =>
      fetch(`${props.apiBase}/ontology/drafts/${encodeURIComponent(draftId)}/entities`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: n.id || null,
          name: n.name || "",
          label: n.label || "Concept",
          props: n.props || {},
        }),
      }).then(async (r) => {
        if (!r.ok) throw new Error(await r.text());
      })
    );

    const relRequests = (relationsSection.parsed || []).map((e) =>
      fetch(`${props.apiBase}/ontology/drafts/${encodeURIComponent(draftId)}/relations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: e.id || null,
          src: e.src,
          dst: e.dst,
          type: e.type || "RELATED_TO",
          props: e.props || {},
        }),
      }).then(async (r) => {
        if (!r.ok) throw new Error(await r.text());
      })
    );

    await Promise.all([...nodeRequests, ...relRequests]);
    toastSuccess("已将编辑后的 JSON 同步到草稿");
    await refresh();
  } catch (e) {
    toastError(`同步失败: ${e}`);
  } finally {
    loading.value = false;
  }
}

const entities = ref([]);
const relations = ref([]);
const stateTransitions = ref([]); // 对应提示词里的 state_transitions（状态）
const streamGraph = ref({
  nameToId: new Map(), // name -> nodeId
  edgeSig: new Set(), // `${type}::${srcId}::${dstId}`
  layoutTimer: null,
});
const nodeTab = ref("objects"); // objects | relations | behaviors | rules | states
const kw = ref("");
const query = ref({ root_id: "", depth: 3 });

const cyEl = ref(null);
const cy = ref(null);

const selected = ref(null); // {kind:'node'|'edge', id}
const editNode = ref({ id: "", name: "", label: "Concept", propsText: "{}" });
const editEdge = ref({ id: "", type: "RELATED_TO", src: "", dst: "", propsText: "{}" });

const linkMode = ref(false);
const linkDraft = ref({ src: "", dst: "", type: "RELATED_TO", propsText: "{}" });

function normLabel(label) {
  const l = (label || "Concept").toString().trim();
  if (l === "行为") return "Behavior";
  if (l === "规则") return "Rule";
  if (l === "状态") return "State";
  if (l === "证据") return "Evidence";
  if (l === "产物") return "Artifact";
  return l || "Concept";
}

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
    const label = normLabel(n.label);
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
const filteredStateTransitions = computed(() => {
  const k = kw.value.trim();
  if (!k) return stateTransitions.value;
  return stateTransitions.value.filter(
    (t) =>
      (t.object || "").includes(k) ||
      (t.from || "").includes(k) ||
      (t.to || "").includes(k) ||
      (t.via || "").includes(k)
  );
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
    ...nodes.map((n) => ({
      data: {
        id: n.id,
        name: n.name,
        displayName: ((n.name || "").toString().trim() || n.id),
        label: n.label,
        props: n.props || {},
      },
    })),
    ...edges.map((e) => ({ data: { id: e.id, source: e.src, target: e.dst, type: e.type, props: e.props || {} } })),
  ];
  const styleDef = [
    {
      selector: "node",
      style: {
        "background-color": "#6366f1",
        // 始终用 displayName（name 为空时兜底为 id）
        label: "data(displayName)",
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
      selector: 'node[label = "规则"]',
      style: { "background-color": "#f59e0b" },
    },
    {
      selector: 'node[label = "Behavior"]',
      style: { "background-color": "#22c55e" },
    },
    {
      selector: 'node[label = "行为"]',
      style: { "background-color": "#22c55e" },
    },
    {
      selector: 'node[label = "State"]',
      style: { "background-color": "#38bdf8" },
    },
    {
      selector: 'node[label = "状态"]',
      style: { "background-color": "#38bdf8" },
    },
    {
      selector: 'node[label = "Evidence"], node[label = "Artifact"]',
      style: { "background-color": "#a855f7" },
    },
    {
      selector: 'node[label = "证据"], node[label = "产物"]',
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
  ];

  if (!cy.value) {
    cy.value = cytoscape({
      container: cyEl.value,
      elements,
      style: styleDef,
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
        // 如果已选中同一节点但用户把弹窗关了，再点一次也要能重新打开
        if (selected.value?.kind === "node" && selected.value.id === id) {
          openEditorModal();
        } else {
          selectNodeById(id);
        }
      }
    });
    cy.value.on("tap", "edge", (evt) => {
      if (linkMode.value) return;
      const id = evt.target.id();
      if (selected.value?.kind === "edge" && selected.value.id === id) {
        openEditorModal();
      } else {
        selectEdgeById(id);
      }
    });
    cy.value.on("tap", (evt) => {
      if (evt.target === cy.value && !linkMode.value) clearSelection();
    });
  } else {
    cy.value.elements().remove();
    cy.value.add(elements);
    // 关键：cy 已存在时也要刷新 style（否则还是旧的 label:data(name)）
    cy.value.style(styleDef);
    // 给已有节点补 displayName（兼容旧数据）
    cy.value.nodes().forEach((n) => {
      const nm = (n.data("name") || "").toString().trim();
      n.data("displayName", nm || n.id());
    });
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
  // 选中后自动切换到对应 Tab，让列表“能看到”
  const nl = normLabel(n.label);
  if (nl === "Behavior") nodeTab.value = "behaviors";
  else if (nl === "Rule") nodeTab.value = "rules";
  else if (nl === "State") nodeTab.value = "states";
  else nodeTab.value = "objects";
  selected.value = { kind: "node", id };
  editNode.value = { id, name: n.name || "", label: n.label || "Concept", propsText: JSON.stringify(n.props || {}, null, 2) };
  highlightSelected();
  // 点击/选择就打开编辑弹窗（避免同一节点再次点击时 watch 不触发）
  openEditorModal();
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
  openEditorModal();
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
    // 高级感：流式实时展示 DeepSeek 抽取过程（SSE over fetch stream）
    resetStreamPanel();
    const res = await fetch(`${props.apiBase}/ontology/extract/stream`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    if (!res.body) throw new Error("浏览器不支持流式读取");
    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buf = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      // SSE 分段：以 \n\n 结束
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const chunk = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const lines = chunk.split("\n").map((x) => x.trimEnd());
        let ev = "message";
        let dataLine = "";
        for (const ln of lines) {
          if (ln.startsWith("event:")) ev = ln.slice(6).trim();
          if (ln.startsWith("data:")) dataLine += ln.slice(5).trim();
        }
        if (!dataLine) continue;
        const payload = JSON.parse(dataLine);
        if (ev === "status") {
          streamPanel.value.stage = payload.message || payload.stage || "调用中";
        } else if (ev === "token") {
          if (streamPanel.value.pendingClear) {
            console.log("[extract] First token received, clearing old data");
            clearStreamEdits();
            streamPanel.value.pendingClear = false;
          }
          const tokenText = payload.text || "";
          console.log("[extract] Received token:", tokenText.substring(0, 100));
          streamPanel.value.text += tokenText;
          console.log("[extract] Total text length:", streamPanel.value.text.length);
          // 按提示词：动态获取字符串，依据 JSON 规则（{}成对）实时抽取每个 list 的对象并更新右侧列表
          processStreamChunk(tokenText);
          tryParseStreamJson();
        } else if (ev === "done") {
          streamPanel.value.stage = "完成";
          streamPanel.value.done = true;
          streamPanel.value.hasEverOpened = true;
          streamPanel.value.draftId = payload.draft_id || "";
          // 关键：把 draftId 回传给父组件（Draft.vue 存 sessionStorage + 传回 props.draftId）
          // 否则“刷新草稿/图查询/确认入正式图谱”会因为 props.draftId 为空而把画布清空
          if (props.scope === "draft" && streamPanel.value.draftId && streamPanel.value.draftId !== props.draftId) {
            emit("draft-created", streamPanel.value.draftId);
          }
          if (!streamPanel.value.userEdited) {
            streamPanel.value.json = payload;
            streamPanel.value.edit = normalizeEditablePayload(payload);
            streamPanel.value.parseError = "";
            updateGeneratedJson();
          }
          // done 后切换为“真实 draft 图”（带稳定 id），便于画布/编辑/入库
          if (payload.nodes && Array.isArray(payload.nodes)) entities.value = payload.nodes;
          if (payload.edges && Array.isArray(payload.edges)) relations.value = payload.edges;
          if (payload.nodes && Array.isArray(payload.nodes) && payload.edges && Array.isArray(payload.edges)) {
            buildCy(payload.nodes, payload.edges);
          }
          toastSuccess("抽取完成：请在下方编辑后点击「确认入正式图谱（草稿图谱）」。");
        } else if (ev === "error") {
          throw new Error(payload.message || JSON.stringify(payload));
        }
      }
    }
  } catch (e) {
    toastError(`抽取失败: ${e}`);
  } finally {
    loading.value = false;
  }
}

async function commitDraft() {
  if (!props.draftId) return;
  confirmDanger("commitDraft");
  return;
}

async function cancelDraft() {
  if (!props.draftId) return;
  confirmDanger("cancelDraft");
  return;
}

function openCreateEntityModal() {
  const label =
    nodeTab.value === "behaviors"
      ? "Behavior"
      : nodeTab.value === "rules"
        ? "Rule"
        : nodeTab.value === "states"
          ? "State"
          : "Concept";
  const propsTemplate =
    label === "Behavior"
      ? { source: "manual", preconditions: [], effects: [], inputs: [], outputs: [], version: "v1" }
      : label === "Rule"
        ? { source: "manual", trigger: "", action: "", approval_required: false, required_evidence: [] }
        : label === "State"
          ? { source: "manual", domain: "RiskState", meaning: "" }
          : { source: "manual", desc: "" };
  createModal.value = {
    open: true,
    form: { id: "", name: "", label, propsText: JSON.stringify(propsTemplate, null, 2) },
  };
}

function closeCreateModal() {
  createModal.value.open = false;
}

async function createEntityFromModal() {
  const label = createModal.value.form.label;
  const name = createModal.value.form.name.trim();
  const id = (createModal.value.form.id || "").trim() || null;
  const propsObj = safeParseJson(createModal.value.form.propsText);
  loading.value = true;
  try {
    const url =
      props.scope === "draft"
        ? `${props.apiBase}/ontology/drafts/${encodeURIComponent(props.draftId)}/entities`
        : `${props.apiBase}/ontology/entities`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, name, label, props: propsObj }),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    await refresh();
    selectNodeById(data.id);
    toastSuccess(`创建成功：${data.name}（ID=${data.id}）`);
    closeCreateModal();
  } catch (e) {
    toastError(`新建对象失败: ${e}`);
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

const stats = computed(() => {
  const totalNodes = entities.value.length;
  // 关系：只统计 relations（不要把 state_transitions 混入关系）
  const relationsCount = relations.value.length;
  const behaviors = entities.value.filter((n) => normLabel(n.label) === "Behavior").length;
  const rules = entities.value.filter((n) => normLabel(n.label) === "Rule").length;
  // 按提示词：state_transitions 就是“状态”数据
  const states = stateTransitions.value.length;
  // 仍然从节点中扣除 Behavior/Rule/State（如有）以计算“对象”数
  const stateNodes = entities.value.filter((n) => normLabel(n.label) === "State").length;
  const objects = Math.max(0, totalNodes - behaviors - rules - stateNodes);
  return { totalNodes, relations: relationsCount, behaviors, rules, states, objects };
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
      body: JSON.stringify({
        id: null,
        src: linkDraft.value.src,
        dst: linkDraft.value.dst,
        type: linkDraft.value.type || "RELATED_TO",
        props: propsObj,
      }),
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
  confirmDanger("purgeAll");
  return;
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

const createModal = ref({
  open: false,
  form: { id: "", name: "", label: "Concept", propsText: "{}" },
});

const createRelModal = ref({
  open: false,
  form: { id: "", type: "作用于", src: "", dst: "", propsText: "{}" },
});

const confirmModal = ref({
  open: false,
  title: "确认操作",
  message: "",
  action: null,
});

function closeConfirmModal() {
  confirmModal.value.open = false;
  confirmModal.value.action = null;
}

function openCreateRelationModal() {
  // 尝试用当前“连线草稿”预填 src/dst
  const src = linkDraft.value.src || "";
  const dst = linkDraft.value.dst || "";
  createRelModal.value = {
    open: true,
    form: { id: "", type: "作用于", src, dst, propsText: JSON.stringify({ source: "manual" }, null, 2) },
  };
}

function closeCreateRelModal() {
  createRelModal.value.open = false;
}

async function createRelationFromModal() {
  const id = (createRelModal.value.form.id || "").trim() || null;
  const type = (createRelModal.value.form.type || "").trim() || "RELATED_TO";
  const src = createRelModal.value.form.src;
  const dst = createRelModal.value.form.dst;
  const propsObj = safeParseJson(createRelModal.value.form.propsText);
  loading.value = true;
  try {
    const url =
      props.scope === "draft"
        ? `${props.apiBase}/ontology/drafts/${encodeURIComponent(props.draftId)}/relations`
        : `${props.apiBase}/ontology/relations`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, src, dst, type, props: propsObj }),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    await refresh();
    selectEdgeById(data.id);
    toastSuccess(`创建关系成功：${data.type}（ID=${data.id}）`);
    closeCreateRelModal();
  } catch (e) {
    toastError(`创建关系失败: ${e}`);
  } finally {
    loading.value = false;
  }
}

function confirmDanger(action) {
  const map = {
    deleteNode: { title: "删除对象", message: "确认删除该对象？相关关系也会被删除。", action: deleteNode },
    deleteEdge: { title: "删除关系", message: "确认删除该关系？", action: deleteEdge },
    cancelDraft: { title: "清空图谱", message: "确认清空当前草稿图谱？将删除临时图谱数据，且不可恢复。", action: cancelDraftDo },
    commitDraft: { title: "确认入正式图谱", message: "确认将草稿写入正式图谱吗？写入后草稿将被清理。", action: commitDraftDo },
    purgeAll: { title: "清空图数据库", message: "危险：将清空【正式图谱 + 草稿图谱】的所有节点与关系，且不可恢复。", action: purgeAllDo },
  };
  const item = map[action];
  if (!item) return;
  confirmModal.value = { open: true, title: item.title, message: item.message, action: item.action };
}

async function runConfirmAction() {
  const fn = confirmModal.value.action;
  closeConfirmModal();
  if (typeof fn === "function") await fn();
}

// 将需要确认的操作拆出，避免递归 confirm
async function commitDraftDo() {
  // 前端先校验，避免无意义请求：每个行为必须至少挂 1 个对象
  const issues = validateBehaviorsMounted();
  if (issues.length) {
    openInfoModal(
      "写入正式图谱校验未通过",
      "以下行为未挂载任何对象（请为每个行为创建“作用于/适用对象”关系后再写入正式图谱）：\n- " + issues.join("\n- ")
    );
    return;
  }
  loading.value = true;
  try {
    const res = await fetch(`${props.apiBase}/ontology/drafts/${encodeURIComponent(props.draftId)}/commit`, { method: "POST" });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    toastSuccess(`写入正式图谱成功：节点 ${data.created_nodes}，关系 ${data.created_edges}`);
    emit("committed");
    emit("draft-cleared");
  } catch (e) {
    toastError(`写入正式图谱失败: ${e}`);
  } finally {
    loading.value = false;
  }
}

async function cancelDraftDo() {
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

async function purgeAllDo() {
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

function validateBehaviorsMounted() {
  const byId = new Map(entities.value.map((n) => [n.id, n]));
  const behaviors = entities.value.filter((n) => (n.label || "") === "Behavior");
  if (!behaviors.length) return [];

  const nonObjectLabels = new Set(["Behavior", "Rule", "State", "Evidence", "Artifact"]);
  const okTypes = new Set(["作用于", "适用对象", "AFFECTS", "APPLIES_TO"]);
  const issues = [];

  for (const b of behaviors) {
    const outs = relations.value.filter((e) => e.src === b.id && okTypes.has(e.type || ""));
    const hasObj = outs.some((e) => {
      const dst = byId.get(e.dst);
      if (!dst) return false;
      return !nonObjectLabels.has(dst.label || "Concept");
    });
    if (!hasObj) issues.push(`${b.name}（${b.id}）`);
  }
  return issues;
}

const infoModal = ref({ open: false, title: "", message: "" });
function openInfoModal(title, message) {
  infoModal.value = { open: true, title, message };
}
function closeInfoModal() {
  infoModal.value.open = false;
}

const editorModal = ref({ open: false });
function openEditorModal() {
  editorModal.value.open = true;
}
function closeEditorModal() {
  editorModal.value.open = false;
}
async function saveNodeAndClose() {
  await saveNode();
  closeEditorModal();
}
async function saveEdgeAndClose() {
  await saveEdge();
  closeEditorModal();
}

// 选中节点/关系时由 selectNodeById/selectEdgeById 主动打开弹窗；
// 这样“再次点击同一个节点”也能重新打开，不依赖 selected.id 变化。
</script>

<style scoped>
.panel-wrap {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px; /* 更紧凑 */
  border: 1px solid rgba(148, 163, 184, 0.20);
  border-radius: 12px;
  background:
    radial-gradient(900px 300px at 20% 0%, rgba(34, 211, 238, 0.14), transparent 62%),
    radial-gradient(900px 300px at 80% 0%, rgba(99, 102, 241, 0.16), transparent 62%),
    linear-gradient(180deg, rgba(12, 30, 70, 0.78), rgba(6, 18, 42, 0.72));
  color: #e2e8f0;
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.22);
}
.title {
  font-weight: 900;
  font-size: 15px;
}
.subtitle {
  color: rgba(226, 232, 240, 0.7);
  font-size: 12px;
  margin-top: 2px;
}
.actions {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
}
.file {
  width: 220px;
}
.btn {
  padding: 7px 10px; /* 更紧凑 */
  border-radius: 10px;
  border: none;
  background: linear-gradient(90deg, rgba(34, 211, 238, 0.92), rgba(99, 102, 241, 0.88));
  color: #08101f;
  cursor: pointer;
  font-weight: 800;
  font-size: 13px;
}
.btn.secondary {
  background: rgba(148, 163, 184, 0.12);
  color: #e2e8f0;
  border: 1px solid rgba(148, 163, 184, 0.35);
}
.btn.danger {
  background: linear-gradient(90deg, rgba(239, 68, 68, 0.92), rgba(251, 113, 133, 0.82));
  color: #12060a;
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
.stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  background: rgba(2, 6, 23, 0.35);
  color: rgba(226, 232, 240, 0.9);
  font-size: 12px;
}
.st {
  padding: 4px 8px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(148, 163, 184, 0.08);
}
.stream {
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 12px;
  background: rgba(6, 18, 42, 0.52);
  overflow: hidden;
}
.stream-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.15);
  color: rgba(226, 232, 240, 0.9);
}
.stream-actions {
  display: flex;
  gap: 6px;
  align-items: center;
}
.stream-title {
  font-weight: 900;
}
.stream-stage {
  font-size: 12px;
  color: rgba(226, 232, 240, 0.7);
  flex: 1;
  text-align: center;
}
.stream-body {
  max-height: 220px;
  overflow: auto;
  padding: 10px 12px;
  white-space: pre-wrap;
  color: rgba(226, 232, 240, 0.85);
}
.stream-json {
  padding: 10px 12px 12px;
  display: grid;
  gap: 12px;
}
.json-hint {
  font-size: 12px;
  color: rgba(226, 232, 240, 0.7);
}
.json-section {
  border: 1px solid rgba(34, 211, 238, 0.16);
  border-radius: 12px;
  padding: 10px;
  background: rgba(6, 18, 42, 0.42);
  box-shadow: 0 0 24px rgba(34, 211, 238, 0.08);
}
.json-section-title {
  font-weight: 900;
  font-size: 13px;
  margin-bottom: 8px;
  color: rgba(226, 232, 240, 0.92);
}
.json-table-wrap {
  width: 100%;
  overflow: auto;
}
.json-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  color: rgba(226, 232, 240, 0.9);
}
.json-table th,
.json-table td {
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
  padding: 6px 8px;
  text-align: left;
  vertical-align: top;
}
.json-table th {
  color: rgba(226, 232, 240, 0.75);
  font-weight: 800;
  background: rgba(10, 26, 58, 0.5);
}
.json-col-actions,
.json-actions-col {
  width: 140px;
  white-space: nowrap;
}
.json-cell-text {
  display: inline-block;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.json-cell-input {
  width: 100%;
  min-width: 120px;
  padding: 6px 8px;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  background: rgba(6, 18, 42, 0.4);
  color: rgba(226, 232, 240, 0.95);
  box-sizing: border-box;
}
.json-actions {
  display: flex;
  gap: 6px;
}
.json-error {
  color: #fecaca;
}
.stream-collapsed {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 12px;
  background: rgba(2, 6, 23, 0.42);
  color: rgba(226, 232, 240, 0.9);
}
.stream-hint {
  font-size: 12px;
  color: rgba(226, 232, 240, 0.72);
}
.stream-collapsed .btn.secondary {
  color: rgba(226, 232, 240, 0.9);
  border-color: rgba(148, 163, 184, 0.28);
  background: rgba(148, 163, 184, 0.10);
}
.btn.mini {
  padding: 5px 9px;
  border-radius: 10px;
  font-size: 12px;
}
.cursor {
  display: inline-block;
  margin-left: 2px;
  animation: blink 1s steps(2, start) infinite;
}
@keyframes blink {
  to {
    opacity: 0;
  }
}

/* ---------- Modals (产品级弹窗) ---------- */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(2, 6, 23, 0.72);
  backdrop-filter: blur(6px);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 18px;
}
.modal {
  width: min(720px, calc(100vw - 24px));
  max-height: calc(100vh - 48px);
  overflow: auto;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.98), rgba(2, 6, 23, 0.98));
  box-shadow: 0 30px 80px rgba(0, 0, 0, 0.45);
  padding: 14px 14px 12px;
  color: #e2e8f0;
}
.modal.large {
  width: min(980px, calc(100vw - 24px));
}
.modal.danger {
  border-color: rgba(239, 68, 68, 0.45);
}
.modal-title {
  font-weight: 900;
  font-size: 16px;
  margin-bottom: 6px;
}
.modal-sub {
  color: rgba(226, 232, 240, 0.7);
  font-size: 12px;
  line-height: 1.55;
  margin-bottom: 10px;
}
.modal label {
  display: block;
  font-weight: 800;
  margin: 10px 0 6px;
}
.modal input,
.modal textarea {
  width: 100%;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(2, 6, 23, 0.35);
  color: #e2e8f0;
  box-sizing: border-box;
}

.body {
  display: grid;
  grid-template-columns: 1fr 440px;
  gap: 12px;
  /* 更高的工作区：让画布与右侧列表/编辑区都能显示更多内容 */
  height: clamp(680px, calc(100vh - 200px), 980px);
  min-height: 680px;
}
.sidebar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 520px;
  height: 100%;
}
.sidebar .panel {
  min-height: 0;
}
.sidebar .left {
  flex: 1;
  height: 100%;
}
.json-preview-outer {
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  background: rgba(2, 6, 23, 0.18);
  overflow: hidden;
}
.panel {
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.92), rgba(2, 6, 23, 0.92));
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  color: #e2e8f0;
  min-height: 0; /* 允许子元素滚动，不撑开父容器 */
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
  flex: 1;
  min-height: 0;
}

.json-preview,
.json-preview-collapsed {
  margin: 0 12px 10px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(2, 6, 23, 0.35);
  overflow: hidden;
}
.json-preview-head {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 8px 10px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}
.json-preview-title {
  font-weight: 900;
  font-size: 12px;
  color: rgba(226, 232, 240, 0.92);
}
.json-preview-sub {
  flex: 1;
  font-size: 12px;
  color: rgba(226, 232, 240, 0.65);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.json-preview-body {
  max-height: 160px;
  overflow: auto;
  padding: 10px;
  margin: 0;
  font-size: 12px;
  line-height: 1.45;
  color: rgba(226, 232, 240, 0.88);
  background: rgba(2, 6, 23, 0.22);
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
  position: relative;
  z-index: 5;
  overflow: visible;
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
  flex-wrap: wrap;
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
  position: relative;
  z-index: 10;
  background: rgba(2, 6, 23, 0.55);
  padding: 6px 10px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.18);
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
  min-height: 600px;
  position: relative;
  z-index: 1;
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
.right {
  overflow: auto;
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

