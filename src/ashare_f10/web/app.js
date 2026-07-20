const state = {
  backend: false,
  poller: null,
  fields: [],
  staticJson: null,
  chart: null,
};

const $ = (id) => document.getElementById(id);
const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;").replaceAll('"', "&quot;");

function toast(message, error = false) {
  const node = $("toast");
  node.textContent = message;
  node.className = `toast show${error ? " error" : ""}`;
  setTimeout(() => { node.className = "toast"; }, 3500);
}

async function api(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try { detail = (await response.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  const contentType = response.headers.get("content-type") || "";
  return contentType.includes("application/json") ? response.json() : response;
}

async function detectBackend() {
  try {
    await api("/api/health");
    state.backend = true;
    $("modeBadge").textContent = "本地 / 服务端模式";
    $("modeBadge").style.background = "rgba(48,198,132,.25)";
    refreshJobs();
  } catch (_) {
    state.backend = false;
    $("modeBadge").textContent = "GitHub Pages 静态模式";
    $("modeBadge").style.background = "rgba(255,196,87,.25)";
  }
}

document.querySelectorAll("#tabs button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("#tabs button").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    button.classList.add("active");
    $(`tab-${button.dataset.tab}`).classList.add("active");
  });
});

function formatNumber(value, unit = "") {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  if (Number.isNaN(number)) return String(value);
  const abs = Math.abs(number);
  let formatted;
  if (abs >= 1e8) formatted = `${(number / 1e8).toLocaleString(undefined, { maximumFractionDigits: 2 })}亿`;
  else if (abs >= 1e4) formatted = `${(number / 1e4).toLocaleString(undefined, { maximumFractionDigits: 2 })}万`;
  else formatted = number.toLocaleString(undefined, { maximumFractionDigits: 4 });
  return `${formatted}${unit || ""}`;
}

