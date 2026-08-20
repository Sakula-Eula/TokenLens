import { createRouter, createWebHistory } from "vue-router";

const routes = [
  { path: "/", redirect: "/dashboard" },
  { path: "/dashboard", name: "dashboard", component: () => import("../views/DashboardView.vue"), meta: { range: true } },
  { path: "/models", name: "models", component: () => import("../views/ModelsView.vue"), meta: { range: true } },
  { path: "/providers", name: "providers", component: () => import("../views/ProvidersView.vue"), meta: { range: true } },
  { path: "/tokens", name: "tokens", component: () => import("../views/TokensView.vue"), meta: { range: true } },
  { path: "/costs", name: "costs", component: () => import("../views/CostsView.vue") },
  { path: "/requests", name: "requests", component: () => import("../views/RequestsView.vue") },
  { path: "/errors", name: "errors", component: () => import("../views/ErrorsView.vue"), meta: { range: true } },
  { path: "/settings", name: "settings", component: () => import("../views/SettingsView.vue") },
  { path: "/:pathMatch(.*)*", redirect: "/dashboard" },
];

export default createRouter({ history: createWebHistory(), routes });
