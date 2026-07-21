(() => {
  const center = {
    jobs: [],
    expanded: new Set(),
    groups: new Map(),
    poller: null,
    filterTimer: null,
  };
  const activeStatuses = new Set(["PENDING", "RUNNING", "RETRYING", "DELETING"]);
  const statusLabels = {
    PENDING: "等待执行",
    RUNNING: "运行中",
    RETRYING: "重试中",
    PARTIAL: "部分成功",
    COMPLETED: "完整完成",
    FAILED: "执行失败",
    CANCELLED: "已取消",
    DELETING: "删除中",
    DELETE_FAILED: "删除失败",
  };
  const groupStatusLabels = {
    PENDING: "等待",
    RUNNING: "运行中",
    RETRYING: "重试中",
    SUCCESS: "成功",
    FAILED: "失败",
    CANCELLED: "取消",
  };

  const node = (id) => document.getElementById(id);
  const escape = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;");

  function notify(message, error = false) {
    const target = node("toast");
    if (!target) return;
    target.textContent = message;
    target.className = `toast show${error ? " error" : ""}`;
    setTimeout(() => { target.className = "toast"; }, 3800);
  }

  async function jobApi(path, options = {}) {
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

  function formatTime(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
  }

  function formatDuration(value) {
    if (value === null || value === undefined) return "—";
    const seconds = Number(value);
    if (seconds < 60) return `${seconds.toFixed(1)}秒`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}分${Math.round(seconds % 60)}秒`;
    return `${Math.floor(seconds / 3600)}时${Math.floor((seconds % 3600) / 60)}分`;
  }

  function artifactLinks(job) {
    const keys = ["json", "excel", "parquet", "duckdb"];
    const labels = { json: "JSON", excel: "EXCEL", parquet: "PARQUET", duckdb: "DUCKDB" };
    const links = keys.filter((key) => job.artifacts?.[key]).map((key) => (
      `<a href="/api/jobs/${encodeURIComponent(job.job_id)}/download/${key}" target="_blank">${labels[key]}</a>`
    ));
    return links.length ? `<div class="job-files">${links.join(" · ")}</div>` : "";
  }

  function jobActions(job) {
    const active = activeStatuses.has(job.status);
    const expanded = center.expanded.has(job.job_id);
    const actions = [
      `<button type="button" data-job-action="expand" data-job-id="${escape(job.job_id)}">${expanded ? "收起子任务" : `展开子任务（${job.total_groups}）`}</button>`,
    ];
    if (job.failed_groups > 0 && !active) {
      actions.push(`<button type="button" class="primary" data-job-action="retry-failed" data-job-id="${escape(job.job_id)}">重试失败项（${job.failed_groups}）</button>`);
    }
    if (!active) {
      actions.push(`<button type="button" data-job-action="rerun" data-job-id="${escape(job.job_id)}">重新执行全部</button>`);
    }
    if (job.status === "COMPLETED" && job.failed_groups === 0 && !job.is_current) {
      actions.push(`<button type="button" data-job-action="set-current" data-job-id="${escape(job.job_id)}">设为当前版本</button>`);
    }
    if (["PENDING", "RUNNING"].includes(job.status)) {
      actions.push(`<button type="button" data-job-action="cancel" data-job-id="${escape(job.job_id)}">取消任务</button>`);
    }
    if (!active) {
      actions.push(`<button type="button" class="danger" data-job-action="delete" data-job-id="${escape(job.job_id)}">删除任务及文件</button>`);
    }
    return actions.join("");
  }

  function renderJobCard(job) {
    const pct = job.total_groups ? Math.min(100, Math.round(job.completed_groups / job.total_groups * 100)) : 0;
    const displayName = job.stock_name || "名称获取中";
    const currentBadge = job.is_current ? '<span class="current-badge">CURRENT</span>' : "";
    const expanded = center.expanded.has(job.job_id);
    const errorSummary = job.errors?.length ? `<details class="job-error"><summary>任务错误（${job.errors.length}）</summary><pre>${escape(job.errors.join("\n"))}</pre></details>` : "";
    return `
      <article class="job-card ${job.is_current ? "is-current" : ""}" data-job-card="${escape(job.job_id)}">
        <div class="job-title">
          <div>
            <strong class="job-security">${escape(displayName)}（${escape(job.stock_code)}）</strong>
            ${currentBadge}
            <div class="job-id">任务ID：${escape(job.job_id)}</div>
          </div>
          <span class="status ${escape(job.status)}">${escape(statusLabels[job.status] || job.status)}</span>
        </div>
        <div class="progress"><div style="width:${pct}%"></div></div>
        <div class="job-summary-grid">
          <span>完成 ${job.completed_groups}/${job.total_groups}</span>
          <span>成功 ${job.successful_groups}</span>
          <span class="${job.failed_groups ? "failure-text" : ""}">失败 ${job.failed_groups}</span>
          <span>重试 ${job.retry_count || 0}</span>
          <span>创建 ${escape(formatTime(job.created_at_utc))}</span>
          <span>耗时 ${escape(formatDuration(job.duration_seconds))}</span>
        </div>
        <div class="muted job-message">${escape(job.message)}${job.current_group ? ` · ${escape(job.current_group)}` : ""}</div>
        ${artifactLinks(job)}
        ${errorSummary}
        <div class="job-actions">${jobActions(job)}</div>
        <div id="job-groups-${escape(job.job_id)}" class="job-groups ${expanded ? "active" : ""}">${expanded ? '<div class="empty">正在加载子任务…</div>' : ""}</div>
      </article>`;
  }

  function renderJobs() {
    const container = node("managedJobList");
    if (!container) return;
    node("jobListMeta").textContent = `共 ${center.jobs.length.toLocaleString()} 个当前页任务`;
    if (!center.jobs.length) {
      container.className = "job-list empty";
      container.textContent = "暂无符合条件的任务";
      return;
    }
    container.className = "job-list";
    container.innerHTML = center.jobs.map(renderJobCard).join("");
    for (const job of center.jobs) {
      if (center.expanded.has(job.job_id)) loadGroups(job.job_id, activeStatuses.has(job.status));
    }
  }

  function jobQueryParams() {
    const [sortBy, sortDirection] = (node("jobSort")?.value || "created_at_utc:desc").split(":");
    const params = new URLSearchParams({
      paged: "true",
      q: node("jobFilter")?.value.trim() || "",
      sort_by: sortBy,
      sort_direction: sortDirection,
      offset: "0",
      limit: "200",
    });
    const status = node("jobStatusFilter")?.value;
    if (status) params.set("status", status);
    return params;
  }

  async function refreshManagedJobs() {
    try {
      const result = await jobApi(`/api/jobs?${jobQueryParams()}`);
      center.jobs = result.items || [];
      node("jobListMeta").textContent = `共 ${Number(result.total || 0).toLocaleString()} 个任务`;
      renderJobs();
      clearTimeout(center.poller);
      if (center.jobs.some((job) => activeStatuses.has(job.status))) {
        center.poller = setTimeout(refreshManagedJobs, 2500);
      }
    } catch (error) {
      notify(`任务列表加载失败：${error.message}`, true);
    }
  }

  function filteredGroups(jobId) {
    const data = center.groups.get(jobId) || [];
    const container = node(`job-groups-${jobId}`);
    const q = container?.querySelector("[data-group-q]")?.value.trim().toLowerCase() || "";
    const status = container?.querySelector("[data-group-status]")?.value || "";
    return data.filter((group) => {
      if (status && group.status !== status) return false;
      if (!q) return true;
      const text = `${group.theme} ${group.family} ${group.group_id} ${group.strategy} ${(group.errors || []).join(" ")}`.toLowerCase();
      return text.includes(q);
    });
  }

  function renderGroups(jobId) {
    const container = node(`job-groups-${jobId}`);
    if (!container) return;
    const job = center.jobs.find((item) => item.job_id === jobId);
    const active = job ? activeStatuses.has(job.status) : false;
    const rows = filteredGroups(jobId);
    const allCount = (center.groups.get(jobId) || []).length;
    container.innerHTML = `
      <div class="group-toolbar">
        <label>过滤子任务 <input data-group-q placeholder="接口、区块或错误" /></label>
        <label>状态
          <select data-group-status>
            <option value="">全部</option>
            <option value="FAILED">失败</option>
            <option value="SUCCESS">成功</option>
            <option value="RUNNING">运行中</option>
            <option value="RETRYING">重试中</option>
            <option value="PENDING">等待</option>
          </select>
        </label>
        <span class="muted">显示 ${rows.length}/${allCount}</span>
      </div>
      <div class="subtask-table-wrap">
        <table class="subtask-table">
          <thead><tr><th>状态</th><th>区块</th><th>接口</th><th>策略</th><th>记录</th><th>次数</th><th>耗时</th><th>错误/来源</th><th>操作</th></tr></thead>
          <tbody>${rows.map((group) => {
            const errors = (group.errors || []).join("\n");
            const sources = (group.source_urls || []).join("\n");
            return `<tr class="subtask-${escape(group.status.toLowerCase())}">
              <td><span class="status group-status ${escape(group.status)}">${escape(groupStatusLabels[group.status] || group.status)}</span></td>
              <td>${escape(group.theme)}</td>
              <td><code>${escape(group.family)}</code><div class="muted small-text">${escape(group.group_id)}</div></td>
              <td>${escape(group.strategy)}${group.used_fallback ? '<span class="fallback-badge">回退</span>' : ""}</td>
              <td>${Number(group.record_count || 0).toLocaleString()}</td>
              <td>${group.attempt_count || 0}</td>
              <td>${escape(formatDuration(group.duration_seconds))}</td>
              <td>${errors ? `<details><summary class="failure-text">查看错误</summary><pre>${escape(errors)}</pre></details>` : "—"}${sources ? `<details><summary>来源URL</summary><pre>${escape(sources)}</pre></details>` : ""}</td>
              <td><button type="button" data-group-retry data-job-id="${escape(jobId)}" data-group-id="${escape(group.group_id)}" ${active ? "disabled" : ""}>重新执行</button></td>
            </tr>`;
          }).join("")}</tbody>
        </table>
      </div>`;
  }

  async function loadGroups(jobId, force = false) {
    if (!force && center.groups.has(jobId)) {
      renderGroups(jobId);
      return;
    }
    try {
      const result = await jobApi(`/api/jobs/${encodeURIComponent(jobId)}/groups?limit=500`);
      center.groups.set(jobId, result.items || []);
      renderGroups(jobId);
    } catch (error) {
      const container = node(`job-groups-${jobId}`);
      if (container) container.innerHTML = `<div class="failure-text">子任务加载失败：${escape(error.message)}</div>`;
    }
  }

  async function executeJobAction(action, jobId) {
    try {
      if (action === "retry-failed") {
        await jobApi(`/api/jobs/${encodeURIComponent(jobId)}/retry-failed`, { method: "POST" });
        notify("已开始只重试失败子任务");
      } else if (action === "rerun") {
        const created = await jobApi(`/api/jobs/${encodeURIComponent(jobId)}/rerun`, { method: "POST" });
        notify(`已创建新的完整任务：${created.job_id}`);
      } else if (action === "set-current") {
        await jobApi(`/api/jobs/${encodeURIComponent(jobId)}/set-current`, {
          method: "POST", body: JSON.stringify({ allow_partial: false }),
        });
        notify("已设为当前搜索数据版本");
      } else if (action === "cancel") {
        await jobApi(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST" });
        notify("已请求取消任务");
      } else if (action === "delete") {
        const job = center.jobs.find((item) => item.job_id === jobId);
        const confirmation = window.prompt(`将永久删除 ${job?.stock_name || ""}（${job?.stock_code || ""}）\n任务 ${jobId}\n及其JSON、Excel、Parquet、DuckDB、原始缓存和整个文件夹。\n\n请输入 DELETE 确认：`);
        if (confirmation !== "DELETE") return notify("已取消删除");
        await jobApi(`/api/jobs/${encodeURIComponent(jobId)}?confirm=DELETE`, { method: "DELETE" });
        center.expanded.delete(jobId);
        center.groups.delete(jobId);
        notify("任务及对应文件夹已删除");
      }
      await refreshManagedJobs();
    } catch (error) {
      notify(error.message, true);
    }
  }

  async function retryGroup(jobId, groupId) {
    try {
      await jobApi(`/api/jobs/${encodeURIComponent(jobId)}/groups/${encodeURIComponent(groupId)}/retry`, { method: "POST" });
      notify("已开始重新执行该子任务");
      center.groups.delete(jobId);
      await refreshManagedJobs();
    } catch (error) {
      notify(error.message, true);
    }
  }

  async function refreshSearchVersion() {
    const target = node("searchVersionInfo");
    const code = node("searchCode")?.value.trim();
    if (!target || !/^\d{6}$/.test(code || "")) return;
    try {
      const result = await jobApi(`/api/stocks/${code}/latest`);
      const pointer = result.pointer || {};
      target.textContent = `当前版本：${pointer.stock_name || code} · ${pointer.job_id || "—"} · 失败 ${pointer.failed_groups || 0} · ${formatTime(pointer.updated_at_utc)}`;
      target.classList.remove("failure-text");
    } catch (error) {
      target.textContent = `当前没有可用的完整数据版本：${error.message}`;
      target.classList.add("failure-text");
    }
  }

  const list = node("managedJobList");
  if (!list) return;

  list.addEventListener("click", (event) => {
    const jobButton = event.target.closest("button[data-job-action]");
    if (jobButton) {
      const jobId = jobButton.dataset.jobId;
      if (jobButton.dataset.jobAction === "expand") {
        if (center.expanded.has(jobId)) center.expanded.delete(jobId);
        else center.expanded.add(jobId);
        renderJobs();
        return;
      }
      executeJobAction(jobButton.dataset.jobAction, jobId);
      return;
    }
    const retryButton = event.target.closest("button[data-group-retry]");
    if (retryButton) retryGroup(retryButton.dataset.jobId, retryButton.dataset.groupId);
  });

  list.addEventListener("input", (event) => {
    if (event.target.matches("[data-group-q]")) renderGroups(event.target.closest(".job-groups").id.replace("job-groups-", ""));
  });
  list.addEventListener("change", (event) => {
    if (event.target.matches("[data-group-status]")) renderGroups(event.target.closest(".job-groups").id.replace("job-groups-", ""));
  });

  node("jobFilter")?.addEventListener("input", () => {
    clearTimeout(center.filterTimer);
    center.filterTimer = setTimeout(refreshManagedJobs, 250);
  });
  node("jobStatusFilter")?.addEventListener("change", refreshManagedJobs);
  node("jobSort")?.addEventListener("change", refreshManagedJobs);
  node("refreshJobs")?.addEventListener("click", () => setTimeout(refreshManagedJobs, 50));
  node("startJob")?.addEventListener("click", () => setTimeout(refreshManagedJobs, 500));
  node("expandAllJobs")?.addEventListener("click", () => {
    center.jobs.forEach((job) => center.expanded.add(job.job_id));
    renderJobs();
  });
  node("collapseAllJobs")?.addEventListener("click", () => {
    center.expanded.clear();
    renderJobs();
  });
  node("runSearch")?.addEventListener("click", refreshSearchVersion);
  node("searchCode")?.addEventListener("change", refreshSearchVersion);

  setTimeout(refreshManagedJobs, 250);
  setTimeout(refreshSearchVersion, 500);
})();
