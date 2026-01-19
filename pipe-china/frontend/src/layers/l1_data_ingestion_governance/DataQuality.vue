<template>
  <div class="card">
    <h2>L1 · 手动写入 / 传感器数据模拟</h2>
    <p>
      你当前未接入真实传感器时，可在此手动写入/模拟生成读数（pressure/flow），并可选触发告警（阈值模拟）。
      这些数据会落到 PostgreSQL，供 L3/L4/L5 联动使用。
    </p>

    <div class="grid2">
      <div class="card subcard">
        <h3>1) 管段（PipelineSegment）</h3>
        <div class="row">
          <input v-model="segmentForm.name" placeholder="例如：管段A" />
          <input v-model.number="segmentForm.latitude" type="number" step="0.000001" placeholder="纬度 lat（可选）" />
          <input v-model.number="segmentForm.longitude" type="number" step="0.000001" placeholder="经度 lon（可选）" />
          <input v-model="segmentForm.ontology_class" placeholder="本体类（默认：管段）" />
          <button class="btn" :disabled="!segmentForm.name" @click="createSegment">创建/复用</button>
          <button class="btn secondary" @click="fetchSegments">刷新</button>
        </div>
        <div class="list">
          <div v-if="segments.length === 0" class="muted">暂无管段</div>
          <div v-for="s in segments" :key="s.id" class="item" :class="{ active: s.id === selectedSegmentId }" @click="selectSegment(s.id)">
            <div class="row itemrow">
              <div class="left">
                <div class="title">{{ s.name }}</div>
                <div class="meta mono">{{ s.id }}</div>
                <div class="meta mono" v-if="s.latitude != null && s.longitude != null">lat={{ s.latitude }}, lon={{ s.longitude }}</div>
                <div class="meta mono" v-if="s.ontology_class">class={{ s.ontology_class }}</div>
              </div>
              <div class="right">
                <button class="btn mini secondary" @click.stop="openEditSegment(s)">编辑</button>
                <button class="btn mini danger" @click.stop="deleteSegment(s)">删除</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="card subcard">
        <h3>2) 传感器（Sensor）</h3>
        <div class="row">
          <select v-model="sensorForm.segment_id">
            <option value="">选择管段…</option>
            <option v-for="s in segments" :key="s.id" :value="s.id">{{ s.name }} ({{ s.id }})</option>
          </select>
        </div>
        <div class="row">
          <input v-model="sensorForm.name" placeholder="例如：压力传感器-1" />
          <input v-model="sensorForm.sensor_type" placeholder="例如：压力/流量" />
        </div>
        <div class="row">
          <button class="btn" :disabled="!sensorForm.segment_id || !sensorForm.name" @click="createSensor">创建/复用</button>
          <button class="btn secondary" :disabled="!activeSegmentId" @click="fetchSensors">刷新</button>
        </div>
        <div class="list">
          <div v-if="sensors.length === 0" class="muted">暂无传感器</div>
          <div
            v-for="s in sensors"
            :key="s.id"
            class="item"
            :class="{ active: s.id === selectedSensorId }"
            @click="selectedSensorId = s.id"
          >
            <div class="row itemrow">
              <div class="left">
                <div class="title">{{ s.name }} <span class="pill">{{ s.sensor_type }}</span></div>
                <div class="meta mono">{{ s.id }}</div>
              </div>
              <div class="right">
                <button class="btn mini secondary" @click.stop="openEditSensor(s)">编辑</button>
                <button class="btn mini danger" @click.stop="deleteSensor(s)">删除</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="card subcard">
      <h3>3) 写入读数（SensorReading）</h3>
      <div class="row">
        <select v-model="readingForm.sensor_id">
          <option value="">选择传感器…</option>
          <option v-for="s in sensors" :key="s.id" :value="s.id">{{ s.name }} ({{ s.id }})</option>
        </select>
        <input v-model.number="readingForm.pressure" type="number" step="0.01" placeholder="pressure（压力）" />
        <input v-model.number="readingForm.flow" type="number" step="0.01" placeholder="flow（流量）" />
      </div>
      <div class="row">
        <textarea v-model="readingForm.rawText" rows="3" class="mono" placeholder='可选：raw JSON（例如 {"temp": 30}）'></textarea>
      </div>
      <div class="row">
        <button class="btn" :disabled="!readingForm.sensor_id || busyReading || busyDemo" @click="submitReading">写入一条读数</button>
        <button class="btn secondary" :disabled="busyReading || busyDemo || busy" @click="refreshTables">刷新读数/告警</button>
        <button class="btn secondary" :disabled="!selectedSegmentId || busyDemo || busyReading || busy" @click="generateDemoData">一键生成模拟数据</button>
        <button class="btn danger" :disabled="busy" @click="purgeSensingAndAlerts">清空感知/预警数据</button>
      </div>
      <div class="muted" style="margin-top: 8px">
        提示：L1 只写事实读数，不产生预警。请到 L3 风险推理/模型根据 L2 行为/规则生成预警结论（并回写到告警表/本体库）。
      </div>
    </div>

    <div class="card subcard">
      <h3>4) 写入原始告警（Alarm，仅接收并存储）</h3>
      <div class="row">
        <select v-model="alarmForm.segment_id">
          <option value="">选择管段（可选，若选传感器则可不选）…</option>
          <option v-for="s in segments" :key="s.id" :value="s.id">{{ s.name }} ({{ s.id }})</option>
        </select>
        <select v-model="alarmForm.sensor_id">
          <option value="">选择传感器（可选）…</option>
          <option v-for="s in sensors" :key="s.id" :value="s.id">{{ s.name }} ({{ s.id }})</option>
        </select>
      </div>
      <div class="row">
        <input v-model="alarmForm.alarm_type" placeholder="告警类型，例如：压力异常" />
        <select v-model="alarmForm.severity">
          <option value="low">low</option>
          <option value="medium">medium</option>
          <option value="high">high</option>
        </select>
      </div>
      <div class="row">
        <input v-model="alarmForm.message" placeholder="告警消息，例如：上游系统提示压力超限" />
      </div>
      <div class="row">
        <textarea v-model="alarmForm.rawText" rows="3" class="mono" placeholder='可选：raw JSON（例如 {"vendor":"x","code":123}）'></textarea>
      </div>
      <div class="row">
        <button class="btn" :disabled="!alarmForm.alarm_type || !alarmForm.message || busyAlarm" @click="submitAlarm">写入原始告警</button>
      </div>
    </div>

    <div class="grid2">
      <div class="card subcard">
        <h3>最新读数（最近 {{ readings.length }} 条）</h3>
        <div v-if="readings.length === 0" class="muted">暂无读数</div>
        <table v-else class="tbl">
          <thead>
            <tr>
              <th>时间</th>
              <th>传感器</th>
              <th>pressure</th>
              <th>flow</th>
              <th>ID</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in readings" :key="r.id">
              <td class="mono">{{ formatTs(r.ts) }}</td>
              <td>{{ r.sensor_name }}</td>
              <td class="mono">{{ r.pressure ?? "-" }}</td>
              <td class="mono">{{ r.flow ?? "-" }}</td>
              <td class="mono">{{ r.id }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card subcard">
        <h3>最新告警（最近 {{ alarms.length }} 条）</h3>
        <div v-if="alarms.length === 0" class="muted">暂无告警</div>
        <table v-else class="tbl">
          <thead>
            <tr>
              <th>时间</th>
              <th>类型</th>
              <th>级别</th>
              <th>消息</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in alarms" :key="a.id">
              <td class="mono">{{ formatTs(a.ts) }}</td>
              <td>{{ a.alarm_type }}</td>
              <td><span class="pill" :class="`sev-${a.severity}`">{{ a.severity }}</span></td>
              <td>{{ a.message }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 编辑管段 Modal -->
    <div v-if="editSegmentModal.open" class="modal-backdrop" @click.self="editSegmentModal.open = false">
      <div class="modal">
        <div class="modal-title">编辑管段</div>
        <label>名称</label>
        <input v-model="editSegmentModal.form.name" placeholder="例如：管段B" />
        <label>纬度（lat，可选）</label>
        <input v-model.number="editSegmentModal.form.latitude" type="number" step="0.000001" placeholder="例如 40.0503" />
        <label>经度（lon，可选）</label>
        <input v-model.number="editSegmentModal.form.longitude" type="number" step="0.000001" placeholder="例如 116.3070" />
        <label>本体类（ontology_class）</label>
        <input v-model="editSegmentModal.form.ontology_class" placeholder="默认：管段" />
        <div class="btnrow">
          <button class="btn secondary" :disabled="busyEditSegment" @click="editSegmentModal.open = false">取消</button>
          <button class="btn" :disabled="!editSegmentModal.form.name || busyEditSegment" @click="submitEditSegment">保存</button>
        </div>
      </div>
    </div>

    <!-- 编辑传感器 Modal -->
    <div v-if="editSensorModal.open" class="modal-backdrop" @click.self="editSensorModal.open = false">
      <div class="modal">
        <div class="modal-title">编辑传感器</div>
        <label>所属管段</label>
        <select v-model="editSensorModal.form.segment_id">
          <option v-for="s in segments" :key="s.id" :value="s.id">{{ s.name }} ({{ s.id }})</option>
        </select>
        <label>名称</label>
        <input v-model="editSensorModal.form.name" placeholder="例如：压力传感器-2" />
        <label>类型</label>
        <input v-model="editSensorModal.form.sensor_type" placeholder="例如：压力/流量" />
        <div class="btnrow">
          <button class="btn secondary" :disabled="busyEditSensor" @click="editSensorModal.open = false">取消</button>
          <button class="btn" :disabled="!editSensorModal.form.name || !editSensorModal.form.segment_id || busyEditSensor" @click="submitEditSensor">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  apiBase: { type: String, required: true },
});

