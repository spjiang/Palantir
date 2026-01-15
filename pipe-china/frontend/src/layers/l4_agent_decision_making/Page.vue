<template>
  <div class="card">
    <h2>L4 Agent Decision-Making</h2>
    <p>DeepSeek integration placeholder: keep an input box on the UI; backend can later proxy DeepSeek (to be implemented).</p>
    <div class="row">
      <div class="card">
        <h3>Input</h3>
        <label>Instruction</label>
        <textarea v-model="msg" rows="4" placeholder="e.g., assess high-risk points and generate a task package"></textarea>
        <button :disabled="loading" @click="send">Send (sample response)</button>
      </div>
      <div class="card">
        <h3>Response</h3>
        <pre>{{ resp }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";

const msg = ref("");
const resp = ref("Not invoked yet. Backend needs to integrate the DeepSeek API.");
const loading = ref(false);

const send = async () => {
  loading.value = true;
  // Placeholder: once backend implements /agent/chat, replace with a real call
  resp.value = `Sample response: received "${msg.value || "empty"}". Please integrate DeepSeek on backend to return real results.`;
  loading.value = false;
};
</script>

