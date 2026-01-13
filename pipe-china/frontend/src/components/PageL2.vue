<template>
  <div class="card">
    <h2>L2 本体/语义选型</h2>
    <p>上传需求文档 → 自动抽取实体/关系；可手动补充与图谱检索。</p>

    <div class="card">
      <h3>自动导入</h3>
      <div class="row">
        <div>
          <label>需求文档 (Markdown)</label>
          <input type="file" @change="onFile" accept=".md,.txt" />
        </div>
        <div>
          <label>操作</label>
          <button :disabled="!file || loading" @click="upload">上传并建模</button>
        </div>
      </div>
      <p v-if="importResult">已创建节点 {{ importResult.created_nodes }} 个，关系 {{ importResult.created_edges }} 个。</p>
      <pre v-if="importResult">{{ importResult }}</pre>
    </div>

    <div class="row">
      <div class="card">
        <h3>手动创建实体</h3>
        <label>名称</label>
        <input v-model="entityForm.name" placeholder="如：雨量站/管段A" />
        <label>标签</label>
        <input v-model="entityForm.label" placeholder="Concept/Asset" />
        <button :disabled="loading" @click="createEntity">创建</button>
      </div>
      <div class="card">
        <h3>手动创建关系</h3>
        <label>源节点ID</label>
        <input v-model="relForm.src" placeholder="ent-xxxx" />
        <label>目标节点ID</label>
        <input v-model="relForm.dst" placeholder="ent-xxxx" />
        <label>关系类型</label>
        <input v-model="relForm.type" placeholder="SERVES/LOCATED_IN" />
        <button :disabled="loading" @click="createRelation">创建</button>
      </div>
    </div>

    <div class="card">
      <h3>图谱查询</h3>
      <div class="row">
        <div>
          <label>根节点ID（可空，空则返回全局样例）</label>
          <input v-model="queryForm.root_id" placeholder="ent-xxxx" />
        </div>
        <div>
          <label>深度 (1-4)</label>
          <input type="number" v-model.number="queryForm.depth" min="1" max="4" />
        </div>
        <div>
          <label>&nbsp;</label>
          <button :disabled="loading" @click="runQuery">查询</button>
        </div>
      </div>

      <div class="row" v-if="graph.nodes.length">
        <div>
          <h4>节点</h4>
          <ul>
            <li v-for="n in graph.nodes" :key="n.id">
              {{ n.id }} · {{ n.name }} ({{ n.label }})
            </li>
          </ul>
        </div>
        <div>
          <h4>关系</h4>
          <ul>
            <li v-for="e in graph.edges" :key="e.id">
              {{ e.src }} -[{{ e.type }}]-> {{ e.dst }}
            </li>
          </ul>
        </div>
      </div>
    </div>

    <div class="card">
      <h3>检索</h3>
      <div class="row">
        <div>
          <label>关键词</label>
          <input v-model="searchKw" placeholder="泵站/雨量/风险" />
        </div>
        <div>
          <label>&nbsp;</label>
          <button :disabled="loading" @click="search">搜索</button>
        </div>
      </div>
      <ul>
        <li v-for="n in searchResult" :key="n.id">{{ n.id }} · {{ n.name }} ({{ n.label }})</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";

const props = defineProps({
  apiBase: { type: String, required: true },
});

const file = ref(null);
const loading = ref(false);
const importResult = ref(null);
const graph = ref({ nodes: [], edges: [] });
const searchResult = ref([]);

const entityForm = ref({ name: "", label: "Concept" });
const relForm = ref({ src: "", dst: "", type: "RELATED_TO" });
const queryForm = ref({ root_id: "", depth: 2 });
const searchKw = ref("");

const onFile = (e) => {
  file.value = e.target.files?.[0] || null;
};

const upload = async () => {
  if (!file.value) return;
  loading.value = true;
  const fd = new FormData();
  fd.append("file", file.value);
  try {
    const res = await fetch(`${props.apiBase}/ontology/import`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    importResult.value = await res.json();
  } catch (err) {
    alert(`导入失败: ${err}`);
  } finally {
    loading.value = false;
  }
};

const createEntity = async () => {
  if (!entityForm.value.name) return;
  loading.value = true;
  try {
    const res = await fetch(`${props.apiBase}/ontology/entities`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(entityForm.value),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    alert(`创建成功：${data.id}`);
  } catch (err) {
    alert(`创建失败: ${err}`);
  } finally {
    loading.value = false;
  }
};

const createRelation = async () => {
  if (!relForm.value.src || !relForm.value.dst) return;
  loading.value = true;
  try {
    const res = await fetch(`${props.apiBase}/ontology/relations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(relForm.value),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    alert(`创建关系成功：${data.id}`);
  } catch (err) {
    alert(`创建关系失败: ${err}`);
  } finally {
    loading.value = false;
  }
};

const runQuery = async () => {
  loading.value = true;
  try {
    const res = await fetch(`${props.apiBase}/ontology/graph`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(queryForm.value),
    });
    if (!res.ok) throw new Error(await res.text());
    graph.value = await res.json();
  } catch (err) {
    alert(`查询失败: ${err}`);
  } finally {
    loading.value = false;
  }
};

const search = async () => {
  if (!searchKw.value) return;
  loading.value = true;
  try {
    const res = await fetch(`${props.apiBase}/ontology/search?q=${encodeURIComponent(searchKw.value)}`);
    if (!res.ok) throw new Error(await res.text());
    searchResult.value = await res.json();
  } catch (err) {
    alert(`搜索失败: ${err}`);
  } finally {
    loading.value = false;
  }
};
</script>
