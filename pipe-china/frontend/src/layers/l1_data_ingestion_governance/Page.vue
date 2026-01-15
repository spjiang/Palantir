<template>
  <div class="card">
    <h2>L1 Data Ingestion &amp; Governance</h2>
    <p>Demo scope: show a static data flow (ingest → standardize → load into ontology).</p>
    <div class="row">
      <div class="card">
        <h3>Data Flow</h3>
        <ul>
          <li>Raw: rainfall / water level / pipeline operations / alert events</li>
          <li>Standardized: units / coordinates / enums unified, DQ tags applied</li>
          <li>Ontology load: write entities &amp; relations for downstream models/agents</li>
        </ul>
      </div>
      <div class="card">
        <h3>Data Quality (Example)</h3>
        <ul>
          <li>freshness: 0.95</li>
          <li>validity: true</li>
          <li>latency(p95): 3s</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup></script>

