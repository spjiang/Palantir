<template>
  <div class="card">
    <h2>L3 · 数字孪生地图（占位）</h2>
    <p>
      以“北京海淀区 东北旺西路8号院”为中心展示底图，并叠加风险 TopN 列表。
      由于当前未接入真实 GIS 坐标，点位为“稳定伪定位”（按 segment_id 哈希分布在视窗内），用于占位演示联动与可视化。
    </p>

    <div class="toolbar">
      <div class="left">
        <div class="kv">
          <div class="k">中心点</div>
          <div class="v">{{ centerLabel }}</div>
        </div>
        <div class="kv">
          <div class="k">draftId</div>
          <div class="v mono">{{ draftId || "（空：仅用 L1 告警启发式评分）" }}</div>
        </div>
      </div>
      <div class="right">
        <button class="btn secondary" @click="loadDraftIdFromSession">读取当前 draftId</button>
        <button class="btn" :disabled="loading" @click="fetchTopN">刷新 TopN</button>
      </div>
    </div>

    <div class="layout">
      <div class="mapwrap">
        <iframe class="map" :src="mapUrl" loading="lazy" />
        <div class="overlay">
          <div class="center-pin" title="中心点"></div>
          <div
            v-for="p in points"
            :key="p.segment_id"
            class="pin"
            :class="{ active: p.segment_id === selectedId }"
            :style="{ left: `${p.x * 100}%`, top: `${p.y * 100}%` }"
            :title="`${p.segment_name} · ${p.risk_state} (${p.risk_score})`"
            @click="select(p.segment_id)"
          ></div>
        </div>
      </div>

      <div class="side">
        <div class="card subcard">
          <div class="sidehead">
            <div>
              <div class="stitle">风险 TopN</div>
              <div class="ssub">点击条目高亮地图点位</div>
            </div>
            <select v-model.number="limit">
              <option :value="5">Top 5</option>
              <option :value="10">Top 10</option>
              <option :value="20">Top 20</option>
            </select>
          </div>

          <div v-if="items.length === 0" class="muted">暂无数据（先去 L1 写入/模拟读数与告警）</div>
          <div v-else class="list">
            <div v-for="it in items" :key="it.segment_id" class="row" :class="{ active: it.segment_id === selectedId }" @click="select(it.segment_id)">
              <div class="r1">
                <div class="name">{{ it.segment_name }}</div>
                <div class="pill" :class="`st-${it.risk_state}`">{{ it.risk_state }}</div>
              </div>
              <div class="r2">
                <div class="mono">score={{ it.risk_score }}</div>
                <div class="mono">sensors={{ it.sensor_count }} alarms={{ it.alarm_count }}</div>
              </div>
              <div class="r3">{{ it.explain }}</div>
            </div>
          </div>
        </div>

        <div class="card subcard" v-if="selected">
          <div class="stitle">详情</div>
          <div class="mono pre">{{ JSON.stringify(selected, null, 2) }}</div>
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

// 近似中心点（软件园/东北旺附近），用于占位展示
const center = ref({ lat: 40.0503, lon: 116.3070 });
const centerLabel = "北京海淀区 东北旺西路8号院";

const draftId = ref("");
const limit = ref(10);
const loading = ref(false);
const items = ref([]);
const selectedId = ref("");

function loadDraftIdFromSession() {
  try {
    draftId.value = sessionStorage.getItem("pipe-china:draftId") || "";
  } catch {
    draftId.value = "";
  }
}

