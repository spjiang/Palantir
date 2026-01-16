<template>
  <div class="admin">
    <header class="topbar">
      <div class="brand">
        <div class="brand-title">Pipe-China</div>
        <div class="brand-sub">行为建模演示（后台管理）</div>
      </div>

      <nav class="topnav">
        <RouterLink class="nav-item" :class="{ active: isActiveLayer('l1') }" to="/l1/overview">L1 数据接入与治理</RouterLink>
        <RouterLink class="nav-item" :class="{ active: isActiveLayer('l2') }" to="/l2/draft">L2 本体/语义选型</RouterLink>
        <RouterLink class="nav-item" :class="{ active: isActiveLayer('l3') }" to="/l3/overview">L3 风险推理/模型</RouterLink>
        <RouterLink class="nav-item" :class="{ active: isActiveLayer('l4') }" to="/l4/overview">L4 智能体决策</RouterLink>
        <RouterLink class="nav-item" :class="{ active: isActiveLayer('l5') }" to="/l5/overview">L5 执行闭环/工作流</RouterLink>
        <RouterLink class="nav-item" :class="{ active: isActiveLayer('l6') }" to="/l6/overview">L6 战报与追溯</RouterLink>
      </nav>

      <div class="api">
        <span class="api-label">API</span>
        <span class="api-val mono">{{ apiBase }}</span>
      </div>
    </header>

    <div class="main">
      <aside class="sidebar">
        <div class="side-title">{{ currentLayerTitle }}</div>
        <div class="side-menu">
          <RouterLink v-for="it in sidebarItems" :key="it.to" class="side-item" :to="it.to">
            {{ it.label }}
          </RouterLink>
        </div>
      </aside>

      <section class="content">
        <!-- 通过 v-slot 显式把 apiBase 传给每个页面组件 -->
        <RouterView v-slot="{ Component }">
          <component :is="Component" :api-base="apiBase" />
        </RouterView>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();

// 与旧 App.vue 保持一致的 apiBase 推导
const apiBase = computed(() => {
  const fromEnv = import.meta.env.VITE_API_BASE;
  const envVal = fromEnv ? String(fromEnv).trim() : "";
  if (envVal && !/^https?:\/\/(localhost|127\.0\.0\.1)(:|\/|$)/i.test(envVal)) return envVal;
  const proto = window.location.protocol;
  const host = window.location.hostname;
  return `${proto}//${host}:18088`;
});

const layerMeta = computed(() => {
  // 从匹配链里找到最近的 layer meta（带 sidebar/layerTitle 的那个）
  for (let i = route.matched.length - 1; i >= 0; i--) {
    const m = route.matched[i];
    if (m?.meta?.layerTitle && m?.meta?.sidebar) return m.meta;
  }
  return { layerTitle: "", sidebar: [] };
});

const currentLayerTitle = computed(() => layerMeta.value.layerTitle || "");
const sidebarItems = computed(() => layerMeta.value.sidebar || []);

function isActiveLayer(key) {
  return String(route.path || "").startsWith(`/${key}`);
}
</script>

<style scoped>
.admin {
  min-height: 100vh;
  background: transparent;
  color: var(--text);
}
.topbar {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 0 16px;
  background: linear-gradient(180deg, rgba(2, 6, 23, 0.88), rgba(2, 6, 23, 0.72));
  color: #e2e8f0;
  border-bottom: 1px solid var(--border);
  backdrop-filter: blur(10px);
}
.brand {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 180px;
}
.brand-title {
  font-weight: 900;
  letter-spacing: 0.2px;
}
.brand-sub {
  font-size: 12px;
  color: rgba(226, 232, 240, 0.7);
}
.topnav {
  display: flex;
  gap: 8px;
  flex: 1;
  overflow: auto;
}
.nav-item {
  white-space: nowrap;
  text-decoration: none;
  color: rgba(226, 232, 240, 0.88);
  padding: 7px 10px; /* 更紧凑 */
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(148, 163, 184, 0.06);
}
.nav-item.active {
  background: linear-gradient(90deg, rgba(34, 211, 238, 0.22), rgba(99, 102, 241, 0.18));
  border-color: rgba(34, 211, 238, 0.55);
  color: #ffffff;
  box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.12);
}
.api {
  display: flex;
  gap: 8px;
  align-items: center;
  min-width: 280px;
  justify-content: flex-end;
}
.api-label {
  font-size: 12px;
  color: rgba(226, 232, 240, 0.7);
}
.api-val {
  font-size: 12px;
  color: rgba(226, 232, 240, 0.92);
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.main {
  display: grid;
  grid-template-columns: 240px 1fr;
  min-height: calc(100vh - 64px);
}
.sidebar {
  background: linear-gradient(180deg, rgba(2, 6, 23, 0.72), rgba(2, 6, 23, 0.55));
  color: rgba(226, 232, 240, 0.92);
  border-right: 1px solid var(--border);
  padding: 12px 10px; /* 更紧凑 */
  backdrop-filter: blur(10px);
}
.side-title {
  font-weight: 900;
  margin-bottom: 10px;
}
.side-menu {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.side-item {
  text-decoration: none;
  color: rgba(226, 232, 240, 0.85);
  padding: 9px 10px; /* 更紧凑 */
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  background: rgba(148, 163, 184, 0.06);
}
.side-item.router-link-active {
  background: linear-gradient(90deg, rgba(34, 211, 238, 0.14), rgba(99, 102, 241, 0.12));
  border-color: rgba(34, 211, 238, 0.45);
  color: #fff;
}
.content {
  padding: 12px; /* 更紧凑 */
  overflow: auto;
}
</style>

