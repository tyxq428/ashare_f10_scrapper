const fs = require("fs");
const path = require("path");
const vm = require("vm");

const messages = [];
const context = {
  console,
  Map,
  Set,
  JSON,
  Number,
  String,
  Math,
  RegExp,
  Error,
  self: {
    postMessage(message) { messages.push(message); },
  },
};
vm.createContext(context);
const workerPath = path.join(__dirname, "..", "src", "ashare_f10", "web", "static-search-worker.js");
vm.runInContext(fs.readFileSync(workerPath, "utf8"), context, { filename: workerPath });

function send(type, payload = {}) {
  messages.length = 0;
  context.self.onmessage({ data: { id: 1, type, ...payload } });
  if (messages.length !== 1) throw new Error(`Expected one worker response, got ${messages.length}`);
  const message = messages[0];
  if (!message.ok) throw new Error(message.error);
  return message.result;
}

const payload = {
  metadata: { security: { security_code: "688521", secucode: "688521.SH" } },
  field_mapping: { global: {
    CASH_A: { label: "现金项目A", unit: "元" },
    CASH_B_YOY: { label: "现金项目B同比", unit: "%" },
    REVENUE: { label: "营业收入", unit: "元" },
  } },
  groups: [
    { theme: "财务", family: "CASH", records: [
      { REPORT_DATE: "2026-03-31", CASH_A: 100 },
      { REPORT_DATE: "2025-12-31", CASH_B_YOY: 20 },
    ] },
    { theme: "财务", family: "INCOME", records: [
      { REPORT_DATE: "2025-12-31", REVENUE: 300 },
    ] },
  ],
};

const loaded = send("load", { text: JSON.stringify(payload) });
if (loaded.fact_count < 3) throw new Error(`Unexpected fact count: ${loaded.fact_count}`);

const request = {
  base_query: "现金",
  base_match_type: "contains",
  base_columns: ["field_name_cn"],
  base_threshold: 60,
  search_steps: [{
    query: "同比",
    operation: "exclude",
    match_type: "contains",
    columns: ["field_name_cn"],
    threshold: 60,
    enabled: true,
  }],
  filters: [{ column: "family", operator: "in", values: ["CASH"], enabled: true }],
  sort: [{ column: "report_date", direction: "desc" }],
  page: 1,
  page_size: 20,
};
const result = send("query", { request });
if (result.total !== 1 || result.rows[0].field_key !== "CASH_A") {
  throw new Error(`Unexpected query result: ${JSON.stringify(result)}`);
}
if (result.stage_counts.length < 4) throw new Error("Missing stage counts");

const facet = send("facet", { request, column: "family", term: "", limit: 20 });
if (!facet.values.some((item) => item.value === "CASH")) {
  throw new Error(`Missing CASH facet: ${JSON.stringify(facet)}`);
}

const exported = send("export", { request, maxRows: 100 });
if (!exported.csv.includes("CASH_A") || exported.csv.includes("CASH_B_YOY")) {
  throw new Error(`Unexpected CSV export: ${exported.csv}`);
}

console.log(JSON.stringify({
  loaded,
  total: result.total,
  stageCounts: result.stage_counts,
  exportRows: exported.row_count,
}));
