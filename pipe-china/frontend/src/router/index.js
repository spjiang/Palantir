import { createRouter, createWebHistory } from "vue-router";
import { h } from "vue";

import AdminLayout from "../layouts/AdminLayout.vue";

// L1~L6 概览页（现有内容）
import L1Overview from "../layers/l1_data_ingestion_governance/Page.vue";
import L2Overview from "../layers/l2_ontology_semantics/Page.vue";
import L3Overview from "../layers/l3_risk_reasoning_models/Page.vue";
import L4Overview from "../layers/l4_agent_decision_making/Page.vue";
import L5Overview from "../layers/l5_closed_loop_execution_workflow/Page.vue";
import L6Overview from "../layers/l6_reports_traceability/Page.vue";

// L2 拆分后的功能页
import L2Draft from "../layers/l2_ontology_semantics/Draft.vue";
import L2Formal from "../layers/l2_ontology_semantics/Formal.vue";

// 其它层的示例功能页（占位，后续可替换为真实功能）
import L1DataQuality from "../layers/l1_data_ingestion_governance/DataQuality.vue";
import L3RiskTopN from "../layers/l3_risk_reasoning_models/RiskTopN.vue";
import L4Chat from "../layers/l4_agent_decision_making/Chat.vue";
import L5Tasks from "../layers/l5_closed_loop_execution_workflow/Tasks.vue";
import L6Timeline from "../layers/l6_reports_traceability/Timeline.vue";

const LayerOutlet = { render: () => h("router-view") };

const routes = [
  { path: "/", redirect: "/l2/draft" },
  {
    path: "/",
    component: AdminLayout,
    children: [
      {
        path: "l1",
        component: LayerOutlet,
        meta: {
          layerKey: "l1",
          layerTitle: "L1 数据接入与治理",
          sidebar: [
            { label: "概览", to: "/l1/overview" },
            { label: "数据质量", to: "/l1/data-quality" },
          ],
        },
        children: [
          { path: "overview", component: L1Overview },
          { path: "data-quality", component: L1DataQuality },
          { path: "", redirect: "/l1/overview" },
        ],
      },
      {
        path: "l2",
        component: LayerOutlet,
        meta: {
          layerKey: "l2",
          layerTitle: "L2 本体/语义选型",
          sidebar: [
            { label: "概览", to: "/l2/overview" },
            { label: "草稿图谱（抽取/编辑）", to: "/l2/draft" },
            { label: "正式图谱（查询/维护）", to: "/l2/formal" },
          ],
        },
        children: [
          { path: "overview", component: L2Overview },
          { path: "draft", component: L2Draft },
          { path: "formal", component: L2Formal },
          { path: "", redirect: "/l2/draft" },
        ],
      },
      {
        path: "l3",
        component: LayerOutlet,
        meta: {
          layerKey: "l3",
          layerTitle: "L3 风险推理/模型",
          sidebar: [
            { label: "概览", to: "/l3/overview" },
            { label: "风险 TopN", to: "/l3/risk-topn" },
          ],
        },
        children: [
          { path: "overview", component: L3Overview },
          { path: "risk-topn", component: L3RiskTopN },
          { path: "", redirect: "/l3/overview" },
        ],
      },
      {
        path: "l4",
        component: LayerOutlet,
        meta: {
          layerKey: "l4",
          layerTitle: "L4 智能体决策",
          sidebar: [
            { label: "概览", to: "/l4/overview" },
            { label: "对话", to: "/l4/chat" },
          ],
        },
        children: [
          { path: "overview", component: L4Overview },
          { path: "chat", component: L4Chat },
          { path: "", redirect: "/l4/overview" },
        ],
      },
      {
        path: "l5",
        component: LayerOutlet,
        meta: {
          layerKey: "l5",
          layerTitle: "L5 执行闭环/工作流",
          sidebar: [
            { label: "概览", to: "/l5/overview" },
            { label: "任务列表", to: "/l5/tasks" },
          ],
        },
        children: [
          { path: "overview", component: L5Overview },
          { path: "tasks", component: L5Tasks },
          { path: "", redirect: "/l5/overview" },
        ],
      },
      {
        path: "l6",
        component: LayerOutlet,
        meta: {
          layerKey: "l6",
          layerTitle: "L6 战报与追溯",
          sidebar: [
            { label: "概览", to: "/l6/overview" },
            { label: "时间线", to: "/l6/timeline" },
          ],
        },
        children: [
          { path: "overview", component: L6Overview },
          { path: "timeline", component: L6Timeline },
          { path: "", redirect: "/l6/overview" },
        ],
      },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior() {
    return { top: 0 };
  },
});

export default router;

