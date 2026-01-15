<template>
  <div>
    <OntologyPanel
      :api-base="apiBase"
      scope="formal"
      title="正式图谱（全量）"
      subtitle="展示与维护正式图数据库的全量图谱，支持图查询/编辑"
    />
  </div>
</template>

<script setup>
import OntologyPanel from "../../components/OntologyPanel.vue";

defineProps({
  apiBase: { type: String, required: true },
});
</script>

