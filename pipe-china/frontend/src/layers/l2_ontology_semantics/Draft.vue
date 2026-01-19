<template>
  <div>
    <OntologyPanel
      :api-base="apiBase"
      scope="draft"
      title="临时本体库（当前文档）"
      subtitle="上传业务方案 → DeepSeek 抽取 → 存入临时本体库 → 查询/编辑 → 确认后入库正式本体库"
      :draft-id="draftId"
      @draft-created="onDraftCreated"
      @draft-cleared="onDraftCleared"
      @committed="onCommitted"
    />
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from "vue";
import OntologyPanel from "../../components/OntologyPanel.vue";

defineProps({
  apiBase: { type: String, required: true },
});

// 避免“页面被刷新/组件重载”导致 draftId 丢失，从而草稿画布清空
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
  // 正式本体库页面会自行刷新；这里不需要额外操作
}
</script>

