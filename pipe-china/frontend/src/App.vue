<template>
  <div>
    <h1>Pipe-China 行为建模演示</h1>
    <p>API：{{ apiBase }}</p>

    <div class="tabs">
      <div
        v-for="p in pages"
        :key="p.key"
        class="tab"
        :class="{ active: current === p.key }"
        @click="current = p.key"
      >
        {{ p.title }}
      </div>
    </div>

    <component :is="pageMap[current]" :api-base="apiBase" />
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import PageL1 from "./components/PageL1.vue";
import PageL2 from "./components/PageL2.vue";
import PageL3 from "./components/PageL3.vue";
import PageL4 from "./components/PageL4.vue";
import PageL5 from "./components/PageL5.vue";
import PageL6 from "./components/PageL6.vue";

// 远程部署时，浏览器里的 localhost 不是服务器；因此默认使用“当前访问域名 + 固定 API 端口”
const apiBase = computed(() => {
  const fromEnv = import.meta.env.VITE_API_BASE;
  if (fromEnv && String(fromEnv).trim()) return String(fromEnv).trim();
  const proto = window.location.protocol;
  const host = window.location.hostname;
  return `${proto}//${host}:18088`;
});

const pages = [
  { key: "l1", title: "L1 数据接入与治理" },
  { key: "l2", title: "L2 本体/语义选型" },
  { key: "l3", title: "L3 风险推理/模型" },
  { key: "l4", title: "L4 智能体决策" },
  { key: "l5", title: "L5 执行闭环/工作流" },
  { key: "l6", title: "L6 战报与追溯" },
];

const pageMap = {
  l1: PageL1,
  l2: PageL2,
  l3: PageL3,
  l4: PageL4,
  l5: PageL5,
  l6: PageL6,
};

const current = ref("l2");
</script>