function renderTable(container, rows, columns) {
  if (!rows || rows.length === 0) {
    container.innerHTML = '<div class="empty" style="padding:18px">暂无数据</div>';
    return;
  }
  container.innerHTML = `<table><thead><tr>${columns.map((c) => `<th>${escapeHtml(c.label)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${columns.map((c) => `<td>${escapeHtml(c.format ? c.format(row[c.key], row) : row[c.key])}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

$("startJob").addEventListener("click", async () => {
  if (!state.backend) return toast("静态模式无法直接运行Python，请使用GitHub Actions或本地后端。", true);
  const stockCode = $("stockCode").value.trim();
  if (!/^\d{6}$/.test(stockCode)) return toast("请输入6位股票代码", true);
  try {
    const job = await api("/api/jobs", { method: "POST", body: JSON.stringify({ stock_code: stockCode, resume: true }) });
    toast(`任务已创建：${job.job_id}`);
    refreshJobs();
  } catch (error) { toast(error.message, true); }
});

$("refreshJobs").addEventListener("click", refreshJobs);
async function refreshJobs() {
  if (!state.backend) return;
  try {
    const jobs = await api("/api/jobs?limit=30");
    const container = $("jobList");
    if (!jobs.length) { container.className = "job-list empty"; container.textContent = "暂无任务"; return; }
    container.className = "job-list";
    container.innerHTML = jobs.map((job) => {
      const pct = job.total_groups ? Math.min(100, Math.round(job.completed_groups / job.total_groups * 100)) : 0;
      const files = job.status === "COMPLETED" ? `<div>${["json", "excel", "parquet", "duckdb"].filter((k) => job.artifacts[k]).map((k) => `<a href="/api/stocks/${job.stock_code}/download/${k}" target="_blank">${k.toUpperCase()}</a>`).join(" · ")}</div>` : "";
      return `<div class="job-card"><div class="job-title"><strong>${escapeHtml(job.stock_code)} · ${escapeHtml(job.job_id)}</strong><span class="status ${job.status}">${job.status}</span></div><div class="progress"><div style="width:${pct}%"></div></div><div class="muted">${escapeHtml(job.message)} ${job.current_group ? `· ${escapeHtml(job.current_group)}` : ""}</div><div>${job.completed_groups}/${job.total_groups}，失败 ${job.failed_groups}</div>${files}</div>`;
    }).join("");
    if (jobs.some((job) => ["PENDING", "RUNNING"].includes(job.status))) {
      clearTimeout(state.poller); state.poller = setTimeout(refreshJobs, 2500);
    }
  } catch (error) { toast(error.message, true); }
}

$("loadOverview").addEventListener("click", loadOverview);
async function loadOverview() {
  const code = $("overviewCode").value.trim();
  try {
    const data = await api(`/api/stocks/${code}/latest`);
    const o = data.overview;
    $("overviewStats").innerHTML = [
      ["事实记录", o.fact_count], ["字段数量", o.field_count], ["接口家族", o.family_count],
      ["最早报告期", o.min_report_date || "—"], ["最新报告期", o.max_report_date || "—"],
    ].map(([label, value]) => `<div class="metric"><div class="label">${label}</div><div class="value">${escapeHtml(value)}</div></div>`).join("");
    renderTable($("overviewTable"), o.latest_metrics, [
      { key: "field_name_cn", label: "项目" }, { key: "field_key", label: "原始Key" },
      { key: "report_date", label: "报告期" }, { key: "value_num", label: "数值", format: (v, r) => formatNumber(v, r.unit) },
      { key: "family", label: "来源接口" },
    ]);
    renderOverviewChart(code, o.latest_metrics);
  } catch (error) { toast(error.message, true); }
}

async function renderOverviewChart(code, metrics) {
  const preferred = metrics.find((m) => m.field_key === "TOTAL_OPERATE_INCOME") || metrics[0];
  if (!preferred || !window.echarts) return;
  const rows = await api(`/api/stocks/${code}/search?q=${encodeURIComponent(preferred.field_key)}&limit=80`);
  const points = rows.filter((r) => r.field_key === preferred.field_key && r.report_date && r.value_num !== null)
    .sort((a, b) => a.report_date.localeCompare(b.report_date));
  if (state.chart) state.chart.dispose();
  state.chart = echarts.init($("overviewChart"));
  state.chart.setOption({
    tooltip: { trigger: "axis" }, title: { text: preferred.field_name_cn },
    xAxis: { type: "category", data: points.map((p) => p.report_date), axisLabel: { rotate: 45 } },
    yAxis: { type: "value" }, series: [{ type: "line", smooth: true, data: points.map((p) => p.value_num) }],
    grid: { left: 70, right: 30, bottom: 90, top: 60 },
  });
}

$("runSearch").addEventListener("click", runSearch);
async function runSearch() {
  const code = $("searchCode").value.trim();
  const params = new URLSearchParams({ q: $("searchQuery").value.trim(), limit: "300" });
  [["start_date", "startDate"], ["end_date", "endDate"], ["numeric_min", "numericMin"], ["numeric_max", "numericMax"]].forEach(([key, id]) => { if ($(id).value) params.set(key, $(id).value); });
  try {
    const rows = await api(`/api/stocks/${code}/search?${params}`);
    $("searchCount").textContent = `${rows.length} 条`;
    renderTable($("searchResults"), rows, [
      { key: "report_date", label: "报告期" }, { key: "event_date", label: "事件日期" },
      { key: "theme", label: "区块" }, { key: "field_name_cn", label: "项目名称" },
      { key: "field_key", label: "原始Key" }, { key: "value_num", label: "数值", format: (v, r) => v !== null ? formatNumber(v, r.unit) : r.value_text },
      { key: "family", label: "接口" }, { key: "score", label: "匹配度" },
    ]);
  } catch (error) { toast(error.message, true); }
}

async function loadPeriodsAndFields(code) {
  try {
    const [periods, fields] = await Promise.all([api(`/api/stocks/${code}/periods`), api(`/api/stocks/${code}/fields?limit=500`)]);
    state.fields = fields;
    [$("ttmPeriod"), $("formulaPeriod")].forEach((select) => { select.innerHTML = periods.map((p) => `<option value="${p}">${p}</option>`).join(""); });
    renderFields(fields);
  } catch (error) { toast(error.message, true); }
}

function renderFields(fields) {
  $("fieldList").innerHTML = fields.slice(0, 300).map((f) => `<div class="field-item" data-key="${escapeHtml(f.field_key)}"><strong>${escapeHtml(f.field_name_cn)}</strong><small>${escapeHtml(f.field_key)} · ${escapeHtml(f.unit)} · ${f.observations}条</small></div>`).join("");
  document.querySelectorAll(".field-item").forEach((item) => item.addEventListener("click", () => {
    const key = item.dataset.key;
    $("formulaText").value += ($("formulaText").value ? " " : "") + key;
    $("ttmField").value = key;
  }));
}

$("fieldQuery").addEventListener("input", () => {
  const q = $("fieldQuery").value.toLowerCase();
  renderFields(state.fields.filter((f) => `${f.field_name_cn} ${f.field_key}`.toLowerCase().includes(q)));
});

$("ttmCode").addEventListener("change", () => loadPeriodsAndFields($("ttmCode").value.trim()));
$("runTTM").addEventListener("click", async () => {
  const code = $("ttmCode").value.trim();
  try {
    const result = await api(`/api/stocks/${code}/ttm`, { method: "POST", body: JSON.stringify({ field: $("ttmField").value.trim(), end_period: $("ttmPeriod").value }) });
    $("ttmResult").textContent = JSON.stringify(result, null, 2);
  } catch (error) { $("ttmResult").textContent = error.message; }
});

$("runFormula").addEventListener("click", async () => {
  const code = $("formulaCode").value.trim();
  try {
    const result = await api(`/api/stocks/${code}/formula`, { method: "POST", body: JSON.stringify({ formula: $("formulaText").value.trim(), end_period: $("formulaPeriod").value || null }) });
    $("formulaResult").textContent = JSON.stringify(result, null, 2);
  } catch (error) { $("formulaResult").textContent = error.message; }
});

$("loadQuality").addEventListener("click", async () => {
  const code = $("qualityCode").value.trim();
  try {
    const data = await api(`/api/stocks/${code}/latest`);
    $("downloadCards").innerHTML = Object.entries(data.pointer.artifacts).filter(([, path]) => typeof path === "string" && path.includes(".")).map(([kind, path]) => `<div class="download-card"><strong>${kind.toUpperCase()}</strong><div class="muted">${escapeHtml(path.split(/[\\/]/).pop())}</div><a href="/api/stocks/${code}/download/${kind}" target="_blank">下载文件</a></div>`).join("");
  } catch (error) { toast(error.message, true); }
});

$("jsonUpload").addEventListener("change", async (event) => {
  const file = event.target.files[0]; if (!file) return;
  try {
    state.staticJson = JSON.parse(await file.text());
    const groups = state.staticJson.groups || [];
    const records = groups.reduce((sum, g) => sum + (g.records?.length || 0), 0);
    $("staticSummary").innerHTML = [["请求组", groups.length], ["记录数", records], ["证券", state.staticJson.metadata?.security?.secucode || "—"]].map(([l,v]) => `<div class="metric"><div class="label">${l}</div><div class="value">${escapeHtml(v)}</div></div>`).join("");
    toast("JSON已载入");
  } catch (error) { toast(`JSON解析失败：${error.message}`, true); }
});

$("staticSearch").addEventListener("click", () => {
  if (!state.staticJson) return toast("请先上传JSON", true);
  const q = $("staticQuery").value.trim().toLowerCase();
  const results = [];
  for (const group of state.staticJson.groups || []) {
    for (const record of group.records || []) {
      for (const [key, value] of Object.entries(record)) {
        const haystack = `${group.theme} ${group.family} ${key} ${JSON.stringify(value)}`.toLowerCase();
        if (!q || haystack.includes(q)) results.push({ theme: group.theme, family: group.family, key, value: typeof value === "object" ? JSON.stringify(value) : value });
        if (results.length >= 300) break;
      }
      if (results.length >= 300) break;
    }
    if (results.length >= 300) break;
  }
  renderTable($("staticResults"), results, [
    { key: "theme", label: "区块" }, { key: "family", label: "接口" }, { key: "key", label: "字段Key" }, { key: "value", label: "值" },
  ]);
});

// Default initialization.
detectBackend().then(() => {
  if (state.backend) loadPeriodsAndFields($("ttmCode").value.trim());
});
