const state = {
  code: "688521",
  offset: 0,
  limit: 100,
  total: 0,
  selectedObservationId: null,
  pollTimer: null,
};

const $ = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function toast(message, error = false) {
  const node = $("toast");
  node.textContent = message;
  node.className = `toast show${error ? " error" : ""}`;
  window.setTimeout(() => { node.className = "toast"; }, 3200);
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch (_) {
      // Keep the HTTP status when the body is not JSON.
    }
    throw new Error(detail);
  }
  return response.json();
}

function ratio(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function scalar(value) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") return value.toLocaleString("zh-CN");
  return String(value);
}

function statusClass(status) {
  const text = String(status || "");
  if (text.includes("CONFLICT") || text.startsWith("FAIL")) return "failure";
  if (text.includes("UNRESOLVED") || text.includes("GAP") || text.includes("PARTIAL")) return "warning";
  return "";
}

function renderQualityCards(dimensions = {}) {
  const cards = [
    ["分类覆盖", ratio(dimensions.classification_coverage), "字段是否全部进入明确验证模式"],
    ["比较覆盖", ratio(dimensions.comparison_coverage), "理论可比事实中已形成双源比较的比例"],
    ["比较准确率", ratio(dimensions.comparison_accuracy), "已比较事实中的一致比例"],
    ["证据完整度", ratio(dimensions.evidence_completeness), "已比较事实是否有文档与位置证据"],
    ["映射覆盖", ratio(dimensions.mapping_coverage), "源事实映射到研究本体的比例"],
    ["可疑解析率", ratio(dimensions.suspicious_extraction_rate), "解析质量闸门命中的比例"],
    ["未解决率", ratio(dimensions.unresolved_rate), "仍需扩展来源或解析的比例"],
    ["真实冲突", scalar(dimensions.true_conflict_count), dimensions.acceptance_status || "—"],
  ];
  $("qualityCards").innerHTML = cards.map(([label, value, note]) => `
    <div class="metric ${statusClass(note)}">
      <div class="label">${escapeHtml(label)}</div>
      <div class="value">${escapeHtml(value)}</div>
      <div class="muted small-text">${escapeHtml(note)}</div>
    </div>
  `).join("");
}

function renderDownloads(code) {
  const items = [
    ["JSON", "json", "完整结构化包"],
    ["Excel", "excel", "可筛选工作簿"],
    ["DuckDB", "duckdb", "研究查询数据库"],
    ["Summary", "summary", "质量和表规模"],
    ["Quality", "quality", "结构完整性校验"],
    ["Manifest", "manifest", "输入指纹和表清单"],
    ["Checkpoint", "checkpoint", "恢复状态"],
  ];
  $("downloadCards").innerHTML = items.map(([label, kind, note]) => `
    <div class="download-card">
      <strong>${escapeHtml(label)}</strong>
      <div class="muted">${escapeHtml(note)}</div>
      <a href="/api/research-pack/stocks/${encodeURIComponent(code)}/download/${kind}">下载</a>
    </div>
  `).join("");
}

async function loadLatest() {
  const code = $("stockCode").value.trim();
  if (!/^\d{6}$/.test(code)) {
    toast("请输入六位股票代码", true);
    return;
  }
  try {
    const payload = await api(`/api/research-pack/stocks/${encodeURIComponent(code)}/latest`);
    state.code = code;
    state.offset = 0;
    $("serviceBadge").textContent = "Research Pack 已就绪";
    const pointer = payload.pointer || {};
    const summary = payload.summary || {};
    $("metaCode").textContent = pointer.stock_code || summary.security_code || code;
    $("metaMode").textContent = pointer.mode || "—";
    $("metaAsOf").textContent = pointer.as_of_date || summary.as_of_date || "—";
    $("metaSchema").textContent = summary.schema_version || "—";
    $("metaGenerated").textContent = summary.generated_at_utc || pointer.completed_at_utc || "—";
    $("metaQuality").textContent = payload.quality?.status || "—";
    renderQualityCards(payload.quality_dimensions || {});
    renderDownloads(code);
    await Promise.all([loadFacts(), loadVersions()]);
  } catch (error) {
    $("serviceBadge").textContent = "尚无Research Pack";
    toast(error.message, true);
  }
}

function jobProgress(stage) {
  const order = ["PENDING", "RESOLVE_INPUT", "CROSS_VALIDATION", "RESEARCH_PACK", "COMPLETED"];
  const index = Math.max(0, order.indexOf(stage));
  return Math.round((index / (order.length - 1)) * 100);
}

