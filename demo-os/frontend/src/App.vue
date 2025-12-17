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

      <section class="card wide">
        <h3>系统分层与节点（含数据接入与治理）</h3>
        <div class="layer-grid">
          <div v-for="layer in layerBlocks" :key="layer.name" class="layer-card">
            <div class="layer-title">{{ layer.name }}</div>
            <div class="layer-desc">{{ layer.desc }}</div>
            <ul class="layer-list">
              <li v-for="node in layer.nodes" :key="node.title">
                <div class="node-title">{{ node.title }}</div>
                <div class="node-detail">{{ node.detail }}</div>
              </li>
            </ul>
          </div>
        </div>
        <div class="hint">说明：为前端展示而简化的节点清单；实际数据流与接口见方案书 1.1.2。</div>
      </section>

      <section class="card">
        <h3>2) 暴雨参谋长智能体（对话）</h3>
        <div class="row">
          <label>事件ID</label>
          <input v-model="incidentId" placeholder="留空自动创建" />
          <button @click="createIncident">新建事件</button>
        </div>
        <div class="chips">
          <span class="chip muted">当前区域：{{ areaId }}</span>
          <span class="chip" :class="{ muted: !selectedTarget }">当前目标：{{ selectedTarget || "未选择" }}</span>
        </div>
        <textarea v-model="chatInput" rows="4" placeholder="输入：例如“请研判并一键下发任务包”"></textarea>
        <div class="row">
          <button @click="sendChat">发送</button>
          <button class="ghost" @click="fillOneClick">一键派单口令</button>
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
        <div v-if="reportData" class="report-grid">
          <div class="report-card">
            <div class="rc-title">事件</div>
            <div class="rc-main">{{ reportData.title || reportData.incident_id }}</div>
            <div class="rc-sub">状态：{{ reportData.status }}</div>
          </div>
          <div class="report-card">
            <div class="rc-title">任务指标</div>
            <div class="rc-metrics">
              <div><span>总数</span><strong>{{ reportData.metrics?.task_total ?? "-" }}</strong></div>
              <div><span>完成</span><strong>{{ reportData.metrics?.task_done ?? "-" }}</strong></div>
              <div><span>完成率</span><strong>{{ (reportData.metrics?.task_done_rate ?? 0) | percent }}</strong></div>
            </div>
          </div>
          <div class="report-card timeline">
            <div class="rc-title">时间线</div>
            <ul class="timeline-list">
              <li v-for="(e, idx) in reportData.timeline" :key="idx">
                <div class="tl-time">{{ formatTime(e.time) }}</div>
                <div class="tl-body">
                  <div class="tl-type">{{ e.type }}</div>
                  <div class="tl-payload muted">{{ stringify(e.payload) }}</div>
                </div>
              </li>
            </ul>
          </div>
        </div>
        <div class="box">
          <div class="muted">原始 JSON：</div>
          <pre class="pre">{{ reportOut }}</pre>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import axios from "axios";
import { ref } from "vue";

// 默认走同源代理（见 vite.config.ts 的 server.proxy），避免必须暴露 7000/7001 端口给外部网络
const apiBase = import.meta.env.VITE_API_BASE_URL || "/api";
const agentBase = import.meta.env.VITE_AGENT_BASE_URL || "/agent";

