(function () {
  "use strict";

  const esc = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

  const clone = (value) => JSON.parse(JSON.stringify(value));

  class ResearchGrid {
    constructor(root, options) {
      this.root = root;
      this.options = options;
      this.columns = options.columns || [];
      this.state = {
        filters: [],
        sort: [],
        page: 1,
        pageSize: options.pageSize || 200,
        hidden: new Set(),
        widths: {},
        result: null,
        pageFind: "",
        loading: false,
      };
      this.persistKey = options.persistKey || "research-grid";
      this.restoreView();
      this.renderShell();
    }

    get visibleColumns() {
      return this.columns.filter((column) => !this.state.hidden.has(column.key));
    }

    buildQuery(page = this.state.page) {
      const base = clone(this.options.getQuery ? this.options.getQuery() : {});
      base.filters = [...(base.filters || []), ...clone(this.state.filters)];
      base.sort = clone(this.state.sort);
      base.page = page;
      base.page_size = this.state.pageSize;
      return base;
    }

    async load(page = 1) {
      if (this.state.loading) return;
      this.state.loading = true;
      this.state.page = Math.max(1, page);
      this.status.textContent = "正在查询…";
      try {
        const result = await this.options.fetchRows(this.buildQuery(this.state.page));
        this.state.result = result;
        if (result.page_count && this.state.page > result.page_count) {
          this.state.page = result.page_count;
          this.state.loading = false;
          return this.load(this.state.page);
        }
        this.renderResult();
        if (this.options.onResult) this.options.onResult(result);
      } catch (error) {
        this.status.textContent = `查询失败：${error.message}`;
        if (this.options.onError) this.options.onError(error);
      } finally {
        this.state.loading = false;
      }
    }

    renderShell() {
      this.root.innerHTML = `
        <div class="rg-toolbar">
          <div class="rg-toolbar-left">
            <button type="button" data-action="columns">列设置</button>
            <button type="button" data-action="save">保存视图</button>
            <button type="button" data-action="restore">恢复视图</button>
            <button type="button" data-action="clear">清除列筛选</button>
            <button type="button" data-action="export">导出筛选结果</button>
          </div>
          <div class="rg-toolbar-right">
            <label class="rg-page-find">当前页查找 <input type="search" placeholder="仅高亮当前页" /></label>
            <label>每页
              <select data-role="page-size">
                <option value="100">100</option>
                <option value="200">200</option>
                <option value="500">500</option>
              </select>
            </label>
            <span data-role="status" class="muted"></span>
          </div>
        </div>
        <div data-role="filter-chips" class="rg-filter-chips"></div>
        <div class="rg-table-wrap"><table class="rg-table"><thead></thead><tbody></tbody></table></div>
        <div class="rg-pagination">
          <button type="button" data-action="first">首页</button>
          <button type="button" data-action="prev">上一页</button>
          <span data-role="page-info"></span>
          <button type="button" data-action="next">下一页</button>
          <button type="button" data-action="last">末页</button>
          <label>跳转 <input data-role="page-jump" type="number" min="1" /></label>
        </div>
      `;
      this.thead = this.root.querySelector("thead");
      this.tbody = this.root.querySelector("tbody");
      this.status = this.root.querySelector('[data-role="status"]');
      this.chips = this.root.querySelector('[data-role="filter-chips"]');
      this.pageInfo = this.root.querySelector('[data-role="page-info"]');
      const pageSize = this.root.querySelector('[data-role="page-size"]');
      pageSize.value = String(this.state.pageSize);
      pageSize.addEventListener("change", () => {
        this.state.pageSize = Number(pageSize.value);
        this.persistView();
        this.load(1);
      });
      this.root.querySelector(".rg-page-find input").addEventListener("input", (event) => {
        this.state.pageFind = event.target.value.trim().toLowerCase();
        this.applyPageHighlight();
      });
      this.root.addEventListener("click", (event) => this.handleClick(event));
      this.root.querySelector('[data-role="page-jump"]').addEventListener("change", (event) => {
        const target = Number(event.target.value);
        if (target > 0) this.load(target);
      });
      this.renderHeader();
      this.renderFilterChips();
    }

    handleClick(event) {
      const button = event.target.closest("button");
      if (!button || !this.root.contains(button)) return;
      const action = button.dataset.action;
      if (action === "columns") this.openColumnChooser(button);
      else if (action === "save") this.persistView(true);
      else if (action === "restore") { this.restoreView(); this.renderHeader(); this.renderFilterChips(); this.load(1); }
      else if (action === "clear") { this.state.filters = []; this.persistView(); this.renderFilterChips(); this.load(1); }
      else if (action === "export") this.exportRows();
      else if (action === "first") this.load(1);
      else if (action === "prev") this.load(Math.max(1, this.state.page - 1));
      else if (action === "next") this.load(Math.min(this.state.result?.page_count || 1, this.state.page + 1));
      else if (action === "last") this.load(this.state.result?.page_count || 1);
      else if (action === "filter") this.openFilter(button.dataset.column, button);
      else if (action === "sort") this.cycleSort(button.dataset.column);
      else if (action === "remove-filter") this.removeFilter(Number(button.dataset.index));
    }

    renderHeader() {
      const sortMap = new Map(this.state.sort.map((item) => [item.column, item.direction]));
      const filterColumns = new Set(this.state.filters.map((item) => item.column));
      this.thead.innerHTML = `<tr>${this.visibleColumns.map((column) => {
        const direction = sortMap.get(column.key);
        const filtered = filterColumns.has(column.key);
        const width = this.state.widths[column.key] || column.width || 150;
        return `<th data-column="${esc(column.key)}" style="width:${width}px;min-width:${Math.min(width, 100)}px">
          <div class="rg-th-content">
            <button type="button" class="rg-th-label" data-action="sort" data-column="${esc(column.key)}" title="点击排序">
              ${esc(column.label)} <span>${direction === "asc" ? "↑" : direction === "desc" ? "↓" : ""}</span>
            </button>
            <button type="button" class="rg-filter-button${filtered ? " active" : ""}" data-action="filter" data-column="${esc(column.key)}" title="筛选">▼</button>
          </div>
          <span class="rg-resize" data-column="${esc(column.key)}"></span>
        </th>`;
      }).join("")}</tr>`;
      this.attachResizeHandlers();
    }

    renderResult() {
      const result = this.state.result || { rows: [], total: 0, page: 1, page_count: 0 };
      this.status.textContent = `符合条件 ${result.total.toLocaleString()} 条`;
      this.pageInfo.textContent = `第 ${result.page || 1} / ${Math.max(1, result.page_count || 1)} 页`;
      if (!result.rows?.length) {
        this.tbody.innerHTML = `<tr><td colspan="${Math.max(1, this.visibleColumns.length)}" class="empty">暂无数据</td></tr>`;
        return;
      }
      this.tbody.innerHTML = result.rows.map((row) => `<tr>${this.visibleColumns.map((column) => {
        const raw = row[column.key];
        const display = column.format ? column.format(raw, row) : raw;
        return `<td data-column="${esc(column.key)}" title="${esc(raw)}">${esc(display)}</td>`;
      }).join("")}</tr>`).join("");
      this.applyPageHighlight();
    }

    applyPageHighlight() {
      const query = this.state.pageFind;
      this.tbody.querySelectorAll("tr").forEach((row) => {
        row.classList.toggle("rg-page-match", Boolean(query) && row.textContent.toLowerCase().includes(query));
      });
    }

    cycleSort(column) {
      const existing = this.state.sort.find((item) => item.column === column);
      if (!existing) this.state.sort = [{ column, direction: "asc" }];
      else if (existing.direction === "asc") this.state.sort = [{ column, direction: "desc" }];
      else this.state.sort = [];
      this.persistView();
      this.renderHeader();
      this.load(1);
    }

    removeFilter(index) {
      this.state.filters.splice(index, 1);
      this.persistView();
      this.renderFilterChips();
      this.renderHeader();
      this.load(1);
    }

    renderFilterChips() {
      if (!this.state.filters.length) {
        this.chips.innerHTML = '<span class="muted">未启用逐列筛选</span>';
        return;
      }
      this.chips.innerHTML = `<strong>当前列筛选：</strong>${this.state.filters.map((filter, index) => {
        const column = this.columns.find((item) => item.key === filter.column);
        let value = filter.values?.length ? filter.values.join("、") : filter.value ?? "";
        if (filter.operator === "between") value = `${filter.lower ?? ""}～${filter.upper ?? ""}`;
        return `<span class="rg-chip">${esc(column?.label || filter.column)}：${esc(filter.operator)} ${esc(value)}
          <button type="button" data-action="remove-filter" data-index="${index}" aria-label="删除">×</button></span>`;
      }).join("")}`;
    }

    async openFilter(columnKey, anchor) {
      this.closePopover();
      const column = this.columns.find((item) => item.key === columnKey);
      if (!column) return;
      const current = this.state.filters.find((item) => item.column === columnKey);
      const popover = document.createElement("div");
      popover.className = "rg-popover";
      popover.innerHTML = this.filterFormHtml(column, current);
      document.body.appendChild(popover);
      this.popover = popover;
      const rect = anchor.getBoundingClientRect();
      popover.style.left = `${Math.min(window.innerWidth - 360, Math.max(8, rect.left - 250))}px`;
      popover.style.top = `${rect.bottom + 6 + window.scrollY}px`;

      const operator = popover.querySelector('[data-role="operator"]');
      const refreshForm = () => this.refreshFilterInputs(popover, column, operator.value, current);
      operator.addEventListener("change", refreshForm);
      refreshForm();

      popover.querySelector('[data-action="apply-filter"]').addEventListener("click", () => {
        const filter = this.collectFilter(popover, column);
        this.state.filters = this.state.filters.filter((item) => item.column !== columnKey);
        if (filter) this.state.filters.push(filter);
        this.persistView();
        this.closePopover();
        this.renderFilterChips();
        this.renderHeader();
        this.load(1);
      });
      popover.querySelector('[data-action="clear-filter"]').addEventListener("click", () => {
        this.state.filters = this.state.filters.filter((item) => item.column !== columnKey);
        this.persistView();
        this.closePopover();
        this.renderFilterChips();
        this.renderHeader();
        this.load(1);
      });
      popover.querySelector('[data-action="hide-column"]').addEventListener("click", () => {
        this.state.hidden.add(columnKey);
        this.persistView();
        this.closePopover();
        this.renderHeader();
        this.renderResult();
      });
    }

    filterFormHtml(column, current) {
      const textOps = [
        ["in", "从唯一值多选"], ["contains", "包含"], ["not_contains", "不包含"],
        ["exact", "等于"], ["not_equal", "不等于"], ["prefix", "开头是"],
        ["is_empty", "为空"], ["not_empty", "非空"],
      ];
      const rangeOps = [
        ["between", "区间"], ["gte", "大于或等于"], ["lte", "小于或等于"],
        ["exact", "等于"], ["not_equal", "不等于"], ["is_empty", "为空"], ["not_empty", "非空"],
      ];
      const ops = ["number", "date"].includes(column.type) ? rangeOps : textOps;
      const selected = current?.operator || ops[0][0];
      return `<div class="rg-popover-title">筛选：${esc(column.label)}</div>
        <label>条件<select data-role="operator">${ops.map(([value, label]) => `<option value="${value}"${value === selected ? " selected" : ""}>${label}</option>`).join("")}</select></label>
        <div data-role="filter-inputs"></div>
        <div class="rg-popover-actions">
          <button type="button" data-action="clear-filter">清除此列</button>
          <button type="button" data-action="hide-column">隐藏此列</button>
          <button type="button" class="primary" data-action="apply-filter">应用</button>
        </div>`;
    }

    refreshFilterInputs(popover, column, operator, current) {
      const area = popover.querySelector('[data-role="filter-inputs"]');
      if (["is_empty", "not_empty"].includes(operator)) {
        area.innerHTML = '<div class="muted">此条件不需要输入值</div>';
        return;
      }
      if (operator === "in") {
        area.innerHTML = `<label>搜索唯一值<input data-role="facet-term" type="search" placeholder="输入后筛选可选值" /></label>
          <div data-role="facet-values" class="rg-facet-values"><span class="muted">加载中…</span></div>`;
        const input = area.querySelector('[data-role="facet-term"]');
        let timer;
        const load = () => {
          clearTimeout(timer);
          timer = setTimeout(() => this.loadFacetValues(popover, column, input.value, current), 180);
        };
        input.addEventListener("input", load);
        this.loadFacetValues(popover, column, "", current);
        return;
      }
      const inputType = column.type === "date" ? "date" : column.type === "number" ? "number" : "text";
      if (operator === "between") {
        area.innerHTML = `<label>起始值<input data-role="lower" type="${inputType}" value="${esc(current?.lower ?? "")}" /></label>
          <label>结束值<input data-role="upper" type="${inputType}" value="${esc(current?.upper ?? "")}" /></label>`;
      } else {
        area.innerHTML = `<label>筛选值<input data-role="value" type="${inputType}" value="${esc(current?.value ?? "")}" /></label>`;
      }
    }

    async loadFacetValues(popover, column, term, current) {
      const container = popover.querySelector('[data-role="facet-values"]');
      if (!container || !this.options.fetchFacet) return;
      try {
        const data = await this.options.fetchFacet(column.key, term, this.buildQuery(1));
        if (data.kind === "numeric") {
          container.innerHTML = `<div>最小值：${esc(data.min)}<br />最大值：${esc(data.max)}<br />空值：${esc(data.null_count)}</div>`;
          return;
        }
        const selected = new Set(current?.operator === "in" ? current.values || [] : []);
        container.innerHTML = (data.values || []).map((item) => `<label class="rg-facet-item">
          <input type="checkbox" value="${esc(item.value)}"${selected.has(item.value) ? " checked" : ""} />
          <span>${esc(item.value || "（空）")}</span><small>${item.count.toLocaleString()}</small>
        </label>`).join("") || '<span class="muted">没有可选值</span>';
      } catch (error) {
        container.innerHTML = `<span class="error-text">${esc(error.message)}</span>`;
      }
    }

    collectFilter(popover, column) {
      const operator = popover.querySelector('[data-role="operator"]').value;
      const filter = { column: column.key, operator, enabled: true };
      if (["is_empty", "not_empty"].includes(operator)) return filter;
      if (operator === "in") {
        filter.values = [...popover.querySelectorAll('[data-role="facet-values"] input:checked')].map((item) => item.value);
        return filter.values.length ? filter : null;
      }
      if (operator === "between") {
        filter.lower = popover.querySelector('[data-role="lower"]').value;
        filter.upper = popover.querySelector('[data-role="upper"]').value;
        return filter.lower !== "" && filter.upper !== "" ? filter : null;
      }
      const value = popover.querySelector('[data-role="value"]').value;
      if (value === "") return null;
      filter.value = column.type === "number" ? Number(value) : value;
      return filter;
    }

    openColumnChooser(anchor) {
      this.closePopover();
      const popover = document.createElement("div");
      popover.className = "rg-popover rg-column-chooser";
      popover.innerHTML = `<div class="rg-popover-title">显示列</div>${this.columns.map((column) => `<label class="rg-facet-item">
        <input type="checkbox" value="${esc(column.key)}"${this.state.hidden.has(column.key) ? "" : " checked"} />
        <span>${esc(column.label)}</span>
      </label>`).join("")}<div class="rg-popover-actions"><button type="button" class="primary">完成</button></div>`;
      document.body.appendChild(popover);
      this.popover = popover;
      const rect = anchor.getBoundingClientRect();
      popover.style.left = `${Math.min(window.innerWidth - 340, rect.left)}px`;
      popover.style.top = `${rect.bottom + 6 + window.scrollY}px`;
      popover.querySelector("button").addEventListener("click", () => {
        const visible = new Set([...popover.querySelectorAll("input:checked")].map((item) => item.value));
        this.state.hidden = new Set(this.columns.filter((column) => !visible.has(column.key)).map((column) => column.key));
        this.persistView();
        this.closePopover();
        this.renderHeader();
        this.renderResult();
      });
    }

    closePopover() {
      if (this.popover) this.popover.remove();
      this.popover = null;
    }

    attachResizeHandlers() {
      this.thead.querySelectorAll(".rg-resize").forEach((handle) => {
        handle.addEventListener("mousedown", (event) => {
          event.preventDefault();
          const column = handle.dataset.column;
          const th = handle.closest("th");
          const startX = event.clientX;
          const startWidth = th.getBoundingClientRect().width;
          const move = (moveEvent) => {
            this.state.widths[column] = Math.max(80, Math.round(startWidth + moveEvent.clientX - startX));
            th.style.width = `${this.state.widths[column]}px`;
          };
          const up = () => {
            document.removeEventListener("mousemove", move);
            document.removeEventListener("mouseup", up);
            this.persistView();
          };
          document.addEventListener("mousemove", move);
          document.addEventListener("mouseup", up);
        });
      });
    }

    async exportRows() {
      if (!this.options.exportRows) return;
      try {
        await this.options.exportRows(this.buildQuery(1));
      } catch (error) {
        if (this.options.onError) this.options.onError(error);
      }
    }

    persistView(showMessage = false) {
      const payload = {
        filters: this.state.filters,
        sort: this.state.sort,
        pageSize: this.state.pageSize,
        hidden: [...this.state.hidden],
        widths: this.state.widths,
      };
      localStorage.setItem(this.persistKey, JSON.stringify(payload));
      if (showMessage && this.options.onNotice) this.options.onNotice("当前筛选视图已保存到浏览器");
    }

    restoreView() {
      try {
        const payload = JSON.parse(localStorage.getItem(this.persistKey) || "null");
        if (!payload) return;
        this.state.filters = payload.filters || [];
        this.state.sort = payload.sort || [];
        this.state.pageSize = payload.pageSize || this.state.pageSize;
        this.state.hidden = new Set(payload.hidden || []);
        this.state.widths = payload.widths || {};
      } catch (_) {
        localStorage.removeItem(this.persistKey);
      }
    }
  }

  window.ResearchGrid = ResearchGrid;
})();
