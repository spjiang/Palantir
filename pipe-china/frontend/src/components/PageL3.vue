<template>
  <div class="card">
    <h2>L3 风险推理/模型</h2>
    <p>数字孪生地图占位：以北京海淀区“东北旺西路8号院”作为中心，展示风险 TopN 列表。</p>
    <div class="row">
      <div class="card">
        <h3>地图占位</h3>
        <p>可替换为 Mapbox/Cesium；当前为占位示意。</p>
        <pre>中心: 北京市海淀区东北旺西路8号院中关村软件园一期尚东数字谷A区</pre>
      </div>
      <div class="card">
        <h3>风险 TopN（示例数据）</h3>
        <ul>
          <li>road-001 · 风险 红 · explain: 雨强上升/低洼/排水不足</li>
          <li>road-002 · 风险 橙 · explain: 泵站故障/雨强上升</li>
          <li>road-003 · 风险 橙 · explain: 交通拥堵/排水不足</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
</script>
