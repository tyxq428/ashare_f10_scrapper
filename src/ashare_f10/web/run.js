const byId = (id) => document.getElementById(id);
const activeStatuses = new Set(["PENDING", "RUNNING", "RETRYING", "DELETING"]);
const stageLabels = { f10: "F10结构化数据", raw_pack: "Raw Pack官方资料", official_validation: "官方交叉验证" };
const statusLabels = {
  PENDING: "等待执行", RUNNING: "运行中", RETRYING: "自动恢复中", PARTIAL: "部分完成",
  COMPLETED: "已完成", COMPLETED_WITH_REVIEW: "完成，需复核", FAILED: "失败", CANCELLED: "已取消",
  NOT_REQUESTED: "未选择", SKIPPED_INCOMPLETE_F10: "F10未完整，已跳过", UNKNOWN: "状态待识别",
};
const artifactLabels = {
  json: "完整JSON", excel: "F10 Excel", parquet: "F10 Parquet", duckdb: "F10 DuckDB",
  raw_pack_excel: "Raw Pack Excel", raw_pack_parquet: "Raw Pack Parquet", raw_pack_duckdb: "Raw Pack DuckDB",
  raw_pack_quality: "Raw Pack质量报告", raw_pack_manifest: "Raw Pack运行清单",
  official_eastmoney_json: "F10验证输入JSON", official_eastmoney_excel: "F10验证输入Excel",
  official_eastmoney_parquet: "F10验证输入Parquet", official_eastmoney_duckdb: "F10验证输入DuckDB",
  official_official_json: "官方事实JSON", official_official_excel: "官方事实Excel",
  official_official_parquet: "官方事实Parquet", official_official_duckdb: "官方事实DuckDB",
  official_comparison_json: "全历史对账JSON", official_comparison_excel: "全历史对账Excel",
  official_comparison_parquet: "全历史对账Parquet", official_comparison_duckdb: "全历史对账DuckDB",
  official_summary_json: "官方验证摘要", official_evidence_zip: "官方证据包",
  official_validation_mismatches_excel: "官方验证Excel", official_validation_evidence_json: "官方验证证据",
  official_validation_detail_parquet: "官方验证明细", official_official_facts_parquet: "官方事实Parquet",
  official_source_hashes_json: "官方文件哈希",
};
const state = { presets: [], selectedPreset: "full_research", poller: null, capabilities: null, jobs: [] };

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
}

function toast(message, error = false) {
  const node = byId("toast");
  node.textContent = message;
  node.className = `show${error ? " error" : ""}`;
  setTimeout(() => { node.className = ""; }, 4200);
}

