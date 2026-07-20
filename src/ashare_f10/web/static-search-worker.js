"use strict";

let facts = [];
let rawPayload = null;

const TEXT_COLUMNS = ["field_name_cn", "field_key", "theme", "family", "dataset", "value_text", "unit", "source_url"];
const DATE_KEYS = ["REPORT_DATE", "END_DATE", "TRADE_DATE", "NOTICE_DATE", "PUBLISH_DATE", "UPDATE_DATE", "report_date", "notice_date", "publish_time", "showDateTime"];

function text(value) { return value === null || value === undefined ? "" : String(value); }
function normalizeDate(value) { const valueText = text(value); return valueText.length >= 10 ? valueText.slice(0, 10) : valueText || null; }
function numeric(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "boolean") return value ? 1 : 0;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value.replaceAll(",", ""));
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function fieldMapping(payload) {
  const mapping = payload.field_mapping || payload.display_field_map || {};
  return mapping.global || mapping;
}

function resolveLabel(mapping, key) {
  const item = mapping[key];
  if (typeof item === "string") return item;
  return item?.label || item?.中文项目名称 || item?.中文字段名 || key;
}

function flattenPayload(payload) {
  const mapping = fieldMapping(payload);
  const security = payload.metadata?.security || {};
  const securityCode = security.security_code || security.code || payload.metadata?.security_code || "";
  const output = [];
  let rowId = 0;
  for (const group of payload.groups || []) {
    const theme = group.theme || "";
    const family = group.family || "";
    const dataset = `${theme} / ${family}`;
    for (const record of group.records || []) {
      if (!record || typeof record !== "object" || Array.isArray(record)) continue;
      const reportDate = normalizeDate(record.REPORT_DATE);
      let eventDate = null;
      for (const key of DATE_KEYS) {
        if (record[key] !== undefined && record[key] !== null && record[key] !== "") {
          eventDate = normalizeDate(record[key]);
          break;
        }
      }
      for (const [key, value] of Object.entries(record)) {
        if (key.startsWith("_") && !["_SOURCE_URL", "_FETCHED_AT_UTC"].includes(key)) continue;
        let valueText;
        try { valueText = typeof value === "object" ? JSON.stringify(value) : text(value); }
        catch (_) { valueText = text(value); }
        output.push({
          row_id: ++rowId,
          security_code: securityCode,
          theme,
          family,
          dataset,
          report_date: reportDate,
          event_date: eventDate,
          field_key: key,
          field_name_cn: resolveLabel(mapping, key),
          value_text: valueText,
          value_num: numeric(value),
          unit: typeof mapping[key] === "object" ? mapping[key]?.unit || "" : "",
          source_url: record._SOURCE_URL || "",
          base_score: 0,
          secondary_score: 0,
          score: 0,
        });
      }
    }
  }
  return output;
}

function selectedColumns(columns) { return columns?.length ? columns : TEXT_COLUMNS; }

function bigrams(value) {
  const input = value.toLowerCase();
  if (input.length < 2) return new Set([input]);
  const result = new Set();
  for (let index = 0; index < input.length - 1; index += 1) result.add(input.slice(index, index + 2));
  return result;
}

function fuzzyScore(query, value) {
  const q = query.toLowerCase();
  const v = value.toLowerCase();
  if (!q || !v) return 0;
  if (v === q) return 100;
  if (v.includes(q)) return 96;
  if (v.startsWith(q)) return 98;
  const left = bigrams(q);
  const right = bigrams(v);
  let overlap = 0;
  for (const item of left) if (right.has(item)) overlap += 1;
  return Math.round((2 * overlap / Math.max(1, left.size + right.size)) * 100);
}

function matchScore(row, step) {
  const values = selectedColumns(step.columns).map((column) => text(row[column]));
  const query = text(step.query).trim();
  if (step.match_type === "empty") return values.some((value) => !value) ? 100 : null;
  if (step.match_type === "not_empty") return values.some((value) => Boolean(value)) ? 100 : null;
  if (!query) return null;
  const q = query.toLowerCase();
  if (step.match_type === "exact") return values.some((value) => value.toLowerCase() === q) ? 100 : null;
  if (step.match_type === "prefix") return values.some((value) => value.toLowerCase().startsWith(q)) ? 100 : null;
  if (step.match_type === "contains") return values.some((value) => value.toLowerCase().includes(q)) ? 100 : null;
  if (step.match_type === "regex") {
    if (query.length > 100 || /\([^)]*[+*][^)]*\)[+*{]/.test(query)) throw new Error("正则表达式过长或可能导致超时");
    const regex = new RegExp(query, "i");
    return values.some((value) => regex.test(value)) ? 100 : null;
  }
  const score = Math.max(...values.map((value) => fuzzyScore(query, value)), 0);
  return score >= Number(step.threshold ?? 60) ? score : null;
}

