import axios from "axios";

// The standalone /widget keeps its original 30-second cadence. Full pages
// receive their configurable interval from App.vue.
export const POLL_INTERVAL_MS = 30000;
const http = axios.create({ baseURL: "/", timeout: 10000 });

export async function fetchSummary(range = "24h") {
  return (await http.get("/api/stats/summary", { params: { range } })).data;
}
export async function fetchModels(range = "24h", params = {}) {
  return (await http.get("/api/stats/models", { params: { range, ...params } })).data;
}
export async function fetchProviders(range = "24h", params = {}) {
  return (await http.get("/api/stats/providers", { params: { range, ...params } })).data;
}
export async function fetchTrend(range, params = {}) {
  return (await http.get("/api/stats/trend", { params: { range, ...params } })).data;
}
export async function fetchRequests(params) {
  return (await http.get("/api/requests", { params })).data;
}
export async function fetchRequestDetail(id) {
  return (await http.get(`/api/requests/${id}`)).data;
}
export async function fetchErrors(range = "24h", params = {}) {
  return (await http.get("/api/stats/errors", { params: { range, ...params } })).data;
}
export async function fetchProviderSettings() {
  return (await http.get("/api/settings/providers")).data;
}
export async function saveProviderSettings(items) {
  return (await http.put("/api/settings/providers", { items })).data;
}