function stableHash(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

const points = computed(() => {
  return (items.value || []).map((it, idx) => {
    // 优先用真实坐标（L1 管段 latitude/longitude），否则回退伪定位占位
    const lat = it.latitude ?? it.lat ?? null;
    const lon = it.longitude ?? it.lon ?? null;
    if (lat != null && lon != null) {
      const { left, right, bottom, top } = bbox.value;
      const x = (Number(lon) - left) / (right - left);
      const y = (top - Number(lat)) / (top - bottom);
      return { ...it, x: clamp01(x), y: clamp01(y), __geo: { lat: Number(lat), lon: Number(lon) } };
    }
    const h = stableHash(String(it.segment_id || idx));
    const x = 0.1 + ((h % 1000) / 1000) * 0.8;
    const y = 0.1 + (((h / 1000) % 1000) / 1000) * 0.8;
    return { ...it, x, y, __geo: null };
  });
});

const selected = computed(() => (items.value || []).find((x) => x.segment_id === selectedId.value) || null);

function select(id) {
  selectedId.value = id;
}

const mapUrl = computed(() => {
  const { lat, lon } = center.value;
  const d = 0.015; // bbox 半径（度）
  const left = lon - d;
  const right = lon + d;
  const bottom = lat - d;
  const top = lat + d;
  const qs = new URLSearchParams({
    bbox: `${left},${bottom},${right},${top}`,
    layer: "mapnik",
    marker: `${lat},${lon}`,
  });
  return `https://www.openstreetmap.org/export/embed.html?${qs.toString()}`;
});

const bbox = computed(() => {
  const { lat, lon } = center.value;
  const d = 0.015;
  return { left: lon - d, right: lon + d, bottom: lat - d, top: lat + d };
});

function clamp01(v) {
  if (!Number.isFinite(v)) return 0.5;
  return Math.max(0.02, Math.min(0.98, v));
}

async function fetchTopN() {
  loading.value = true;
  try {
    const qs = new URLSearchParams();
    qs.set("limit", String(limit.value || 10));
    if (draftId.value) qs.set("draft_id", draftId.value);
    const res = await fetch(`${props.apiBase}/risk/topn?${qs.toString()}`);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    items.value = data.items || [];
    if (!selectedId.value && items.value.length) selectedId.value = items.value[0].segment_id;
  } catch (e) {
    console.error(e);
    alert(`获取 TopN 失败：${e.message}`);
  } finally {
    loading.value = false;
  }
}

watch(limit, fetchTopN);

onMounted(() => {
  loadDraftIdFromSession();
  fetchTopN();
});
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-top: 10px;
}
.kv {
  display: grid;
  grid-template-columns: 64px 1fr;
  gap: 8px;
  font-size: 13px;
  color: rgba(226, 232, 240, 0.8);
}
.k {
  color: rgba(226, 232, 240, 0.65);
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
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
.layout {
  margin-top: 12px;
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 14px;
}
@media (max-width: 980px) {
  .layout {
    grid-template-columns: 1fr;
  }
}
.mapwrap {
  position: relative;
  overflow: hidden;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(148, 163, 184, 0.06);
  min-height: 560px;
}
.map {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  border: 0;
}
.overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.center-pin {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 14px;
  height: 14px;
  transform: translate(-50%, -50%);
  border-radius: 999px;
  border: 2px solid rgba(226, 232, 240, 0.9);
  background: rgba(14, 165, 233, 0.35);
  box-shadow: 0 0 0 6px rgba(14, 165, 233, 0.18);
}
.pin {
  pointer-events: auto;
  position: absolute;
  width: 12px;
  height: 12px;
  transform: translate(-50%, -50%);
  border-radius: 999px;
  border: 2px solid rgba(226, 232, 240, 0.85);
  background: rgba(239, 68, 68, 0.25);
  cursor: pointer;
}
.pin.active {
  background: rgba(239, 68, 68, 0.55);
  box-shadow: 0 0 0 8px rgba(239, 68, 68, 0.18);
}
.subcard {
  margin-top: 0;
}
.sidehead {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}
.sidehead select {
  background: rgba(15, 23, 42, 0.55);
  border: 1px solid rgba(148, 163, 184, 0.22);
  color: rgba(226, 232, 240, 0.92);
  border-radius: 10px;
  padding: 8px 10px;
  outline: none;
}
.stitle {
  font-weight: 800;
}
.ssub {
  margin-top: 2px;
  font-size: 12px;
  color: rgba(226, 232, 240, 0.65);
}
.muted {
  color: rgba(226, 232, 240, 0.65);
  margin-top: 10px;
}
.list {
  margin-top: 10px;
  display: grid;
  gap: 8px;
  max-height: 520px;
  overflow: auto;
}
.row {
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(148, 163, 184, 0.06);
  border-radius: 12px;
  padding: 10px;
  cursor: pointer;
}
.row.active {
  border-color: rgba(14, 165, 233, 0.55);
  background: rgba(14, 165, 233, 0.12);
}
.r1 {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}
.name {
  font-weight: 800;
}
.r2 {
  margin-top: 6px;
  display: flex;
  justify-content: space-between;
  gap: 10px;
  color: rgba(226, 232, 240, 0.75);
  font-size: 12px;
}
.r3 {
  margin-top: 6px;
  color: rgba(226, 232, 240, 0.8);
  font-size: 12px;
  line-height: 1.4;
}
.pill {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(148, 163, 184, 0.12);
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}
.pill.st-高风险 {
  border-color: rgba(239, 68, 68, 0.45);
  background: rgba(239, 68, 68, 0.16);
}
.pill.st-异常 {
  border-color: rgba(245, 158, 11, 0.45);
  background: rgba(245, 158, 11, 0.14);
}
.pill.st-波动 {
  border-color: rgba(56, 189, 248, 0.45);
  background: rgba(56, 189, 248, 0.14);
}
.pill.st-正常 {
  border-color: rgba(34, 197, 94, 0.45);
  background: rgba(34, 197, 94, 0.14);
}
.pre {
  margin-top: 8px;
  white-space: pre-wrap;
  background: rgba(148, 163, 184, 0.06);
  border: 1px solid rgba(148, 163, 184, 0.16);
  padding: 10px;
  border-radius: 12px;
}
</style>