const layerBlocks = [
  {
    name: "L1 数据接入与治理",
    desc: "采集、落库、质量与口径统一",
    nodes: [
      { title: "接入连接器", detail: "雨量/雷达/水位/泵站/路况/事件" },
      { title: "Raw 落地", detail: "原始数据原样落库，保存完整上下文" },
      { title: "ODS 明细", detail: "清洗对齐后的操作型明细层，统一口径" },
      { title: "TSDB 时序", detail: "高频指标/传感器时序存储与查询" },
      { title: "DQ 标签", detail: "完整性/及时性/一致性等质量标记与评分" },
    ],
  },
  {
    name: "L2 语义与状态（本体）",
    desc: "对象/关系/责任归属与状态快照",
    nodes: [
      { title: "实体/关系", detail: "路段/泵站/管网/责任单位/预案等知识" },
      { title: "空间归属", detail: "责任片区/汇水区/行政区/服务范围" },
      { title: "状态快照", detail: "get_object_state 对象当前属性/特征/质量标记" },
    ],
  },
  {
    name: "L3 风险推理（模型）",
    desc: "风险评分 + 解释 + 置信度",
    nodes: [
      { title: "risk_score / level", detail: "按路段/网格输出风险分与等级" },
      { title: "explain_factors", detail: "雨强、水位、泵站工况、低洼地形等解释因子" },
      { title: "confidence", detail: "置信度，反映模型判断确定性" },
      { title: "TopN / 热力图 API", detail: "对上层服务提供热力图与 TopN 接口" },
    ],
  },
  {
    name: "L4 智能体决策",
    desc: "有依据的建议 → 任务包",
    nodes: [
      { title: "RAG 证据检索", detail: "预案/规程/历史战报/对象上下文" },
      {
        title: "任务包编排",
        detail:
          "create_task_pack -> TaskPack/tasks[]，生成派单所需字段：owner_org（责任单位/队伍）、sla_minutes（完成时限）、required_evidence[]（必传证据：定位/照片/视频/测量值等）、need_approval（是否需人审），可选 title/detail",
      },
      {
        title: "下发接口对接",
        detail: "调用工作流派单 API 落库；失败需带错误回传与重试策略（可选人工兜底）",
      },
      { title: "简报草稿（可选）", detail: "draft_briefing 引用证据生成摘要" },
    ],
  },
  {
    name: "L5 执行闭环（工作流）",
    desc: "审批、派单、SLA、回执校验",
    nodes: [
      { title: "风控门禁/人审", detail: "封控/停运/跨部门联动需审核，人工确认后派单" },
      {
        title: "派单与状态机",
        detail:
          "创建任务落库，通知渠道（消息/短信/APP），SLA 计时，超时升级，required_evidence 校验（缺证拒收或补传）",
      },
      { title: "回执校验", detail: "核对证据/状态，更新任务/事件时间线，异常回退或升级" },
      { title: "证据库", detail: "照片/视频/定位等附件存储与引用 ID" },
    ],
  },
  {
    name: "L6 战报与追溯",
    desc: "时间线/指标/依据可追溯",
    nodes: [
      { title: "时间线汇总", detail: "预警/模型/智能体/审批/派单/回执" },
      { title: "指标与战报", detail: "任务完成率、响应时长等导出" },
      { title: "血缘与审计", detail: "lineage/version_refs 支撑依据可追溯" },
    ],
  },
];

const areaId = ref("A-001");
const incidentId = ref<string>("");
const selectedTarget = ref<string>("");

const topN = ref<any[]>([]);
const tasks = ref<any[]>([]);

const chatInput = ref("请研判并一键下发任务包");
const agentOut = ref("");
const reportOut = ref("");
const reportData = ref<any | null>(null);

async function loadTopN() {
  const { data } = await axios.get(`${apiBase}/risk/topn`, { params: { area_id: areaId.value, n: 5 } });
  topN.value = data.items || [];
  if (!selectedTarget.value && topN.value.length > 0) {
    selectedTarget.value = topN.value[0].target_id || "";
  }
}

function pickTarget(targetId: string) {
  selectedTarget.value = targetId;
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
    target_id: selectedTarget.value || null,
    message: chatInput.value,
  });
  if (data.incident_id) {
    incidentId.value = data.incident_id;
  }
  agentOut.value = JSON.stringify(data, null, 2);
  // 若智能体自动创建了事件
  if (!incidentId.value) {
    // 从 tasks 里推断不到，这里就用后端的“最新事件”能力简化：直接再新建一个事件让用户可控
    // 演示：如果智能体触发派单，用户通常会先点“新建事件”；这里保持简单不反推。
  }
}

function fillOneClick() {
  chatInput.value = selectedTarget.value
    ? `请研判 ${selectedTarget.value} 并一键下发任务包`
    : "请研判并一键下发任务包";
}

function formatTime(t: string | undefined) {
  if (!t) return "-";
  try {
    const d = new Date(t);
    return d.toLocaleString();
  } catch {
    return t;
  }
}

