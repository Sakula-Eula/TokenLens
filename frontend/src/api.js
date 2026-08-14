import axios from "axios";

export const POLL_INTERVAL_MS = 5000;
const http = axios.create({ baseURL: "/", timeout: 10000 });

export async function fetchSummary() {
  return (await http.get("/api/stats/summary")).data;
}
export async function fetchModels() {
  return (await http.get("/api/stats/models")).data;
}
export async function fetchProviders() {
  return (await http.get("/api/stats/providers")).data;
}
export async function fetchTrend(range) {
  return (await http.get("/api/stats/trend", { params: { range } })).data;
}
export async function fetchRequests(params) {
  return (await http.get("/api/requests", { params })).data;
}