function renderJob(job) {
  $("jobPanel").hidden = false;
  $("jobStatus").textContent = job.status || "UNKNOWN";
  $("jobStatus").className = `status ${job.status || "PENDING"}`;
  $("jobMessage").textContent = `${job.stage || ""} · ${job.message || ""}`;
  $("jobProgress").style.width = `${jobProgress(job.stage)}%`;
  $("jobDetails").textContent = JSON.stringify({
    job_id: job.job_id,
    mode: job.mode,
    as_of_date: job.as_of_date,
    manual_review_required: job.manual_review_required,
    error: job.error,
  }, null, 2);
}

async function pollJob(jobId) {
  window.clearTimeout(state.pollTimer);
  try {
    const job = await api(`/api/research-pack/jobs/${encodeURIComponent(jobId)}`);
    renderJob(job);
    if (job.status === "COMPLETED") {
      toast("Research Pack生成完成");
      await loadLatest();
      return;
    }
    if (job.status === "FAILED") {
      toast(job.error || job.message || "Research Pack任务失败", true);
      return;
    }
    state.pollTimer = window.setTimeout(() => pollJob(jobId), 1800);
  } catch (error) {
    toast(error.message, true);
  }
}

async function startJob() {
  const code = $("stockCode").value.trim();
  if (!/^\d{6}$/.test(code)) {
    toast("请输入六位股票代码", true);
    return;
  }
  const body = {
    stock_code: code,
    mode: $("modeSelect").value,
    as_of_date: $("asOfDate").value || null,
    force: false,
  };
  try {
    const job = await api("/api/research-pack/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    renderJob(job);
    pollJob(job.job_id);
  } catch (error) {
    toast(error.message, true);
  }
}

function issuePill(status) {
  const text = String(status || "");
  if (text === "SOURCE_CONFLICT") return '<span class="issue-pill conflict">来源冲突</span>';
  if (text === "UNRESOLVED") return '<span class="issue-pill unresolved">未解决</span>';
  if (text.includes("VERIFIED")) return '<span class="issue-pill verified">已验证</span>';
  return `<span class="issue-pill">${escapeHtml(text || "—")}</span>`;
}

function renderFacts(rows) {
  if (!rows.length) {
    $("factTable").innerHTML = '<div class="empty" style="padding:18px">没有符合条件的规范事实</div>';
    return;
  }
  $("factTable").innerHTML = `
    <table>
      <thead><tr>
        <th>指标</th><th>模块</th><th>期间</th><th>数值</th><th>状态</th><th>来源</th><th>冲突</th>
      </tr></thead>
      <tbody>${rows.map((row) => `
        <tr class="fact-row${row.observation_id === state.selectedObservationId ? " selected" : ""}"
            data-observation-id="${escapeHtml(row.observation_id)}">
          <td><strong>${escapeHtml(row.metric_name_cn || row.metric_id)}</strong><br><span class="muted">${escapeHtml(row.metric_id)}</span></td>
          <td>${escapeHtml(row.research_module)}</td>
          <td>${escapeHtml(row.report_date || row.event_date || "—")}<br><span class="muted">${escapeHtml(row.period_type)}</span></td>
          <td>${escapeHtml(row.value_num ?? row.value_text ?? "—")} ${escapeHtml(row.unit || "")}</td>
          <td>${issuePill(row.status)}</td>
          <td>${escapeHtml(row.usable_source_count ?? 0)} / ${escapeHtml(row.source_count ?? 0)}</td>
          <td>${escapeHtml(row.conflict_count ?? 0)}</td>
        </tr>
      `).join("")}</tbody>
    </table>
  `;
  document.querySelectorAll(".fact-row").forEach((row) => {
    row.addEventListener("click", () => loadEvidence(row.dataset.observationId));
  });
}

async function loadFacts() {
  const params = new URLSearchParams({
    q: $("factQuery").value.trim(),
    research_module: $("moduleFilter").value,
    status: $("statusFilter").value,
    issue: $("issueFilter").value,
    offset: String(state.offset),
    limit: String(state.limit),
  });
  [...params.entries()].forEach(([key, value]) => { if (!value) params.delete(key); });
  try {
    const payload = await api(`/api/research-pack/stocks/${encodeURIComponent(state.code)}/facts?${params}`);
    state.total = payload.total;
    renderFacts(payload.rows || []);
    const moduleSelect = $("moduleFilter");
    const currentModule = moduleSelect.value;
    moduleSelect.innerHTML = '<option value="">全部模块</option>' + (payload.modules || []).map((item) =>
      `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`
    ).join("");
    moduleSelect.value = currentModule;
    const start = state.total ? state.offset + 1 : 0;
    const end = Math.min(state.offset + state.limit, state.total);
    $("factCount").textContent = `共 ${state.total.toLocaleString("zh-CN")} 条，当前 ${start}-${end}`;
    $("pageInfo").textContent = `${Math.floor(state.offset / state.limit) + 1} / ${Math.max(1, Math.ceil(state.total / state.limit))}`;
    $("prevPage").disabled = state.offset === 0;
    $("nextPage").disabled = state.offset + state.limit >= state.total;
  } catch (error) {
    toast(error.message, true);
  }
}

function renderKeyValue(payload) {
  return `<dl class="evidence-grid">${Object.entries(payload || {}).map(([key, value]) => `
    <dt>${escapeHtml(key)}</dt><dd>${escapeHtml(typeof value === "object" ? JSON.stringify(value) : value)}</dd>
  `).join("")}</dl>`;
}

async function loadEvidence(observationId) {
  state.selectedObservationId = observationId;
  try {
    const payload = await api(
      `/api/research-pack/stocks/${encodeURIComponent(state.code)}/facts/${encodeURIComponent(observationId)}/evidence`
    );
    $("evidenceBadge").textContent = payload.observation.metric_name_cn || payload.observation.metric_id;
    const documents = (payload.nodes || []).filter((item) => item.node_type === "DOCUMENT");
    const locations = (payload.nodes || []).filter((item) => item.node_type === "EVIDENCE_LOCATION");
    $("evidenceDetail").className = "evidence-detail";
    $("evidenceDetail").innerHTML = `
      <div class="evidence-card"><h4>规范事实</h4>${renderKeyValue(payload.observation)}</div>
      <div class="evidence-card"><h4>来源血缘（${payload.lineage.length}）</h4>
        ${payload.lineage.map((item) => renderKeyValue(item)).join("<hr>") || '<div class="empty">无血缘</div>'}
      </div>
      <div class="evidence-card"><h4>原始文档（${documents.length}）</h4>
        ${documents.map((item) => renderKeyValue(item.attributes || item)).join("<hr>") || '<div class="empty">无独立文档节点</div>'}
      </div>
      <div class="evidence-card"><h4>证据位置（${locations.length}）</h4>
        ${locations.map((item) => renderKeyValue(item.attributes || item)).join("<hr>") || '<div class="empty">无页码或原始行</div>'}
      </div>
    `;
    await loadFacts();
  } catch (error) {
    toast(error.message, true);
  }
}

async function loadVersions() {
  try {
    const payload = await api(`/api/research-pack/stocks/${encodeURIComponent(state.code)}/versions`);
    const supersedes = new Map((payload.supersedes_edges || []).map((edge) => [edge.from_node_id, edge.to_node_id]));
    const documents = payload.documents || [];
    if (!documents.length) {
      $("versionList").className = "version-list empty";
      $("versionList").textContent = "当前包没有独立文档节点";
      return;
    }
    $("versionList").className = "version-list";
    $("versionList").innerHTML = documents.map((item) => {
      const attrs = item.attributes || {};
      const prior = supersedes.get(item.node_id);
      return `<div class="version-card">
        <h4>${escapeHtml(attrs.document_title || item.label || item.node_id)}</h4>
        <div class="muted">报告期 ${escapeHtml(attrs.report_date || "—")} · 可用日 ${escapeHtml(attrs.available_at || "—")}</div>
        <div>版本：${escapeHtml(attrs.version_label || "原版/未标注")} · 状态：${escapeHtml(attrs.status || attrs.access_status || "—")}</div>
        ${prior ? `<div class="version-chain">SUPERSEDES → ${escapeHtml(prior)}</div>` : ""}
        ${attrs.source_url ? `<div><a href="${escapeHtml(attrs.source_url)}" target="_blank" rel="noreferrer">打开来源</a></div>` : ""}
      </div>`;
    }).join("");
  } catch (error) {
    $("versionList").className = "version-list empty";
    $("versionList").textContent = error.message;
  }
}

$("startJob").addEventListener("click", startJob);
$("loadLatest").addEventListener("click", loadLatest);
$("searchFacts").addEventListener("click", () => { state.offset = 0; loadFacts(); });
$("refreshVersions").addEventListener("click", loadVersions);
$("prevPage").addEventListener("click", () => {
  state.offset = Math.max(0, state.offset - state.limit);
  loadFacts();
});
$("nextPage").addEventListener("click", () => {
  if (state.offset + state.limit < state.total) state.offset += state.limit;
  loadFacts();
});
$("factQuery").addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    state.offset = 0;
    loadFacts();
  }
});

api("/api/research-pack/capabilities")
  .then(() => { $("serviceBadge").textContent = "API正常"; })
  .catch((error) => {
    $("serviceBadge").textContent = "API不可用";
    toast(error.message, true);
  });
