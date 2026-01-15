<template>
  <div class="l2">
    <div class="stack">
      <OntologyPanel
        :api-base="apiBase"
        scope="draft"
        title="Draft Graph (Current Document)"
        subtitle="Upload → DeepSeek extraction → saved to draft graph → query/edit → commit to formal graph"
        :draft-id="draftId"
        @draft-created="onDraftCreated"
        @draft-cleared="onDraftCleared"
        @committed="onCommitted"
      />

      <OntologyPanel
        :api-base="apiBase"
        scope="formal"
        title="Formal Graph (Full)"
        subtitle="Browse and maintain the full graph database; query/edit supported"
        :draft-id="draftId"
        @purged="onPurged"
      />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from "vue";
import OntologyPanel from "../../components/OntologyPanel.vue";

defineProps({
  apiBase: { type: String, required: true },
});

// Prevent draftId loss on reload/component remount
const DRAFT_ID_STORAGE_KEY = "pipe-china:draftId";
const draftId = ref("");

onMounted(() => {
  try {
    draftId.value = sessionStorage.getItem(DRAFT_ID_STORAGE_KEY) || "";
  } catch {
    // ignore
  }
});

watch(
  () => draftId.value,
  (v) => {
    try {
      if (v) sessionStorage.setItem(DRAFT_ID_STORAGE_KEY, v);
      else sessionStorage.removeItem(DRAFT_ID_STORAGE_KEY);
    } catch {
      // ignore
    }
  }
);

function onDraftCreated(id) {
  draftId.value = id;
}
function onDraftCleared() {
  draftId.value = "";
}
function onCommitted() {
  // The formal graph panel refreshes itself
}
function onPurged() {
  draftId.value = "";
}
</script>

<style scoped>
.l2 {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.stack {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
</style>

