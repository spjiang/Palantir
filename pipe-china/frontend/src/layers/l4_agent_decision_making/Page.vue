<template>
  <div class="card">
    <h2>L4 智能体决策</h2>
    <p>需真实对接 DeepSeek：前端保留输入框，后端可按现有 API 转发 DeepSeek（需在后端补充）。</p>
    <div class="row">
      <div class="card">
        <h3>对话输入</h3>
        <label>指令</label>
        <textarea v-model="msg" rows="4" placeholder="例如：请研判高风险点并生成任务包"></textarea>
        <button :disabled="loading" @click="send">发送（目前示例响应）</button>
      </div>
      <div class="card">
        <h3>返回</h3>
        <pre>{{ resp }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";

const msg = ref("");
const resp = ref("尚未调用。后端需接入 DeepSeek API。");
const loading = ref(false);

const send = async () => {
  loading.value = true;
  // 这里仅占位，后端补充 /agent/chat 后可改为真实调用
  resp.value = `示例响应：已收到「${msg.value || "空"}」，请在后端接入 DeepSeek 后替换为真实结果。`;
  loading.value = false;
};
</script>

