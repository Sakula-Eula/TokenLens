const fmt = new Intl.NumberFormat("zh-CN");
const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 4 });
const esc = (value) => String(value ?? "").replace(/[&<>\"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[char]);
const cost = (value) => value === null || value === undefined ? "待配置价格" : usd.format(value);

function metric(label, value, detail) {
  return `<article class="metric"><p>${label}</p><strong>${value}</strong><small>${detail}</small></article>`;
}

function render(data) {
  const month = data.month;
  const today = data.today;
  document.querySelector("#cards").innerHTML = [
    metric("本月请求", fmt.format(month.requests), `今日 ${fmt.format(today.requests)} 次`),
    metric("本月 token", fmt.format(month.totalTokens), `输入 ${fmt.format(month.inputTokens)} · 输出 ${fmt.format(month.outputTokens)}`),
    metric("本月估算费用", usd.format(month.costUsd), `${month.pricedRequests}/${month.requests} 笔已配置价格`),
    metric("今日 token", fmt.format(today.totalTokens), `Cached ${fmt.format(today.cachedTokens)} · Reasoning ${fmt.format(today.reasoningTokens)}`),
  ].join("");
  const budget = data.config.monthlyBudgetUsd;
  document.querySelector("#budget").value = budget ?? "";
  const ratio = budget && budget > 0 ? Math.min(100, month.costUsd / budget * 100) : 0;
  document.querySelector("#progress").style.width = `${ratio}%`;
  document.querySelector("#budget-note").textContent = budget === null ? "尚未设置预算。可在上方输入每月可用额度。" : `已用 ${usd.format(month.costUsd)} / ${usd.format(budget)}（${ratio.toFixed(1)}%），剩余估算 ${usd.format(Math.max(0, budget - month.costUsd))}。`;
  const modelRows = Object.entries(data.models).sort((a, b) => b[1].totalTokens - a[1].totalTokens).map(([model, item]) => `<tr><td>${esc(model)}</td><td>${fmt.format(item.requests)}</td><td>${fmt.format(item.inputTokens)}</td><td>${fmt.format(item.outputTokens)}</td><td>${fmt.format(item.totalTokens)}</td><td>${cost(item.costUsd)}</td></tr>`);
  document.querySelector("#models").innerHTML = modelRows.join("") || '<tr><td colspan="6" class="empty">尚无经过代理的 OpenAI 调用</td></tr>';
  document.querySelector("#recent").innerHTML = data.recent.map((item) => `<tr><td>${new Date(item.timestamp).toLocaleString("zh-CN", { hour12: false })}</td><td>${esc(item.model)}</td><td>${esc(item.endpoint)}</td><td>${fmt.format(item.totalTokens)}</td><td>${cost(item.costUsd)}</td><td>${item.statusCode}</td></tr>`).join("") || '<tr><td colspan="6" class="empty">尚无记录</td></tr>';
}

async function refresh() {
  const response = await fetch("/api/summary", { cache: "no-store" });
  if (response.ok) render(await response.json());
}

document.querySelector("#budget-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const field = document.querySelector("#budget");
  const monthlyBudgetUsd = field.value.trim() === "" ? null : Number(field.value);
  const response = await fetch("/api/config", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ monthlyBudgetUsd }) });
  if (!response.ok) alert((await response.json()).error || "保存失败");
  await refresh();
});

refresh();
setInterval(refresh, 5000);

