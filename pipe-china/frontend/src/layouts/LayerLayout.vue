<template>
  <!-- 负责把 apiBase 继续透传给二级页面 -->
  <RouterView v-slot="{ Component }">
    <component :is="Component" :api-base="apiBase" />
  </RouterView>
</template>

<script setup>
defineProps({
  apiBase: { type: String, required: true },
});
</script>

