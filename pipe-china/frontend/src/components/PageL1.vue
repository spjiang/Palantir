<template>
  <div class="card">
    <h2>L1 数据接入与治理</h2>
    <p>演示口径：用静态样例展示数据流转（接入→标准化→本体入库）。</p>
    <div class="row">
      <div class="card">
        <h3>数据流转</h3>
        <ul>
          <li>原始：雨量/水位/管网工况/告警事件</li>
          <li>标准化：单位/坐标/枚举统一，打 DQ 标签</li>
          <li>本体入库：写入实体/关系，供后续模型/智能体使用</li>
        </ul>
      </div>
      <div class="card">
        <h3>数据质量（示例）</h3>
        <ul>
          <li>freshness: 0.95</li>
          <li>validity: true</li>
          <li>latency(p95): 3s</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
</script>
