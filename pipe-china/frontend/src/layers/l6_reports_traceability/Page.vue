<template>
  <div class="card">
    <h2>L6 Reports &amp; Traceability</h2>
    <p>Timeline &amp; metrics placeholder. Once backend is connected, replace with real queries.</p>
    <div class="row">
      <div class="card">
        <h3>Timeline (Sample)</h3>
        <ul>
          <li>t0 Alert: road-001 rainfall spikes</li>
          <li>t1 Agent: generates a task package (inspection / traffic control prep)</li>
          <li>t2 Human approval: traffic control prep approved</li>
          <li>t3 Task receipt: inspection done, photos uploaded</li>
        </ul>
      </div>
      <div class="card">
        <h3>Metrics (Sample)</h3>
        <ul>
          <li>Total tasks: 2</li>
          <li>Completion rate: 50%</li>
          <li>Alert → dispatch latency: 3s</li>
        </ul>
      </div>
    </div>
    <p>Can be wired to backend <code>/reports/incidents/{id}</code> for timeline and metrics.</p>
  </div>
</template>

<script setup></script>