function effectiveValue(row, column) { return column === "effective_date" ? row.report_date || row.event_date : row[column]; }

function matchesFilter(row, filter) {
  if (filter.enabled === false) return true;
  const value = effectiveValue(row, filter.column);
  const valueText = text(value).toLowerCase();
  const target = text(filter.value).toLowerCase();
  if (filter.operator === "in") return (filter.values || []).map(String).includes(text(value));
  if (filter.operator === "not_in") return !(filter.values || []).map(String).includes(text(value));
  if (filter.operator === "contains") return valueText.includes(target);
  if (filter.operator === "not_contains") return !valueText.includes(target);
  if (filter.operator === "exact") return valueText === target;
  if (filter.operator === "not_equal") return valueText !== target;
  if (filter.operator === "prefix") return valueText.startsWith(target);
  if (filter.operator === "is_empty") return value === null || value === undefined || value === "";
  if (filter.operator === "not_empty") return value !== null && value !== undefined && value !== "";
  if (value === null || value === undefined) return false;
  const comparable = typeof value === "number" ? value : text(value);
  if (filter.operator === "gte") return comparable >= filter.value;
  if (filter.operator === "lte") return comparable <= filter.value;
  if (filter.operator === "between") return comparable >= filter.lower && comparable <= filter.upper;
  return true;
}

function runQuery(request) {
  const stageCounts = [{ stage: "raw", label: "原始事实记录", count: facts.length }];
  const filters = request.filters || [];
  let scope = facts.filter((row) => filters.every((filter) => matchesFilter(row, filter)));
  if (filters.length) stageCounts.push({ stage: "column_filters", label: "逐列筛选", count: scope.length });

  const scoreLists = new Map(scope.map((row) => [row.row_id, []]));
  const baseScores = new Map();
  const secondaryScores = new Map();
  let current = scope;
  if (request.base_query || ["empty", "not_empty"].includes(request.base_match_type)) {
    const step = {
      query: request.base_query || "",
      match_type: request.base_match_type || "fuzzy",
      columns: request.base_columns || [],
      threshold: request.base_threshold ?? 60,
    };
    current = current.filter((row) => {
      const score = matchScore(row, step);
      if (score === null) return false;
      baseScores.set(row.row_id, score);
      scoreLists.get(row.row_id).push(score);
      return true;
    });
    stageCounts.push({ stage: "base_query", label: request.base_query || request.base_match_type, count: current.length });
  }

  (request.search_steps || []).filter((step) => step.enabled !== false).forEach((step, index) => {
    const searchSpace = step.operation === "or" ? scope : current;
    const matches = new Map();
    for (const row of searchSpace) {
      const score = matchScore(row, step);
      if (score !== null) matches.set(row.row_id, { row, score });
    }
    if (step.operation === "include") current = current.filter((row) => matches.has(row.row_id));
    else if (step.operation === "exclude") current = current.filter((row) => !matches.has(row.row_id));
    else {
      const union = new Map(current.map((row) => [row.row_id, row]));
      for (const [rowId, item] of matches) union.set(rowId, item.row);
      current = [...union.values()];
    }
    if (step.operation !== "exclude") {
      for (const [rowId, item] of matches) {
        if (!scoreLists.has(rowId)) scoreLists.set(rowId, []);
        scoreLists.get(rowId).push(item.score);
        if (!secondaryScores.has(rowId)) secondaryScores.set(rowId, []);
        secondaryScores.get(rowId).push(item.score);
      }
    }
    stageCounts.push({ stage: `search_step_${index + 1}`, label: `${step.operation}:${step.query || step.match_type}`, count: current.length });
  });

  let rows = current.map((row) => {
    const scores = scoreLists.get(row.row_id) || [];
    const secondary = secondaryScores.get(row.row_id) || [];
    return {
      ...row,
      base_score: baseScores.get(row.row_id) || 0,
      secondary_score: secondary.length ? secondary.reduce((a, b) => a + b, 0) / secondary.length : 0,
      score: scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : 0,
    };
  });

  const sorts = request.sort?.length ? request.sort : [
    ...((request.base_query || request.search_steps?.length) ? [{ column: "score", direction: "desc" }] : []),
    { column: "effective_date", direction: "desc" },
  ];
  [...sorts].reverse().forEach((sort) => {
    const nonEmpty = rows.filter((row) => effectiveValue(row, sort.column) !== null && effectiveValue(row, sort.column) !== undefined);
    const empty = rows.filter((row) => effectiveValue(row, sort.column) === null || effectiveValue(row, sort.column) === undefined);
    nonEmpty.sort((left, right) => {
      const a = effectiveValue(left, sort.column);
      const b = effectiveValue(right, sort.column);
      if (a === b) return 0;
      const result = a < b ? -1 : 1;
      return sort.direction === "desc" ? -result : result;
    });
    rows = [...nonEmpty, ...empty];
  });

  const total = rows.length;
  const pageSize = Number(request.page_size || 200);
  const page = Math.max(1, Number(request.page || 1));
  const start = (page - 1) * pageSize;
  return {
    raw_total: facts.length,
    total,
    page,
    page_size: pageSize,
    page_count: Math.ceil(total / pageSize),
    stage_counts: stageCounts,
    rows: rows.slice(start, start + pageSize).map(({ row_id: _, ...row }) => row),
    allRows: rows,
  };
}