const segments = ref([]);
const sensors = ref([]);
const readings = ref([]);
const alarms = ref([]);
const busy = ref(false);
const busyReading = ref(false);
const busyAlarm = ref(false);
const busyDemo = ref(false);
const busyEditSegment = ref(false);
const busyEditSensor = ref(false);
const reqCtrl = ref({
  segments: null,
  sensors: null,
  tables: null,
});

const selectedSegmentId = ref("");
const selectedSensorId = ref("");

const segmentForm = ref({ name: "", latitude: null, longitude: null, ontology_class: "管段" });
const sensorForm = ref({ segment_id: "", name: "", sensor_type: "压力/流量" });
const readingForm = ref({
  sensor_id: "",
  pressure: null,
  flow: null,
  rawText: "",
});

const alarmForm = ref({
  segment_id: "",
  sensor_id: "",
  alarm_type: "压力异常",
  severity: "medium",
  message: "",
  rawText: "",
});

const editSegmentModal = ref({
  open: false,
  segmentId: "",
  form: { name: "", latitude: null, longitude: null, ontology_class: "管段" },
});

const editSensorModal = ref({
  open: false,
  sensorId: "",
  form: { segment_id: "", name: "", sensor_type: "" },
});

const activeSegmentId = computed(() => selectedSegmentId.value || sensorForm.value.segment_id || "");
let scheduledRefreshTimer = null;

