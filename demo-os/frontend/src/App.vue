<template>
  <div class="wrap">
    <header class="hdr">
      <div class="title">城市暴雨内涝指挥（演示级）</div>
      <div class="meta">
        <span>API: {{ apiBase }}</span>
        <span>智能体: {{ agentBase }}</span>
      </div>
    </header>

    <main class="grid">
      <section class="card">
        <h3>1) 风险热力图（简化为 TopN 列表）</h3>
        <div class="row">
          <label>区域</label>
          <input v-model="areaId" />
          <button @click="loadTopN">刷新 TopN</button>
        </div>
        <table class="tbl">
          <thead>
            <tr>
              <th>对象</th>
              <th>等级</th>
              <th>分数</th>
              <th>置信度</th>
              <th>解释因子</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="it in topN" :key="it.target_id" @click="pickTarget(it.target_id)">
              <td>{{ it.target_id }}</td>
              <td>{{ it.risk_level }}</td>
              <td>{{ it.risk_score.toFixed(2) }}</td>
              <td>{{ it.confidence.toFixed(2) }}</td>
              <td class="muted">{{ (it.explain_factors || []).slice(0, 3).join(" / ") }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="card">
        <h3>2) 暴雨参谋长智能体（对话）</h3>
        <div class="row">
          <label>事件ID</label>
          <input v-model="incidentId" placeholder="留空自动创建" />
          <button @click="createIncident">新建事件</button>
        </div>
        <textarea v-model="chatInput" rows="4" placeholder="输入：例如“请研判并一键下发任务包”"></textarea>
        <div class="row">
          <button @click="sendChat">发送</button>
          <button class="ghost" @click="chatInput = '请研判并一键下发任务包'">一键派单口令</button>
        </div>
        <div class="box">
          <div class="muted">智能体输出：</div>
          <pre class="pre">{{ agentOut }}</pre>
        </div>
      </section>

      <section class="card">
        <h3>3/4) 任务与回执</h3>
        <div class="row">
          <button @click="loadTasks" :disabled="!incidentId">加载任务</button>
          <button class="ghost" @click="ackAllDone" :disabled="tasks.length === 0">一键回执完成</button>
        </div>
        <table class="tbl">
          <thead>
            <tr>
              <th>任务ID</th>
              <th>类型</th>
              <th>目标</th>
              <th>责任单位</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in tasks" :key="t.task_id">
              <td class="muted">{{ t.task_id }}</td>
              <td>{{ t.task_type }}</td>
              <td>{{ t.target_object_id }}</td>
              <td>{{ t.owner_org }}</td>
              <td>{{ t.status }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="card">
        <h3>5) 战报</h3>
        <div class="row">
          <button @click="loadReport" :disabled="!incidentId">生成战报</button>
        </div>
        <pre class="pre">{{ reportOut }}</pre>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import axios from "axios";
import { ref } from "vue";

const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const agentBase = import.meta.env.VITE_AGENT_BASE_URL || "http://localhost:8001";

const areaId = ref("A-001");
const incidentId = ref<string>("");

const topN = ref<any[]>([]);
const tasks = ref<any[]>([]);

const chatInput = ref("请研判并一键下发任务包");
const agentOut = ref("");
const reportOut = ref("");

async function loadTopN() {
  const { data } = await axios.get(`${apiBase}/risk/topn`, { params: { area_id: areaId.value, n: 5 } });
  topN.value = data.items || [];
}

function pickTarget(targetId: string) {
  chatInput.value = `请研判 ${targetId} 并给出任务包建议`;
}

async function createIncident() {
  const { data } = await axios.post(`${apiBase}/workflow/incidents`, { area_id: areaId.value, title: "城市暴雨内涝处置事件（演示）" });
  incidentId.value = data.incident_id;
}

async function sendChat() {
  agentOut.value = "请求中...";
  const { data } = await axios.post(`${agentBase}/agent/chat`, {
    incident_id: incidentId.value || null,
    area_id: areaId.value,
    message: chatInput.value,
  });
  agentOut.value = JSON.stringify(data, null, 2);
  // 若智能体自动创建了事件
  if (!incidentId.value) {
    // 从 tasks 里推断不到，这里就用后端的“最新事件”能力简化：直接再新建一个事件让用户可控
    // 演示：如果智能体触发派单，用户通常会先点“新建事件”；这里保持简单不反推。
  }
}

async function loadTasks() {
  const { data } = await axios.get(`${apiBase}/workflow/incidents/${incidentId.value}/tasks`);
  tasks.value = data;
}

async function ackAllDone() {
  for (const t of tasks.value) {
    await axios.post(`${apiBase}/workflow/tasks/${t.task_id}/ack`, {
      actor: "demo-mobile",
      status: "done",
      note: "演示回执：已完成",
      evidence: { gps: "31.23,121.47", photo: "placeholder" },
    });
  }
  await loadTasks();
}

async function loadReport() {
  const { data } = await axios.get(`${apiBase}/reports/incidents/${incidentId.value}`);
  reportOut.value = JSON.stringify(data, null, 2);
}

loadTopN().catch(() => {});
</script>

<style scoped>
.wrap {
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji",
    "Segoe UI Emoji";
  padding: 16px;
  color: #111;
}
.hdr {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  padding: 12px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
}
.title {
  font-size: 18px;
  font-weight: 700;
}
.meta {
  display: flex;
  gap: 12px;
  color: #6b7280;
  font-size: 12px;
}
.grid {
  margin-top: 12px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px;
  background: #fff;
}
.row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 8px 0;
}
label {
  width: 48px;
  color: #6b7280;
  font-size: 12px;
}
input,
textarea {
  width: 100%;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 8px;
  font-size: 12px;
}
button {
  border: 1px solid #111827;
  background: #111827;
  color: #fff;
  border-radius: 10px;
  padding: 8px 10px;
  font-size: 12px;
  cursor: pointer;
}
button.ghost {
  background: #fff;
  color: #111827;
}
.tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.tbl th,
.tbl td {
  text-align: left;
  border-bottom: 1px solid #f3f4f6;
  padding: 8px 6px;
}
.tbl tbody tr:hover {
  background: #f9fafb;
  cursor: pointer;
}
.muted {
  color: #6b7280;
}
.box {
  border: 1px solid #f3f4f6;
  border-radius: 10px;
  padding: 8px;
  background: #fafafa;
}
.pre {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.4;
}
@media (max-width: 980px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>