function runFacet(request, column, term, limit) {
  const cloned = JSON.parse(JSON.stringify(request));
  cloned.filters = (cloned.filters || []).filter((filter) => filter.column !== column);
  cloned.page = 1;
  cloned.page_size = 1;
  const result = runQuery(cloned);
  const values = result.allRows.map((row) => effectiveValue(row, column));
  if (["value_num", "score", "base_score", "secondary_score"].includes(column)) {
    const numericValues = values.filter((value) => typeof value === "number" && Number.isFinite(value));
    return { column, kind: "numeric", min: numericValues.length ? Math.min(...numericValues) : null, max: numericValues.length ? Math.max(...numericValues) : null, null_count: values.length - numericValues.length, total: values.length };
  }
  const counts = new Map();
  for (const value of values) {
    const key = text(value);
    if (term && !key.toLowerCase().includes(term.toLowerCase())) continue;
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  const items = [...counts.entries()].map(([value, count]) => ({ value, count })).sort((a, b) => b.count - a.count || a.value.localeCompare(b.value));
  return { column, kind: ["report_date", "event_date", "effective_date"].includes(column) ? "date" : "text", values: items.slice(0, limit), truncated: items.length > limit, total_distinct: items.length, total: values.length };
}

function csvEscape(value) {
  const valueText = text(value);
  return /[",\n]/.test(valueText) ? `"${valueText.replaceAll('"', '""')}"` : valueText;
}

self.onmessage = (event) => {
  const { id, type } = event.data || {};
  try {
    if (type === "load") {
      rawPayload = JSON.parse(event.data.text);
      facts = flattenPayload(rawPayload);
      self.postMessage({ id, ok: true, result: { fact_count: facts.length, group_count: rawPayload.groups?.length || 0, security: rawPayload.metadata?.security || {} } });
      return;
    }
    if (type === "query") {
      const result = runQuery(event.data.request);
      delete result.allRows;
      self.postMessage({ id, ok: true, result });
      return;
    }
    if (type === "facet") {
      const result = runFacet(event.data.request, event.data.column, event.data.term || "", event.data.limit || 200);
      self.postMessage({ id, ok: true, result });
      return;
    }
    if (type === "export") {
      const result = runQuery({ ...event.data.request, page: 1, page_size: 1 });
      const rows = result.allRows.slice(0, event.data.maxRows || 100000);
      const columns = ["security_code", "theme", "family", "dataset", "report_date", "event_date", "field_key", "field_name_cn", "value_text", "value_num", "unit", "source_url", "base_score", "secondary_score", "score"];
      const csv = [columns.join(","), ...rows.map((row) => columns.map((column) => csvEscape(row[column])).join(","))].join("\n");
      self.postMessage({ id, ok: true, result: { csv, row_count: rows.length } });
      return;
    }
    throw new Error(`不支持的Worker操作：${type}`);
  } catch (error) {
    self.postMessage({ id, ok: false, error: error.message || String(error) });
  }
};
