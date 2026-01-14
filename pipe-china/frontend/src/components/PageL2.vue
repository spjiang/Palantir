<template>
  <div class="l2">
    <div class="stack">
      <OntologyPanel
        :api-base="apiBase"
        scope="draft"
        title="临时图谱（当前文档）"
        subtitle="上传业务方案 → DeepSeek 抽取 → 存入临时图谱 → 图查询/编辑 → 确认后入库正式图谱"
        :draft-id="draftId"
        @draft-created="onDraftCreated"
        @draft-cleared="onDraftCleared"
        @committed="onCommitted"
      />

      <OntologyPanel
        :api-base="apiBase"
        scope="formal"
        title="正式图谱（全量）"
        subtitle="展示与维护正式图数据库的全量图谱，支持图查询/编辑"
        :draft-id="draftId"
        @purged="onPurged"
      />
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import OntologyPanel from "./OntologyPanel.vue";

defineProps({
  apiBase: { type: String, required: true },
});

const draftId = ref("");
function onDraftCreated(id) {
  draftId.value = id;
}
function onDraftCleared() {
  draftId.value = "";
}
function onCommitted() {
  // 正式图谱面板会自行刷新；这里不需要额外操作
}
function onPurged() {
  draftId.value = "";
}
</script>

<style scoped>
.l2 {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.stack {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
</style>