async function api(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try { detail = (await response.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  const type = response.headers.get("content-type") || "";
  return type.includes("application/json") ? response.json() : response;
}

function selectedPreset() {
  return state.presets.find((item) => item.id === state.selectedPreset) || state.presets[0] || {};
}

function officialScopeRecord() {
  const value = byId("officialScope")?.value || "full_history";
  return (state.capabilities?.official_validation_scopes || []).find((item) => item.value === value) || {};
}

function renderOfficialScopeHelp() {
  const record = officialScopeRecord();
  byId("officialScopeHelp").textContent = record.description || "系统自动识别上市日期和可用报告期。";
}

function renderPresets() {
  byId("presets").innerHTML = state.presets.map((preset) => `
    <label class="preset ${preset.id === state.selectedPreset ? "active" : ""}">
      <input type="radio" name="preset" value="${escapeHtml(preset.id)}" ${preset.id === state.selectedPreset ? "checked" : ""} />
      <strong>${escapeHtml(preset.label)}</strong>
      <small>${escapeHtml(preset.description)}</small>
    </label>`).join("");
  const preset = selectedPreset();
  byId("rawOptions").style.display = preset.include_raw_pack ? "block" : "none";
  byId("officialOptions").style.display = preset.run_official_validation ? "block" : "none";
  byId("rawMaxField").style.display = preset.include_raw_pack ? "flex" : "none";
  renderOfficialScopeHelp();
}

function readPreferences() {
  try { return JSON.parse(localStorage.getItem("ashare-f10-visual-execution") || "{}"); }
  catch (_) { return {}; }
}

function applyPreferences() {
  const prefs = readPreferences();
  state.selectedPreset = prefs.preset || "full_research";
  for (const [id, key] of [
    ["stockCode", "stock_code"], ["workers", "workers"], ["pollSeconds", "poll_seconds"],
    ["maxRetries", "max_auto_retries"], ["backoff", "retry_backoff_seconds"],
    ["rawPacks", "raw_pack_packs"], ["rawMax", "raw_pack_max_docs"],
    ["officialScope", "official_validation_scope"],
  ]) {
    if (prefs[key] !== undefined && byId(id)) byId(id).value = prefs[key];
  }
  for (const [id, key] of [["resume", "resume"], ["autoRetry", "auto_retry_failed"]]) {
    if (prefs[key] !== undefined && byId(id)) byId(id).checked = Boolean(prefs[key]);
  }
}

function currentConfiguration() {
  const preset = selectedPreset();
  return {
    stock_code: byId("stockCode").value.trim(),
    resume: byId("resume").checked,
    workers: Number(byId("workers").value),
    auto_retry_failed: byId("autoRetry").checked,
    max_auto_retries: Number(byId("maxRetries").value),
    retry_backoff_seconds: Number(byId("backoff").value),
    include_raw_pack: Boolean(preset.include_raw_pack),
    raw_pack_packs: byId("rawPacks").value,
    raw_pack_max_docs: Number(byId("rawMax").value),
    run_official_validation: Boolean(preset.run_official_validation),
    official_validation_scope: byId("officialScope").value,
  };
}

function savePreferences(showToast = true) {
  const config = currentConfiguration();
  localStorage.setItem("ashare-f10-visual-execution", JSON.stringify({ ...config, preset: state.selectedPreset, poll_seconds: Number(byId("pollSeconds").value) }));
  if (showToast) toast("已保存本机默认设置");
}

function validateConfiguration(config) {
  if (!/^\d{6}$/.test(config.stock_code)) throw new Error("请输入6位股票代码");
  if (!Number.isInteger(config.workers) || config.workers < 1 || config.workers > 32) throw new Error("并发数必须是1到32的整数");
  if (!Number.isInteger(config.max_auto_retries) || config.max_auto_retries < 0 || config.max_auto_retries > 5) throw new Error("自动重试轮数必须是0到5的整数");
  if (!Number.isInteger(config.raw_pack_max_docs) || config.raw_pack_max_docs < 1 || config.raw_pack_max_docs > 5000) throw new Error("Raw Pack文档安全上限必须是1到5000的整数");
  const scopes = new Set((state.capabilities?.official_validation_scopes || []).map((item) => item.value));
  if (config.run_official_validation && !scopes.has(config.official_validation_scope)) throw new Error("请选择有效的官方验证范围");
}

function duration(value) {
  if (value === null || value === undefined) return "—";
  const seconds = Number(value);
  if (seconds < 60) return `${seconds.toFixed(1)}秒`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}分${Math.round(seconds % 60)}秒`;
  return `${Math.floor(seconds / 3600)}时${Math.floor((seconds % 3600) / 60)}分`;
}

function heartbeatAge(value) {
  if (!value) return null;
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return null;
  return Math.max(0, Math.round((Date.now() - timestamp) / 1000));
}

function visibleStageStatus(stage, visual) {
  const stored = visual.stage_status?.[stage] || "UNKNOWN";
  const result = visual.stage_results?.[stage] || {};
  if (stage === "official_validation" && stored === "COMPLETED" && (result.display_status === "COMPLETED_WITH_REVIEW" || result.manual_review_required)) return "COMPLETED_WITH_REVIEW";
  return stored;
}

function renderMetrics() {
  const counts = {};
  state.jobs.forEach((job) => { counts[job.status] = (counts[job.status] || 0) + 1; });
  const warningCount = state.jobs.reduce((sum, job) => sum + Number(job.visual?.warning_count || 0), 0);
  byId("metrics").innerHTML = [
    ["任务总数", state.jobs.length], ["运行中", state.jobs.filter((job) => activeStatuses.has(job.status)).length],
    ["完整完成", counts.COMPLETED || 0], ["部分/失败", (counts.PARTIAL || 0) + (counts.FAILED || 0)], ["需复核/警告", warningCount],
  ].map(([label, value]) => `<div class="metric"><span>${escapeHtml(label)}</span><b>${escapeHtml(value)}</b></div>`).join("");
}

function artifactLinks(job) {
  const entries = Object.entries(job.artifacts || {}).filter(([kind, value]) => artifactLabels[kind] && typeof value === "string" && value.trim());
  return entries.map(([kind]) => `<a target="_blank" href="/api/visual-execution/jobs/${encodeURIComponent(job.job_id)}/download/${encodeURIComponent(kind)}">${escapeHtml(artifactLabels[kind])}</a>`).join("");
}

function stageResultText(stage, result) {
  if (!result || !Object.keys(result).length) return "";
  if (stage === "raw_pack") return `资料 ${result.document_count ?? 0} 条`;
  if (stage === "official_validation") {
    const bits = [result.scope_label, result.document_count !== undefined ? `报告 ${result.document_count} 份` : "", result.official_fact_count !== undefined ? `官方事实 ${result.official_fact_count} 条` : "", result.true_conflict_count ? `来源差异 ${result.true_conflict_count} 项` : ""];
    return bits.filter(Boolean).join("；");
  }
  return "";
}

function stageCard(job, stage) {
  const visual = job.visual || {};
  const status = visibleStageStatus(stage, visual);
  const message = visual.stage_messages?.[stage] || "";
  const summary = stageResultText(stage, visual.stage_results?.[stage] || {});
  return `<div class="stage"><strong>${escapeHtml(stageLabels[stage])}</strong><span class="tag stage-${escapeHtml(status)}">${escapeHtml(statusLabels[status] || status)}</span><div class="muted">${escapeHtml(message)}</div>${summary ? `<div class="stage-result">${escapeHtml(summary)}</div>` : ""}</div>`;
}

function renderJob(job) {
  const pct = job.total_groups ? Math.min(100, Math.round(Number(job.completed_groups || 0) / Number(job.total_groups) * 100)) : 0;
  const heartbeat = job.visual?.heartbeat_at_utc || job.updated_at_utc;
  const age = heartbeatAge(heartbeat);
  const stale = activeStatuses.has(job.status) && age !== null && age > 90;
  const options = job.visual?.options || {};
  const officialScope = options.official_validation_scope ? (state.capabilities?.official_validation_scopes || []).find((item) => item.value === options.official_validation_scope)?.label || options.official_validation_scope : "—";
  return `<article class="job">
    <div class="job-head"><div><strong>${escapeHtml(job.stock_name || job.stock_code)}（${escapeHtml(job.stock_code)}）</strong><div class="job-id">${escapeHtml(job.job_id)}</div></div><span class="tag ${escapeHtml(job.status)}">${escapeHtml(statusLabels[job.status] || job.status)}</span></div>
    <div class="progress"><div style="width:${pct}%"></div></div>
    <div class="job-meta"><span>F10 ${job.completed_groups}/${job.total_groups}</span><span>失败 ${job.failed_groups}</span><span>自动重试 ${job.retry_count || 0}</span><span>耗时 ${escapeHtml(duration(job.duration_seconds))}</span><span class="${stale ? "stale" : ""}">心跳 ${age === null ? "—" : `${age}秒前`}${stale ? "（可能停滞）" : ""}</span></div>
    <div class="stage-grid">${["f10", "raw_pack", "official_validation"].map((stage) => stageCard(job, stage)).join("")}</div>
    <div class="muted">${escapeHtml(job.message || "")}</div>
    <div class="muted">配置：并发 ${escapeHtml(options.workers || "—")}；Raw Pack ${options.include_raw_pack ? "已选择" : "未选择"}；官方验证 ${options.run_official_validation ? escapeHtml(officialScope) : "未选择"}</div>
    <div class="job-actions">
      ${job.failed_groups > 0 && !activeStatuses.has(job.status) ? `<button class="primary" data-action="retry" data-id="${escapeHtml(job.job_id)}">仅重试失败项</button>` : ""}
      ${!activeStatuses.has(job.status) ? `<button class="secondary" data-action="rerun" data-id="${escapeHtml(job.job_id)}">按原配置重新执行</button>` : ""}
      ${activeStatuses.has(job.status) ? `<button class="danger" data-action="cancel" data-id="${escapeHtml(job.job_id)}">取消</button>` : ""}
      ${artifactLinks(job)}
    </div>
  </article>`;
}

function renderJobs() {
  renderMetrics();
  byId("jobs").innerHTML = state.jobs.length ? state.jobs.map(renderJob).join("") : '<div class="empty">暂无任务</div>';
}

async function refreshJobs() {
  try {
    const result = await api("/api/visual-execution/jobs?limit=100");
    state.jobs = result.items || [];
    renderJobs();
  } catch (error) {
    toast(`任务状态加载失败：${error.message}`, true);
  } finally {
    clearTimeout(state.poller);
    const active = state.jobs.some((job) => activeStatuses.has(job.status));
    const seconds = active ? Number(byId("pollSeconds").value || 1.5) : 10;
    state.poller = setTimeout(refreshJobs, Math.max(1000, seconds * 1000));
  }
}

async function startJob() {
  const button = byId("start");
  try {
    button.disabled = true;
    button.textContent = "正在创建任务…";
    const config = currentConfiguration();
    validateConfiguration(config);
    savePreferences(false);
    const job = await api("/api/visual-execution/jobs", { method: "POST", body: JSON.stringify(config) });
    toast(`任务已创建：${job.job_id}`);
    await refreshJobs();
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "开始研究";
  }
}

async function executeAction(action, jobId) {
  try {
    await api(`/api/visual-execution/jobs/${encodeURIComponent(jobId)}/${action === "retry" ? "retry-failed" : action}`, { method: "POST" });
    toast(action === "retry" ? "已开始重试失败项" : action === "rerun" ? "已按原配置创建新任务" : "已发送取消请求");
    await refreshJobs();
  } catch (error) { toast(error.message, true); }
}

async function initialize() {
  try {
    state.capabilities = await api("/api/visual-execution/capabilities");
    state.presets = state.capabilities.presets || [];
    byId("officialScope").innerHTML = (state.capabilities.official_validation_scopes || []).map((item) => `<option value="${escapeHtml(item.value)}">${escapeHtml(item.label)}</option>`).join("");
    applyPreferences();
    if (!byId("officialScope").value) byId("officialScope").value = state.capabilities.defaults?.official_validation_scope || "full_history";
    renderPresets();
    byId("backend").textContent = "服务可用";
    byId("backend").classList.add("COMPLETED");
    await refreshJobs();
  } catch (error) {
    byId("backend").textContent = "服务不可用";
    byId("backend").classList.add("FAILED");
    toast(`请先启动本地服务：${error.message}`, true);
  }
}

byId("presets").addEventListener("change", (event) => {
  if (!event.target.matches('input[name="preset"]')) return;
  state.selectedPreset = event.target.value;
  renderPresets();
});
byId("officialScope").addEventListener("change", renderOfficialScopeHelp);
byId("start").addEventListener("click", startJob);
byId("savePreset").addEventListener("click", () => savePreferences(true));
byId("refresh").addEventListener("click", refreshJobs);
byId("pollSeconds").addEventListener("change", refreshJobs);
byId("jobs").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action]");
  if (button) executeAction(button.dataset.action, button.dataset.id);
});

initialize();
