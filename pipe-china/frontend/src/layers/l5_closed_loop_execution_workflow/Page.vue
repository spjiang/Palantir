<template>
  <div class="card">
    <h2>L5 Closed-loop Execution &amp; Workflow</h2>
    <p>Task state machine sketch: pending → accepted → in_progress → done/rejected; can be connected to backend task APIs.</p>
    <div class="card">
      <h3>Sample Tasks</h3>
      <ul>
        <li>task-001 · inspection · road-001 · status: in_progress</li>
        <li>task-002 · traffic control prep · road-001 · status: pending (human approval)</li>
      </ul>
      <p>Real data can be wired to backend <code>/workflow/incidents/{id}/tasks</code>.</p>
    </div>
  </div>
</template>

<script setup></script>

