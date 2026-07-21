(() => {
  let taskId = localStorage.getItem("ashare-f10-cross-validation-task") || null;
  let poller = null;
  const byId = (id) => document.getElementById(id);
  const escape = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");

  async function request(path, options = {}) {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    if (!response.ok) {
      let message = `${response.status} ${response.statusText}`;
      try { message = (await response.json()).detail || message; } catch (_) {}
      throw new Error(message);
    }
    return response.json();
  }

  function renderMetrics(summary) {
    const metrics = [
      ["字段分类覆盖率", `${((summary.classification_coverage || 0) * 100).toFixed(2)}%`],
      ["东方财富事实", summary.eastmoney_fact_count || 0],
      ["官方事实", summary.official_fact_count || 0],
      ["可比记录", summary.comparable_count || 0],
      ["已匹配", summary.matched_count || 0],
      ["真正冲突", summary.true_conflict_count || 0],
      ["验收状态", summary.acceptance_status || "—"],
    ];
    byId("validationMetrics").innerHTML = metrics
      .map(([label, value]) => `<div class="metric"><div class="label">${escape(label)}</div><div class="value">${escape(value)}</div></div>`)
      .join("");
  }

  function renderDownloads(task) {
    if (task.status !== "COMPLETED") return;
    const items = [
      ["comparison_xlsx", "双源比较Excel"], ["comparison_db", "比较DuckDB"],
      ["comparison_json", "比较JSON"], ["comparison_parquet", "比较Parquet"],
      ["official_xlsx", "官方数据Excel"], ["eastmoney_xlsx", "东方财富Excel"],
      ["evidence", "完整证据包"],
    ];
    byId("validationDownloads").innerHTML = items
      .map(([kind, label]) => `<a class="download-card" href="/api/cross-validation/jobs/${task.task_id}/download/${kind}" target="_blank"><strong>${escape(label)}</strong></a>`)
      .join("");
  }

  async function poll() {
    if (!taskId) return;
    try {
      const task = await request(`/api/cross-validation/jobs/${taskId}`);
      byId("validationProgress").textContent = JSON.stringify(task, null, 2);
      if (task.summary) renderMetrics(task.summary);
      renderDownloads(task);
      if (["PENDING", "RUNNING"].includes(task.status)) {
        clearTimeout(poller);
        poller = setTimeout(poll, 2500);
      }
    } catch (error) {
      byId("validationProgress").textContent = error.message;
    }
  }

  async function startFullCrossValidation(code, options = {}) {
    if (!/^\d{6}$/.test(code)) throw new Error("请输入6位股票代码");
    if (byId("validationCode")) byId("validationCode").value = code;
    const task = await request("/api/cross-validation/jobs", {
      method: "POST",
      body: JSON.stringify({
        stock_code: code,
        max_periods: options.max_periods ?? null,
      }),
    });
    taskId = task.task_id;
    localStorage.setItem("ashare-f10-cross-validation-task", taskId);
    clearTimeout(poller);
    poll();
    return task;
  }

  window.startFullCrossValidation = startFullCrossValidation;

  byId("startValidation")?.addEventListener("click", async () => {
    try {
      await startFullCrossValidation(byId("validationCode").value.trim());
    } catch (error) { alert(error.message); }
  });
  byId("refreshValidation")?.addEventListener("click", poll);
  byId("loadValidationRows")?.addEventListener("click", async () => {
    if (!taskId) return alert("请先创建交叉验证任务");
    const params = new URLSearchParams();
    for (const [id, key] of [
      ["validationQuery", "q"], ["validationStatus", "status"], ["validationMode", "validation_mode"],
      ["validationStartDate", "start_date"], ["validationEndDate", "end_date"],
    ]) {
      const value = byId(id).value.trim();
      if (value) params.set(key, value);
    }
    const data = await request(`/api/cross-validation/jobs/${taskId}/comparison?${params}`);
    const columns = [
      "report_date", "field_name_cn", "field_key", "eastmoney_value_num",
      "official_value_num", "difference", "status", "validation_mode",
    ];
    byId("validationRows").innerHTML = `<div class="muted">共${data.total}条</div><table><thead><tr>${columns.map((item) => `<th>${escape(item)}</th>`).join("")}</tr></thead><tbody>${data.items.map((row) => `<tr>${columns.map((item) => `<td>${escape(row[item])}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
  });

  if (taskId) poll();
})();