function stringify(obj: any) {
  try {
    return JSON.stringify(obj);
  } catch {
    return String(obj ?? "");
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
  reportData.value = data;
  reportOut.value = JSON.stringify(data, null, 2);
}

loadTopN().catch(() => {});
</script>

<style scoped>
.wrap {
  font-family: "Inter", "Segoe UI", system-ui, -apple-system, Helvetica, Arial, sans-serif;
  padding: 16px;
  color: #e5ecff;
  background: radial-gradient(80% 120% at 20% 20%, rgba(76, 123, 255, 0.18), transparent),
    radial-gradient(70% 100% at 80% 10%, rgba(16, 185, 129, 0.15), transparent),
    #0c1220;
  min-height: 100vh;
}
.hdr {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  padding: 14px 14px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(64, 82, 255, 0.25), rgba(26, 190, 225, 0.2));
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.25);
  backdrop-filter: blur(8px);
}
.title {
  font-size: 20px;
  font-weight: 800;
  letter-spacing: 0.3px;
}
.meta {
  display: flex;
  gap: 12px;
  color: #c5d1ff;
  font-size: 12px;
}
.grid {
  margin-top: 14px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
.card {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  padding: 14px;
  background: rgba(255, 255, 255, 0.04);
  overflow: hidden;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.25);
  backdrop-filter: blur(10px);
}
.card.wide {
  grid-column: 1 / -1;
}
.row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 8px 0;
}
label {
  width: 48px;
  color: #9fb2d4;
  font-size: 12px;
}
input,
textarea {
  width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 10px;
  padding: 8px;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.05);
  color: #e5ecff;
}
input::placeholder,
textarea::placeholder {
  color: #8fa0c4;
}
button {
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: linear-gradient(135deg, #4f8bff, #3dd6d0);
  color: #0c1220;
  border-radius: 10px;
  padding: 8px 10px;
  font-size: 12px;
  cursor: pointer;
  transition: transform 0.05s ease, box-shadow 0.1s ease;
}
button.ghost {
  background: transparent;
  color: #d8e5ff;
  border-color: rgba(255, 255, 255, 0.2);
}
button:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 18px rgba(79, 139, 255, 0.25);
}
.tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.tbl th,
.tbl td {
  text-align: left;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  padding: 8px 6px;
}
.tbl tbody tr:hover {
  background: rgba(255, 255, 255, 0.04);
  cursor: pointer;
}
.muted {
  color: #9fb2d4;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 6px 0 8px;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: #dfe8ff;
  font-size: 12px;
  border: 1px solid rgba(255, 255, 255, 0.15);
}
.layer-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 10px;
  margin-top: 8px;
}
.layer-card {
  border: 1px dashed rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.02);
}
.layer-title {
  font-weight: 700;
  margin-bottom: 4px;
}
.layer-desc {
  color: #9fb2d4;
  font-size: 12px;
  margin-bottom: 6px;
}
.layer-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.layer-list li {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 6px 8px;
}
.node-title {
  font-weight: 600;
  font-size: 13px;
}
.node-detail {
  color: #9fb2d4;
  font-size: 12px;
}
.hint {
  margin-top: 8px;
  color: #9fb2d4;
  font-size: 12px;
}
.box {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 8px;
  background: rgba(255, 255, 255, 0.03);
}
.report-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 10px;
  margin-bottom: 8px;
}
.report-card {
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.04);
}
.report-card.timeline {
  grid-column: 1 / -1;
}
.rc-title {
  font-weight: 700;
  margin-bottom: 6px;
}
.rc-main {
  font-size: 16px;
  font-weight: 700;
}
.rc-sub {
  color: #9fb2d4;
  font-size: 12px;
}
.rc-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
  gap: 6px;
}
.rc-metrics span {
  display: block;
  color: #9fb2d4;
  font-size: 11px;
}
.rc-metrics strong {
  font-size: 16px;
}
.timeline-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.timeline-list li {
  display: flex;
  gap: 8px;
  border-left: 2px solid rgba(255, 255, 255, 0.12);
  padding-left: 10px;
}
.tl-time {
  font-size: 12px;
  color: #9fb2d4;
  min-width: 150px;
}
.tl-body {
  flex: 1;
}
.tl-type {
  font-weight: 600;
}
.tl-payload {
  font-size: 12px;
  word-break: break-all;
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


