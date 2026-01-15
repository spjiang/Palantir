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
import PageL1 from "./layers/l1_data_ingestion_governance/Page.vue";
import PageL2 from "./layers/l2_ontology_semantics/Page.vue";
import PageL3 from "./layers/l3_risk_reasoning_models/Page.vue";
import PageL4 from "./layers/l4_agent_decision_making/Page.vue";
import PageL5 from "./layers/l5_closed_loop_execution_workflow/Page.vue";
import PageL6 from "./layers/l6_reports_traceability/Page.vue";

// 远程部署时，浏览器里的 localhost 不是服务器；因此默认使用“当前访问域名 + 固定 API 端口”
const apiBase = computed(() => {
  const fromEnv = import.meta.env.VITE_API_BASE;
  const envVal = fromEnv ? String(fromEnv).trim() : "";
  // 远程访问场景：如果 env 里配置了 localhost/127.0.0.1，会导致浏览器请求打到用户本机
  if (envVal && !/^https?:\/\/(localhost|127\.0\.0\.1)(:|\/|$)/i.test(envVal)) return envVal;
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
