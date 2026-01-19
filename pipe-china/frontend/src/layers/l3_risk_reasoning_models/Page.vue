<template>
  <div class="card">
    <h2>L3 风险推理/模型</h2>
    <DigitalTwinMap :api-base="apiBase" />
  </div>
</template>

<script setup>
import DigitalTwinMap from "./DigitalTwinMap.vue";

defineProps({
  apiBase: { type: String, required: true },
});
</script>