function scheduleSegmentRefresh() {
  try {
    if (scheduledRefreshTimer) clearTimeout(scheduledRefreshTimer);
  } catch {
    // ignore
  }
  scheduledRefreshTimer = setTimeout(async () => {
    scheduledRefreshTimer = null;
    try {
      await fetchSensors();
    } catch (e) {
      if (e?.name === "AbortError") return;
      console.error(e);
      alert(`刷新传感器失败：${e.message}`);
      return;
    }
    await refreshTables();
  }, 0);
}

function formatTs(ts) {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts || "";
  }
}

async function apiJson(path, init) {
  const res = await fetch(`${props.apiBase}${path}`, init);
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

async function fetchSegments() {
  try {
    reqCtrl.value.segments?.abort?.();
  } catch {
    // ignore
  }
  const ctrl = new AbortController();
  reqCtrl.value.segments = ctrl;
  try {
    const data = await apiJson("/l1/segments", { signal: ctrl.signal });
    segments.value = data.items || [];
    if (!selectedSegmentId.value && segments.value.length) {
      selectSegment(segments.value[0].id);
    }
  } catch (e) {
    if (e?.name === "AbortError") return;
    throw e;
  }
}

async function createSegment() {
  try {
    const row = await apiJson("/l1/segments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: segmentForm.value.name,
        latitude: segmentForm.value.latitude,
        longitude: segmentForm.value.longitude,
        ontology_class: segmentForm.value.ontology_class,
      }),
    });
    if (row && row.__created === false) {
      alert("该管段名称已存在，已复用已有管段（不会新增第二条同名管段）。");
    }
    await fetchSegments();
    selectSegment(row.id);
    segmentForm.value.name = "";
    segmentForm.value.latitude = null;
    segmentForm.value.longitude = null;
    segmentForm.value.ontology_class = "管段";
  } catch (e) {
    console.error(e);
    alert(`创建管段失败：${e.message}`);
  }
}

