const state = {
  backend: false,
  poller: null,
  fields: [],
  chart: null,
  searchGrid: null,
  searchSteps: [],
  searchHistory: [],
  searchRedo: [],
  searchStageCounts: [],
  staticGrid: null,
  staticSteps: [],
  staticStageCounts: [],
  staticWorker: null,
  staticPending: new Map(),
  staticRequestId: 0,
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
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
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
    document.querySelectorAll("#tabs button").forEach((item) => item.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.remove("active"));
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
  container.innerHTML = `<table><thead><tr>${columns.map((column) => `<th>${escapeHtml(column.label)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${columns.map((column) => `<td>${escapeHtml(column.format ? column.format(row[column.key], row) : row[column.key])}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

function downloadBlob(content, filename, type = "text/csv;charset=utf-8") {
  const blob = content instanceof Blob ? content : new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

$("startJob").addEventListener("click", async () => {
  if (!state.backend) return toast("静态模式无法直接运行Python，请使用GitHub Actions或本地后端。", true);
  const stockCode = $("stockCode").value.trim();
  if (!/^\d{6}$/.test(stockCode)) return toast("请输入6位股票代码", true);
  try {
    if (typeof window.startFullCrossValidation !== "function") throw new Error("双源验证模块尚未加载");
    const task = await window.startFullCrossValidation(stockCode);
    toast(`双源任务已创建：${task.task_id}`);
    document.querySelector('#tabs button[data-tab="validation"]')?.click();
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
      const files = job.status === "COMPLETED" ? `<div>${["json", "excel", "parquet", "duckdb"].filter((key) => job.artifacts[key]).map((key) => `<a href="/api/stocks/${job.stock_code}/download/${key}" target="_blank">${key.toUpperCase()}</a>`).join(" · ")}</div>` : "";
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
    const overview = data.overview;
    $("overviewStats").innerHTML = [
      ["事实记录", overview.fact_count], ["字段数量", overview.field_count], ["接口家族", overview.family_count],
      ["最早报告期", overview.min_report_date || "—"], ["最新报告期", overview.max_report_date || "—"],
    ].map(([label, value]) => `<div class="metric"><div class="label">${label}</div><div class="value">${escapeHtml(value)}</div></div>`).join("");
    renderTable($("overviewTable"), overview.latest_metrics, [
      { key: "field_name_cn", label: "项目" }, { key: "field_key", label: "原始Key" },
      { key: "report_date", label: "报告期" }, { key: "value_num", label: "数值", format: (value, row) => formatNumber(value, row.unit) },
      { key: "family", label: "来源接口" },
    ]);
    renderOverviewChart(code, overview.latest_metrics);
  } catch (error) { toast(error.message, true); }
}

async function renderOverviewChart(code, metrics) {
  const preferred = metrics.find((metric) => metric.field_key === "TOTAL_OPERATE_INCOME") || metrics[0];
  if (!preferred || !window.echarts) return;
  const rows = await api(`/api/stocks/${code}/search?q=${encodeURIComponent(preferred.field_key)}&limit=80`);
  const points = rows.filter((row) => row.field_key === preferred.field_key && row.report_date && row.value_num !== null)
    .sort((left, right) => left.report_date.localeCompare(right.report_date));
  if (state.chart) state.chart.dispose();
  state.chart = echarts.init($("overviewChart"));
  state.chart.setOption({
    tooltip: { trigger: "axis" }, title: { text: preferred.field_name_cn },
    xAxis: { type: "category", data: points.map((point) => point.report_date), axisLabel: { rotate: 45 } },
    yAxis: { type: "value" }, series: [{ type: "line", smooth: true, data: points.map((point) => point.value_num) }],
    grid: { left: 70, right: 30, bottom: 90, top: 60 },
  });
}

const SEARCH_COLUMNS = [
  { key: "report_date", label: "报告期", type: "date", width: 125 },
  { key: "event_date", label: "事件日期", type: "date", width: 125 },
  { key: "theme", label: "区块", type: "text", width: 150 },
  { key: "field_name_cn", label: "项目名称", type: "text", width: 310 },
  { key: "field_key", label: "原始Key", type: "text", width: 250 },
  { key: "value_num", label: "数值", type: "number", width: 140, format: (value, row) => value !== null ? formatNumber(value, row.unit) : row.value_text },
  { key: "unit", label: "单位", type: "text", width: 90 },
  { key: "family", label: "接口", type: "text", width: 250 },
  { key: "dataset", label: "数据集", type: "text", width: 220 },
  { key: "score", label: "综合匹配度", type: "number", width: 120, format: (value) => Number(value || 0).toFixed(1) },
];

function baseRangeFilters(prefix = "") {
  const filters = [];
  const start = $(`${prefix}startDate`)?.value;
  const end = $(`${prefix}endDate`)?.value;
  const min = $(`${prefix}numericMin`)?.value;
  const max = $(`${prefix}numericMax`)?.value;
  if (start && end) filters.push({ column: "effective_date", operator: "between", lower: start, upper: end, enabled: true });
  else if (start) filters.push({ column: "effective_date", operator: "gte", value: start, enabled: true });
  else if (end) filters.push({ column: "effective_date", operator: "lte", value: end, enabled: true });
  if (min !== "" && min !== undefined) filters.push({ column: "value_num", operator: "gte", value: Number(min), enabled: true });
  if (max !== "" && max !== undefined) filters.push({ column: "value_num", operator: "lte", value: Number(max), enabled: true });
  return filters;
}

function buildBackendQuery() {
  return {
    base_query: $("searchQuery").value.trim(),
    base_match_type: $("baseMatchType").value,
    base_columns: [],
    base_threshold: Number($("baseThreshold").value || 60),
    search_steps: state.searchSteps,
    filters: baseRangeFilters(""),
    sort: [],
    page: 1,
    page_size: 200,
  };
}

function selectedStepColumns(prefix = "secondary") {
  return [...document.querySelectorAll(`[data-${prefix}-column]:checked`)].map((input) => input.value);
}

function snapshotSearchSteps() {
  state.searchHistory.push(JSON.stringify(state.searchSteps));
  if (state.searchHistory.length > 30) state.searchHistory.shift();
  state.searchRedo = [];
}

function renderSearchChain() {
  const panel = $("searchChainPanel");
  panel.classList.toggle("active", Boolean(state.searchGrid?.state.result || state.searchSteps.length));
  $("searchStepList").innerHTML = state.searchSteps.length ? state.searchSteps.map((step, index) => `
    <span class="search-step${step.enabled === false ? " disabled" : ""}">
      ${escapeHtml(step.operation)} · ${escapeHtml(step.match_type)} · ${escapeHtml(step.query || step.match_type)}
      <button type="button" data-step-action="toggle" data-index="${index}" title="启用/禁用">${step.enabled === false ? "启用" : "暂停"}</button>
      <button type="button" data-step-action="remove" data-index="${index}" title="删除">×</button>
    </span>`).join("") : '<span class="muted">尚未添加二次搜索条件</span>';
  $("searchStageCounts").innerHTML = state.searchStageCounts.map((stage) => `<span class="search-stage">${escapeHtml(stage.label)}：${Number(stage.count).toLocaleString()}条</span>`).join("");
}

$("searchStepList").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-step-action]");
  if (!button) return;
  snapshotSearchSteps();
  const index = Number(button.dataset.index);
  if (button.dataset.stepAction === "remove") state.searchSteps.splice(index, 1);
  else state.searchSteps[index].enabled = state.searchSteps[index].enabled === false;
  renderSearchChain();
  state.searchGrid.load(1);
});

function initializeBackendGrid() {
  if (state.searchGrid) return;
  state.searchGrid = new ResearchGrid($("searchResults"), {
    columns: SEARCH_COLUMNS,
    pageSize: 200,
    persistKey: "f10-backend-search-grid-v2",
    getQuery: buildBackendQuery,
    fetchRows: (query) => {
      const code = $("searchCode").value.trim();
      return api(`/api/stocks/${code}/search/query`, { method: "POST", body: JSON.stringify(query) });
    },
    fetchFacet: (column, term, query) => {
      const code = $("searchCode").value.trim();
      return api(`/api/stocks/${code}/search/facets`, {
        method: "POST",
        body: JSON.stringify({ query, column, term, limit: 200 }),
      });
    },
    exportRows: async (query) => {
      const code = $("searchCode").value.trim();
      const response = await api(`/api/stocks/${code}/search/export`, {
        method: "POST",
        body: JSON.stringify({ query, format: "csv", max_rows: 100000 }),
      });
      downloadBlob(await response.blob(), `${code}-search-results.csv`);
    },
    onResult: (result) => {
      state.searchStageCounts = result.stage_counts || [];
      $("searchCount").textContent = `${Number(result.total).toLocaleString()} 条`;
      renderSearchChain();
    },
    onError: (error) => toast(error.message, true),
    onNotice: (message) => toast(message),
  });
}

$("runSearch").addEventListener("click", () => {
  if (!state.backend) return toast("请在本地/服务端模式使用完整搜索，或切换到静态文件查看。", true);
  if (!/^\d{6}$/.test($("searchCode").value.trim())) return toast("请输入6位股票代码", true);
  state.searchSteps = [];
  state.searchHistory = [];
  state.searchRedo = [];
  initializeBackendGrid();
  renderSearchChain();
  state.searchGrid.load(1);
});

$("addSecondarySearch").addEventListener("click", () => {
  const query = $("secondaryQuery").value.trim();
  const matchType = $("secondaryMatchType").value;
  if (!query && !["empty", "not_empty"].includes(matchType)) return toast("请输入二次搜索词", true);
  snapshotSearchSteps();
  state.searchSteps.push({
    query,
    operation: $("secondaryOperation").value,
    match_type: matchType,
    columns: selectedStepColumns("secondary"),
    threshold: Number($("secondaryThreshold").value || 60),
    enabled: true,
  });
  $("secondaryQuery").value = "";
  renderSearchChain();
  state.searchGrid.load(1);
});

$("undoSearchStep").addEventListener("click", () => {
  if (!state.searchHistory.length) return;
  state.searchRedo.push(JSON.stringify(state.searchSteps));
  state.searchSteps = JSON.parse(state.searchHistory.pop());
  renderSearchChain();
  state.searchGrid.load(1);
});

$("redoSearchStep").addEventListener("click", () => {
  if (!state.searchRedo.length) return;
  state.searchHistory.push(JSON.stringify(state.searchSteps));
  state.searchSteps = JSON.parse(state.searchRedo.pop());
  renderSearchChain();
  state.searchGrid.load(1);
});

$("clearSecondarySearch").addEventListener("click", () => {
  if (!state.searchSteps.length) return;
  snapshotSearchSteps();
  state.searchSteps = [];
  renderSearchChain();
  state.searchGrid.load(1);
});

$("resetAllSearch").addEventListener("click", () => {
  state.searchSteps = [];
  state.searchHistory = [];
  state.searchRedo = [];
  ["searchQuery", "startDate", "endDate", "numericMin", "numericMax"].forEach((id) => { $(id).value = ""; });
  if (state.searchGrid) {
    state.searchGrid.state.filters = [];
    state.searchGrid.state.sort = [];
    state.searchGrid.renderFilterChips();
    state.searchGrid.renderHeader();
    state.searchGrid.load(1);
  }
  renderSearchChain();
});

async function loadPeriodsAndFields(code) {
  try {
    const [periods, fields] = await Promise.all([api(`/api/stocks/${code}/periods`), api(`/api/stocks/${code}/fields?limit=500`)]);
    state.fields = fields;
    [$("ttmPeriod"), $("formulaPeriod")].forEach((select) => { select.innerHTML = periods.map((period) => `<option value="${period}">${period}</option>`).join(""); });
    renderFields(fields);
  } catch (error) { toast(error.message, true); }
}

function renderFields(fields) {
  $("fieldList").innerHTML = fields.slice(0, 300).map((field) => `<div class="field-item" data-key="${escapeHtml(field.field_key)}"><strong>${escapeHtml(field.field_name_cn)}</strong><small>${escapeHtml(field.field_key)} · ${escapeHtml(field.unit)} · ${field.observations}条</small></div>`).join("");
  document.querySelectorAll(".field-item").forEach((item) => item.addEventListener("click", () => {
    const key = item.dataset.key;
    $("formulaText").value += ($("formulaText").value ? " " : "") + key;
    $("ttmField").value = key;
  }));
}

$("fieldQuery").addEventListener("input", () => {
  const query = $("fieldQuery").value.toLowerCase();
  renderFields(state.fields.filter((field) => `${field.field_name_cn} ${field.field_key}`.toLowerCase().includes(query)));
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

function initializeStaticWorker() {
  if (state.staticWorker) return;
  state.staticWorker = new Worker("./static-search-worker.js");
  state.staticWorker.onmessage = (event) => {
    const pending = state.staticPending.get(event.data.id);
    if (!pending) return;
    state.staticPending.delete(event.data.id);
    if (event.data.ok) pending.resolve(event.data.result);
    else pending.reject(new Error(event.data.error));
  };
  state.staticWorker.onerror = (error) => toast(`静态搜索Worker失败：${error.message}`, true);
}

function staticWorkerRequest(type, payload = {}) {
  initializeStaticWorker();
  const id = ++state.staticRequestId;
  return new Promise((resolve, reject) => {
    state.staticPending.set(id, { resolve, reject });
    state.staticWorker.postMessage({ id, type, ...payload });
  });
}

function buildStaticQuery() {
  return {
    base_query: $("staticQuery").value.trim(),
    base_match_type: $("staticBaseMatchType").value,
    base_columns: [],
    base_threshold: 60,
    search_steps: state.staticSteps,
    filters: [],
    sort: [],
    page: 1,
    page_size: 200,
  };
}

function renderStaticChain() {
  $("staticStepList").innerHTML = state.staticSteps.length ? state.staticSteps.map((step, index) => `<span class="search-step">${escapeHtml(step.operation)} · ${escapeHtml(step.query)} <button type="button" data-static-remove="${index}">×</button></span>`).join("") : '<span class="muted">尚未添加二次搜索</span>';
  $("staticStageCounts").innerHTML = state.staticStageCounts.map((stage) => `<span class="search-stage">${escapeHtml(stage.label)}：${Number(stage.count).toLocaleString()}条</span>`).join("");
}

function initializeStaticGrid() {
  if (state.staticGrid) return;
  state.staticGrid = new ResearchGrid($("staticResults"), {
    columns: SEARCH_COLUMNS,
    pageSize: 200,
    persistKey: "f10-static-search-grid-v2",
    getQuery: buildStaticQuery,
    fetchRows: (query) => staticWorkerRequest("query", { request: query }),
    fetchFacet: (column, term, query) => staticWorkerRequest("facet", { request: query, column, term, limit: 200 }),
    exportRows: async (query) => {
      const result = await staticWorkerRequest("export", { request: query, maxRows: 100000 });
      downloadBlob(`\ufeff${result.csv}`, "static-search-results.csv");
    },
    onResult: (result) => {
      state.staticStageCounts = result.stage_counts || [];
      renderStaticChain();
    },
    onError: (error) => toast(error.message, true),
    onNotice: (message) => toast(message),
  });
}

$("jsonUpload").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    $("staticIndexProgress").textContent = "正在解析JSON并建立浏览器索引…";
    const summary = await staticWorkerRequest("load", { text: await file.text() });
    initializeStaticGrid();
    $("staticSummary").innerHTML = [
      ["请求组", summary.group_count], ["事实记录", summary.fact_count],
      ["证券", summary.security?.secucode || summary.security?.security_code || summary.security?.code || "—"],
    ].map(([label, value]) => `<div class="metric"><div class="label">${label}</div><div class="value">${escapeHtml(value)}</div></div>`).join("");
    $("staticIndexProgress").textContent = "索引已建立，可以使用逐列筛选和二次搜索。";
    state.staticGrid.load(1);
    toast("JSON已在Web Worker中完成索引");
  } catch (error) {
    $("staticIndexProgress").textContent = "索引失败";
    toast(`JSON解析失败：${error.message}`, true);
  }
});

$("staticSearch").addEventListener("click", () => {
  if (!state.staticGrid) return toast("请先上传完整JSON", true);
  state.staticSteps = [];
  renderStaticChain();
  state.staticGrid.load(1);
});

$("addStaticSecondary").addEventListener("click", () => {
  if (!state.staticGrid) return toast("请先上传完整JSON", true);
  const query = $("staticSecondaryQuery").value.trim();
  if (!query) return toast("请输入二次搜索词", true);
  state.staticSteps.push({
    query,
    operation: $("staticSecondaryOperation").value,
    match_type: $("staticSecondaryMatchType").value,
    columns: [],
    threshold: 60,
    enabled: true,
  });
  $("staticSecondaryQuery").value = "";
  renderStaticChain();
  state.staticGrid.load(1);
});

$("clearStaticSecondary").addEventListener("click", () => {
  state.staticSteps = [];
  renderStaticChain();
  if (state.staticGrid) state.staticGrid.load(1);
});

$("staticStepList").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-static-remove]");
  if (!button) return;
  state.staticSteps.splice(Number(button.dataset.staticRemove), 1);
  renderStaticChain();
  state.staticGrid.load(1);
});

// Default initialization.
detectBackend().then(() => {
  if (state.backend) {
    initializeBackendGrid();
    loadPeriodsAndFields($("ttmCode").value.trim());
  }
});
