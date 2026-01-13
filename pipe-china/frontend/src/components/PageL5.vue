<template>
  <div class="card">
    <h2>L5 执行闭环/工作流</h2>
    <p>示意任务状态机：pending → accepted → in_progress → done/rejected；可与后端任务接口对接。</p>
    <div class="card">
      <h3>任务列表示例</h3>
      <ul>
        <li>task-001 · 巡查 · road-001 · status: in_progress</li>
        <li>task-002 · 封控准备 · road-001 · status: pending (需人审)</li>
      </ul>
      <p>实际数据可对接后端 `/workflow/incidents/{id}/tasks`。</p>
    </div>
  </div>
</template>

<script setup>
</script>
