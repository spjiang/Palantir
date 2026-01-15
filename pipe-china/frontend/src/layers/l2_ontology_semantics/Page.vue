<template>
  <div class="card">
    <h2>L2 本体/语义选型</h2>
    <p>请使用左侧菜单分别进入“草稿图谱（抽取/编辑）”与“正式图谱（查询/维护）”。</p>
    <ul>
      <li>草稿图谱：上传业务方案，调用 DeepSeek 抽取并在临时图谱中编辑</li>
      <li>正式图谱：对正式图数据库做查询与维护</li>
    </ul>
  </div>
</template>

<script setup>
defineProps({
  apiBase: { type: String, required: true },
});
</script>
