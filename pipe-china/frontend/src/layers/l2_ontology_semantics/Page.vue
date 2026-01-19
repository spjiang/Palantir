<template>
  <div class="card">
    <h2>L2 本体/语义选型</h2>
    <p>请使用左侧菜单分别进入“临时本体库（抽取/编辑）”与“正式本体库（查询/维护）”。</p>
    <ul>
      <li>临时本体库：上传业务方案，调用 DeepSeek 抽取并在临时本体库中编辑</li>
      <li>正式本体库：对正式本体库做查询与维护</li>
    </ul>
  </div>
</template>

<script setup>
defineProps({
  apiBase: { type: String, required: true },
});
</script>