function openEditSegment(seg) {
  editSegmentModal.value.segmentId = seg.id;
  editSegmentModal.value.form = {
    name: seg.name,
    latitude: seg.latitude ?? null,
    longitude: seg.longitude ?? null,
    ontology_class: seg.ontology_class ?? "管段",
  };
  editSegmentModal.value.open = true;
}

async function submitEditSegment() {
  const sid = editSegmentModal.value.segmentId;
  busyEditSegment.value = true;
  try {
    await apiJson(`/l1/segments/${encodeURIComponent(sid)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: editSegmentModal.value.form.name,
        latitude: editSegmentModal.value.form.latitude,
        longitude: editSegmentModal.value.form.longitude,
        ontology_class: editSegmentModal.value.form.ontology_class,
      }),
    });
    editSegmentModal.value.open = false;
    await fetchSegments();
  } catch (e) {
    console.error(e);
    alert(`保存管段失败：${e.message}`);
  } finally {
    busyEditSegment.value = false;
  }
}

async function deleteSegment(seg) {
  const ok = confirm(`确认删除管段「${seg.name}」吗？\n注意：会级联删除该管段下所有传感器及其读数。`);
  if (!ok) return;
  try {
    await apiJson(`/l1/segments/${encodeURIComponent(seg.id)}`, { method: "DELETE" });
    if (selectedSegmentId.value === seg.id) {
      selectedSegmentId.value = "";
      selectedSensorId.value = "";
      sensors.value = [];
      readings.value = [];
      alarms.value = [];
    }
    await fetchSegments();
  } catch (e) {
    console.error(e);
    alert(`删除管段失败：${e.message}`);
  }
}

function selectSegment(id) {
  selectedSegmentId.value = id;
  sensorForm.value.segment_id = id;
  // 合并短时间内的多次刷新（防止切换/初始化时请求风暴导致卡死）
  scheduleSegmentRefresh();
}

// 当用户只在下拉框切换管段（未点击左侧列表）时，也要自动刷新传感器/读数/告警
watch(
  () => sensorForm.value.segment_id,
  (newId) => {
    if (!newId) return;
    if (newId === selectedSegmentId.value) return;
    selectSegment(newId);
  }
);

async function fetchSensors() {
  if (!activeSegmentId.value) {
    sensors.value = [];
    return;
  }
  try {
    reqCtrl.value.sensors?.abort?.();
  } catch {
    // ignore
  }
  const ctrl = new AbortController();
  reqCtrl.value.sensors = ctrl;
  try {
    const data = await apiJson(`/l1/sensors?segment_id=${encodeURIComponent(activeSegmentId.value)}`, { signal: ctrl.signal });
    sensors.value = data.items || [];
    if (!selectedSensorId.value && sensors.value.length) {
      selectedSensorId.value = sensors.value[0].id;
    }
    if (!readingForm.value.sensor_id && selectedSensorId.value) {
      readingForm.value.sensor_id = selectedSensorId.value;
    }
  } catch (e) {
    if (e?.name === "AbortError") return;
    throw e;
  }
}

async function createSensor() {
  try {
    const row = await apiJson("/l1/sensors", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(sensorForm.value),
    });
    if (row && row.__created === false) {
      alert("该管段下已存在同名传感器，已复用已有传感器（不会新增第二条同名传感器）。请换一个名字再创建。");
    }
    await fetchSensors();
    selectedSensorId.value = row.id;
    readingForm.value.sensor_id = row.id;
    sensorForm.value.name = "";
  } catch (e) {
    console.error(e);
    alert(`创建传感器失败：${e.message}`);
  }
}

function openEditSensor(sensor) {
  editSensorModal.value.sensorId = sensor.id;
  editSensorModal.value.form = {
    segment_id: sensor.segment_id,
    name: sensor.name,
    sensor_type: sensor.sensor_type,
  };
  editSensorModal.value.open = true;
}

async function submitEditSensor() {
  const sid = editSensorModal.value.sensorId;
  const payload = { ...editSensorModal.value.form };
  busyEditSensor.value = true;
  try {
    const row = await apiJson(`/l1/sensors/${encodeURIComponent(sid)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    editSensorModal.value.open = false;
    await fetchSensors();
    selectedSensorId.value = row.id;
    readingForm.value.sensor_id = row.id;
    await refreshTables();
  } catch (e) {
    console.error(e);
    alert(`保存传感器失败：${e.message}`);
  } finally {
    busyEditSensor.value = false;
  }
}

async function deleteSensor(sensor) {
  const ok = confirm(`确认删除传感器「${sensor.name}」吗？\n注意：会删除该传感器的所有读数。`);
  if (!ok) return;
  try {
    await apiJson(`/l1/sensors/${encodeURIComponent(sensor.id)}`, { method: "DELETE" });
    if (selectedSensorId.value === sensor.id) {
      selectedSensorId.value = "";
      readingForm.value.sensor_id = "";
    }
    await fetchSensors();
    await refreshTables();
  } catch (e) {
    console.error(e);
    alert(`删除传感器失败：${e.message}`);
  }
}

function parseRawJson(text) {
  const t = (text || "").trim();
  if (!t) return {};
  try {
    return JSON.parse(t);
  } catch {
    throw new Error("raw JSON 解析失败，请检查格式");
  }
}

async function submitReading() {
  busyReading.value = true;
  try {
    const payload = {
      sensor_id: readingForm.value.sensor_id,
      pressure: readingForm.value.pressure,
      flow: readingForm.value.flow,
      raw: parseRawJson(readingForm.value.rawText),
    };
    await apiJson("/l1/readings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    await refreshTables();
  } catch (e) {
    console.error(e);
    alert(`写入读数失败：${e.message}`);
  } finally {
    busyReading.value = false;
  }
}

async function submitAlarm() {
  busyAlarm.value = true;
  try {
    const payload = {
      alarm_type: alarmForm.value.alarm_type,
      severity: alarmForm.value.severity,
      message: alarmForm.value.message,
      sensor_id: alarmForm.value.sensor_id || null,
      segment_id: alarmForm.value.segment_id || null,
      raw: parseRawJson(alarmForm.value.rawText),
    };
    await apiJson("/l1/alarms", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    alarmForm.value.message = "";
    alarmForm.value.rawText = "";
    await refreshTables();
  } catch (e) {
    console.error(e);
    alert(`写入原始告警失败：${e.message}`);
  } finally {
    busyAlarm.value = false;
  }
}

async function refreshTables() {
  const seg = activeSegmentId.value;
  const limit = 50; // 默认只拉取最近 50 条，避免大表格渲染导致卡死
  const q = seg ? `?segment_id=${encodeURIComponent(seg)}&limit=${limit}` : `?limit=${limit}`;
  try {
    reqCtrl.value.tables?.abort?.();
  } catch {
    // ignore
  }
  const ctrl = new AbortController();
  reqCtrl.value.tables = ctrl;
  try {
    const [r1, r2] = await Promise.all([apiJson(`/l1/readings${q}`, { signal: ctrl.signal }), apiJson(`/l1/alarms${q}`, { signal: ctrl.signal })]);
    readings.value = r1.items || [];
    alarms.value = r2.items || [];
  } catch (e) {
    if (e?.name === "AbortError") return;
    console.error(e);
    // 不要 throw，避免未捕获异常把页面打崩（开发模式会红屏）
    alert(`刷新读数/告警失败：${e.message}`);
  }
}

async function purgeSensingAndAlerts() {
  const seg = activeSegmentId.value;
  const msg = seg
    ? "确认清空【当前管段】的感知数据(读数)与预警数据(告警/风险事件)吗？\n注意：不会删除管段/传感器。"
    : "当前未选择管段，将清空【全局】感知数据(读数)与预警数据(告警/风险事件)。\n确认继续吗？";
  if (!confirm(msg)) return;
  busy.value = true;
  try {
    const qs = new URLSearchParams({ confirm: "YES" });
    if (seg) qs.set("segment_id", seg);
    await apiJson(`/l1/purge?${qs.toString()}`, { method: "POST" });
    // 先清空 UI，避免“旧表格 + 新请求”叠加导致卡顿
    readings.value = [];
    alarms.value = [];
    await refreshTables();
    alert("清空完成（TopN 需要到 L3 刷新）");
  } catch (e) {
    console.error(e);
    alert(`清空失败：${e.message}`);
  } finally {
    busy.value = false;
  }
}

function rand(min, max) {
  return min + Math.random() * (max - min);
}

async function generateDemoData() {
  // 如果当前管段下没有传感器，默认创建 2 个
  if (!activeSegmentId.value) return;
  busyDemo.value = true;
  try {
    await fetchSensors();
    if (sensors.value.length === 0) {
      await apiJson("/l1/sensors", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ segment_id: activeSegmentId.value, name: "压力传感器-1", sensor_type: "压力/流量" }),
      });
      await apiJson("/l1/sensors", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ segment_id: activeSegmentId.value, name: "压力传感器-2", sensor_type: "压力/流量" }),
      });
      await fetchSensors();
    }
    // 给每个传感器写 5 条读数
    for (const s of sensors.value) {
      for (let i = 0; i < 5; i++) {
        const pressure = Number(rand(4.5, 9.5).toFixed(2));
        const flow = Number(rand(50, 120).toFixed(2));
        await apiJson("/l1/readings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sensor_id: s.id,
            pressure,
            flow,
            raw: { source: "demo", seq: i + 1 },
          }),
        });
      }
    }
    await refreshTables();
  } catch (e) {
    console.error(e);
    alert(`生成模拟数据失败：${e.message}`);
  } finally {
    busyDemo.value = false;
  }
}

