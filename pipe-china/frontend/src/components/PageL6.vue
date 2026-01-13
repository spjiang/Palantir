<template>
  <div class="card">
    <h2>L6 战报与追溯</h2>
    <p>示意时间线与指标，后端对接后可替换为真实查询。</p>
    <div class="row">
      <div class="card">
        <h3>时间线（示例）</h3>
        <ul>
          <li>t0 预警：road-001 雨强突增</li>
          <li>t1 智能体：生成任务包（巡查/封控准备）</li>
          <li>t2 人审：通过封控准备</li>
          <li>t3 任务回执：巡查完成，上传照片</li>
        </ul>
      </div>
      <div class="card">
        <h3>指标（示例）</h3>
        <ul>
          <li>任务总数：2</li>
          <li>完成率：50%</li>
          <li>预警→派单时延：3s</li>
        </ul>
      </div>
    </div>
    <p>可对接后端 `/reports/incidents/{id}` 返回时间线与指标。</p>
  </div>
</template>

<script setup>
</script>