onMounted(async () => {
  try {
    await fetchSegments();
  } catch (e) {
    console.error(e);
    alert(`L1 初始化失败：${e.message}`);
  }
});

onBeforeUnmount(() => {
  // 防止页面切换后仍有未完成请求/计时器占用主线程
  try {
    if (scheduledRefreshTimer) clearTimeout(scheduledRefreshTimer);
  } catch {
    // ignore
  }
  scheduledRefreshTimer = null;
  try {
    reqCtrl.value.segments?.abort?.();
    reqCtrl.value.sensors?.abort?.();
    reqCtrl.value.tables?.abort?.();
  } catch {
    // ignore
  }
});
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
.row {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-top: 10px;
  flex-wrap: wrap;
}
.itemrow {
  margin-top: 0;
  align-items: flex-start;
}
.left {
  flex: 1 1 auto;
  min-width: 220px;
}
.right {
  flex: 0 0 auto;
  display: flex;
  gap: 8px;
}
input,
select,
textarea {
  width: 100%;
  background: rgba(15, 23, 42, 0.55);
  border: 1px solid rgba(148, 163, 184, 0.22);
  color: rgba(226, 232, 240, 0.92);
  border-radius: 10px;
  padding: 10px 12px;
  outline: none;
}
textarea {
  resize: vertical;
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
.btn.mini {
  padding: 6px 10px;
  border-radius: 10px;
  font-size: 12px;
}
.btn.danger {
  background: rgba(239, 68, 68, 0.18);
  border-color: rgba(239, 68, 68, 0.35);
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.list {
  margin-top: 10px;
  display: grid;
  gap: 8px;
}
.item {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(148, 163, 184, 0.06);
  cursor: pointer;
}
.item.active {
  border-color: rgba(14, 165, 233, 0.5);
  background: rgba(14, 165, 233, 0.12);
}
.title {
  font-weight: 700;
}
.meta {
  font-size: 12px;
  color: rgba(226, 232, 240, 0.7);
  margin-top: 4px;
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}
.muted {
  color: rgba(226, 232, 240, 0.65);
}
.pill {
  display: inline-block;
  margin-left: 8px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(148, 163, 184, 0.12);
  font-size: 12px;
  font-weight: 600;
}
.pill.sev-high {
  border-color: rgba(239, 68, 68, 0.45);
  background: rgba(239, 68, 68, 0.15);
}
.pill.sev-medium {
  border-color: rgba(245, 158, 11, 0.45);
  background: rgba(245, 158, 11, 0.15);
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

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(2, 6, 23, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  z-index: 50;
}
.modal {
  width: min(640px, 96vw);
  background: rgba(15, 23, 42, 0.95);
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 14px;
  padding: 14px;
}
.modal-title {
  font-weight: 800;
  margin-bottom: 10px;
}
.btnrow {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 12px;
}
label {
  display: block;
  margin-top: 10px;
  margin-bottom: 6px;
  color: rgba(226, 232, 240, 0.8);
  font-size: 13px;
}
</style>

