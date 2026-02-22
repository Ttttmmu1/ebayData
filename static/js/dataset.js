function esc(v) {
  return String(v ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function fmtNum(x, digits = 2) {
  if (x === null || x === undefined) return "—";
  const n = Number(x);
  if (!Number.isFinite(n)) return "—";
  return n.toFixed(digits);
}

let histChart = null;
let topChart = null;

async function apiGet(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

async function apiPostBlob(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.blob();
}

function downloadBlob(blob, filename = "export.xlsx") {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function renderCards(cardsEl, cards) {
  cardsEl.innerHTML = (cards || [])
    .map(c => `
      <div class="a-card">
        <div class="a-title">${esc(c.title)}</div>
        <div class="a-value">${esc(c.value)}</div>
      </div>
    `).join("");
  cardsEl.style.display = "flex";
}

function fillSelect(selectEl, items, placeholder) {
  selectEl.innerHTML = "";
  const opt0 = document.createElement("option");
  opt0.value = "";
  opt0.textContent = placeholder;
  selectEl.appendChild(opt0);

  (items || []).forEach((x) => {
    const opt = document.createElement("option");
    opt.value = x;
    opt.textContent = x;
    selectEl.appendChild(opt);
  });
}

function fillFilterSelect(selectEl, columns) {
  const current = selectEl.value || "";
  selectEl.innerHTML = `<option value="">(всі колонки)</option>`;
  (columns || []).forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c;
    opt.textContent = c;
    selectEl.appendChild(opt);
  });
  selectEl.value = current;
}

function renderTable(tableEl, headEl, bodyEl, columns, rows) {
  headEl.innerHTML = "";
  (columns || []).forEach((c) => {
    const th = document.createElement("th");
    th.textContent = c;
    headEl.appendChild(th);
  });

  bodyEl.innerHTML = "";
  (rows || []).forEach((r) => {
    const tr = document.createElement("tr");
    (columns || []).forEach((c) => {
      const td = document.createElement("td");
      td.innerHTML = esc(r[c]);
      tr.appendChild(td);
    });
    bodyEl.appendChild(tr);
  });

  tableEl.style.display = "table";
}

function buildHistogramBins(values, bins = 12) {
  const nums = (values || []).map(Number).filter(v => Number.isFinite(v));
  if (!nums.length) return { labels: [], counts: [] };

  const mn = Math.min(...nums);
  const mx = Math.max(...nums);
  if (mn === mx) return { labels: [`${mn}`], counts: [nums.length] };

  const step = (mx - mn) / bins;
  const counts = Array(bins).fill(0);

  nums.forEach(v => {
    let idx = Math.floor((v - mn) / step);
    if (idx >= bins) idx = bins - 1;
    if (idx < 0) idx = 0;
    counts[idx] += 1;
  });

  const labels = counts.map((_, i) => {
    const a = mn + i * step;
    const b = mn + (i + 1) * step;
    return `${a.toFixed(0)}-${b.toFixed(0)}`;
  });

  return { labels, counts };
}

function renderCharts(chartsBox, histCanvas, topCanvas, histData, topData) {
  chartsBox.style.display = "grid";

  if (window.Chart && histCanvas) {
    if (histChart) histChart.destroy();
    histChart = new Chart(histCanvas, {
      type: "bar",
      data: {
        labels: histData.labels,
        datasets: [{ label: "Count", data: histData.counts }]
      },
      options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
    });
  }

  if (window.Chart && topCanvas) {
    if (topChart) topChart.destroy();
    topChart = new Chart(topCanvas, {
      type: "bar",
      data: {
        labels: topData.labels,
        datasets: [{ label: "Count", data: topData.counts }]
      },
      options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
    });
  }
}

/* ---------- Numeric parsing for range filter (same idea as backend) ---------- */
function isMissingToken(s) {
  const x = String(s ?? "").trim().toLowerCase();
  return x === "" || x === "na" || x === "n/a" || x === "nan" || x === "null" || x === "none" || x === "-" || x === "--" || x === "—";
}

function tryParseNumber(v) {
  if (v === null || v === undefined) return null;
  if (isMissingToken(v)) return null;

  let s = String(v).trim();
  // remove commas/spaces
  s = s.replaceAll(",", "").replaceAll(" ", "");
  // keep only digits/dot/minus
  s = s.replace(/[^0-9.\-]/g, "");
  if (!s || s === "-" || s === "." || s === "-.") return null;

  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

// -------------------- state --------------------
let dsColumns = [];
let dsRowsRaw = [];
let dsRowsShown = [];
let currentPage = 1;
let pageSize = 50;
let currentOffset = 0;

let datasetName = "";
let modeText = "";

let numericColsSet = new Set();   // ✅ for range filter switching

let lastColStats = null;
let lastHist = { labels: [], counts: [] };
let lastTop = { labels: [], counts: [] };
let lastNumericCol = "";
let lastCatCol = "";

// -------------------- filter UI mode switching --------------------
function setFilterMode(isNumeric) {
  const textBox = document.getElementById("filterTextBox");
  const minBox = document.getElementById("filterMinBox");
  const maxBox = document.getElementById("filterMaxBox");

  if (isNumeric) {
    textBox.style.display = "none";
    minBox.style.display = "";
    maxBox.style.display = "";
  } else {
    textBox.style.display = "";
    minBox.style.display = "none";
    maxBox.style.display = "none";
  }
}

function onFilterColumnChange() {
  const col = document.getElementById("filterCol").value || "";
  const isNumeric = col && numericColsSet.has(col);
  setFilterMode(Boolean(isNumeric));
}

function applyFilterToCurrentPage() {
  const filterCol = document.getElementById("filterCol").value || "";

  // numeric?
  const isNumeric = filterCol && numericColsSet.has(filterCol);

  if (isNumeric) {
    const minRaw = document.getElementById("filterMin").value;
    const maxRaw = document.getElementById("filterMax").value;

    const minV = tryParseNumber(minRaw);
    const maxV = tryParseNumber(maxRaw);

    // якщо обидва пусті -> без фільтра
    if (minV === null && maxV === null) {
      dsRowsShown = dsRowsRaw.slice();
      return;
    }

    dsRowsShown = dsRowsRaw.filter((row) => {
      const val = tryParseNumber(row?.[filterCol]);
      if (val === null) return false;

      if (minV !== null && val < minV) return false;
      if (maxV !== null && val > maxV) return false;
      return true;
    });
    return;
  }

  // text contains (existing)
  const filterText = (document.getElementById("filterText").value || "").trim().toLowerCase();
  if (!filterText) {
    dsRowsShown = dsRowsRaw.slice();
    return;
  }

  const colsToCheck = filterCol ? [filterCol] : dsColumns;

  dsRowsShown = dsRowsRaw.filter((row) => {
    for (const c of colsToCheck) {
      const v = String(row?.[c] ?? "").toLowerCase();
      if (v.includes(filterText)) return true;
    }
    return false;
  });
}

async function loadPreviewPage() {
  const table = document.getElementById("dsTable");
  const head = document.getElementById("dsHead");
  const body = document.getElementById("dsBody");
  const err = document.getElementById("dsErr");
  const pageInfo = document.getElementById("pageInfo");
  const filterColSel = document.getElementById("filterCol");

  err.style.display = "none";
  err.textContent = "";

  pageSize = Math.max(10, Math.min(500, Number(document.getElementById("pageSize").value || 50)));
  currentPage = Math.max(1, Number(document.getElementById("pageNum").value || 1));
  currentOffset = (currentPage - 1) * pageSize;

  try {
    const preview = await apiGet(`/api/dataset/preview?offset=${currentOffset}&limit=${pageSize}`);

    dsColumns = preview.columns || [];
    dsRowsRaw = preview.rows || [];

    fillFilterSelect(filterColSel, dsColumns);

    // keep mode correct after refresh
    onFilterColumnChange();

    applyFilterToCurrentPage();
    renderTable(table, head, body, dsColumns, dsRowsShown);

    pageInfo.textContent =
      `Сторінка: ${currentPage} | offset: ${currentOffset} | rows on page: ${dsRowsRaw.length} | показано після фільтра: ${dsRowsShown.length}`;

  } catch (e) {
    err.textContent = "Помилка завантаження таблиці. Перевір консоль.";
    err.style.display = "block";
    console.error(e);
  }
}

// -------------------- summary + charts/stats --------------------
async function refreshAll() {
  const dsNameEl = document.getElementById("dsName");
  const dsModeEl = document.getElementById("dsMode");
  const dsMeta = document.getElementById("dsMeta");
  const dsCards = document.getElementById("dsCards");

  const numColSel = document.getElementById("numCol");
  const catColSel = document.getElementById("catCol");

  const err = document.getElementById("dsErr");
  const chartsBox = document.getElementById("dsCharts");

  err.style.display = "none";
  err.textContent = "";

  try {
    const summary = await apiGet("/api/dataset/summary");
    datasetName = summary.dataset_name || "dataset.csv";
    modeText = summary.mode_text || "";

    // ✅ cache numeric columns set for range filter
    numericColsSet = new Set(summary.numeric_columns || []);

    dsNameEl.value = datasetName;
    dsModeEl.textContent = modeText;

    dsMeta.textContent = `Рядків (скан): ${summary.row_count}, Колонок: ${(summary.columns||[]).length} | numeric threshold: ${(summary.numeric_threshold * 100).toFixed(0)}%`;

    renderCards(dsCards, [
      { title: "Рядків (скан)", value: summary.row_count ?? "—" },
      { title: "Колонок", value: (summary.columns || []).length },
      { title: "Числових колонок", value: (summary.numeric_columns || []).length },
      { title: "Категоріальних колонок", value: (summary.categorical_columns || []).length },
    ]);

    fillSelect(numColSel, summary.numeric_columns || [], "— вибери колонку —");
    fillSelect(catColSel, summary.categorical_columns || [], "— вибери колонку —");

    chartsBox.style.display = "none";

    // ensure filter mode correct (default: text)
    onFilterColumnChange();

    await loadPreviewPage();

  } catch (e) {
    err.textContent = "Помилка завантаження датасету. Перевір консоль.";
    err.style.display = "block";
    console.error(e);
  }
}

async function updateChartsAndStats() {
  const chartsBox = document.getElementById("dsCharts");
  const histCanvas = document.getElementById("histChart");
  const topCanvas = document.getElementById("topChart");

  const numCol = document.getElementById("numCol").value;
  const catCol = document.getElementById("catCol").value;

  const dsMeta = document.getElementById("dsMeta");
  const dsCards = document.getElementById("dsCards");

  lastNumericCol = numCol || "";
  lastCatCol = catCol || "";
  lastColStats = null;
  lastHist = { labels: [], counts: [] };
  lastTop = { labels: [], counts: [] };

  if (!numCol && !catCol) {
    chartsBox.style.display = "none";
    return;
  }

  if (numCol) {
    const cs = await apiGet(`/api/dataset/colstats?name=${encodeURIComponent(numCol)}`);
    lastColStats = cs;
    const st = cs.stats || {};

    dsMeta.textContent =
      `Колонка: ${numCol} | parsed: ${cs.parsed_count} | missing: ${cs.missing_count} | unparsable: ${cs.unparsable_count} | parse ratio: ${(cs.parse_ratio * 100).toFixed(1)}%`;

    renderCards(dsCards, [
      { title: "Колонка", value: numCol },
      { title: "avg / median", value: `${fmtNum(st.avg)} / ${fmtNum(st.median)}` },
      { title: "min / max", value: `${fmtNum(st.min)} / ${fmtNum(st.max)}` },
      { title: "std", value: `${fmtNum(st.std)}` },
      { title: "Q1 / Q3", value: `${fmtNum(st.q1)} / ${fmtNum(st.q3)}` },
      { title: "IQR", value: `${fmtNum(st.iqr)}` },
      { title: "Parsed", value: String(cs.parsed_count ?? "—") },
      { title: "Missing", value: String(cs.missing_count ?? "—") },
      { title: "Unparsable", value: String(cs.unparsable_count ?? "—") },
    ]);

    const histValues = await apiGet(`/api/dataset/column?name=${encodeURIComponent(numCol)}&limit=20000`);
    const histData = buildHistogramBins(histValues.values || [], 12);
    lastHist = histData;

    let topData = { labels: [], counts: [] };
    if (catCol) {
      const top = await apiGet(`/api/dataset/top?name=${encodeURIComponent(catCol)}&limit=10`);
      topData = { labels: top.labels || [], counts: top.counts || [] };
      lastTop = topData;
    }

    renderCharts(chartsBox, histCanvas, topCanvas, histData, topData);
    return;
  }

  if (catCol) {
    const top = await apiGet(`/api/dataset/top?name=${encodeURIComponent(catCol)}&limit=10`);
    const topData = { labels: top.labels || [], counts: top.counts || [] };
    lastTop = topData;

    renderCharts(
      chartsBox,
      histCanvas,
      topCanvas,
      { labels: [], counts: [] },
      topData
    );
  }
}

// -------------------- Export handlers --------------------
function getFilterState() {
  const filter_col = document.getElementById("filterCol").value || "";
  const isNumeric = filter_col && numericColsSet.has(filter_col);

  if (isNumeric) {
    return {
      filter_col,
      filter_text: "",
      filter_min: document.getElementById("filterMin").value || "",
      filter_max: document.getElementById("filterMax").value || "",
      filter_mode: "range",
    };
  }

  return {
    filter_col,
    filter_text: document.getElementById("filterText").value || "",
    filter_min: "",
    filter_max: "",
    filter_mode: "contains",
  };
}

async function exportFiltered() {
  const fs = getFilterState();

  const payload = {
    dataset_name: datasetName || "dataset.csv",
    mode_text: modeText || "",
    columns: dsColumns || [],
    rows: dsRowsShown || [],
    filter_col: fs.filter_col,
    filter_text:
      fs.filter_mode === "range"
        ? `range: [${fs.filter_min || "-inf"}, ${fs.filter_max || "+inf"}]`
        : fs.filter_text,
  };

  const blob = await apiPostBlob("/api/dataset/export_filtered", payload);
  downloadBlob(blob, "dataset_filtered.xlsx");
}

async function exportReport() {
  const fs = getFilterState();

  const payload = {
    dataset_name: datasetName || "dataset.csv",
    mode_text: modeText || "",
    columns: dsColumns || [],
    rows: dsRowsShown || [],
    filter_col: fs.filter_col,
    filter_text:
      fs.filter_mode === "range"
        ? `range: [${fs.filter_min || "-inf"}, ${fs.filter_max || "+inf"}]`
        : fs.filter_text,
    numeric_col: lastNumericCol || "",
    colstats: lastColStats || {},
    hist_labels: (lastHist && lastHist.labels) ? lastHist.labels : [],
    hist_counts: (lastHist && lastHist.counts) ? lastHist.counts : [],
    cat_col: lastCatCol || "",
    top_labels: (lastTop && lastTop.labels) ? lastTop.labels : [],
    top_counts: (lastTop && lastTop.counts) ? lastTop.counts : [],
  };

  const blob = await apiPostBlob("/api/dataset/export_report", payload);
  downloadBlob(blob, "dataset_report.xlsx");
}

document.addEventListener("DOMContentLoaded", () => {
  const reloadBtn = document.getElementById("reloadBtn");
  const upload = document.getElementById("uploadFile");
  const numCol = document.getElementById("numCol");
  const catCol = document.getElementById("catCol");

  const prevBtn = document.getElementById("prevBtn");
  const nextBtn = document.getElementById("nextBtn");
  const goBtn = document.getElementById("goBtn");

  const filterCol = document.getElementById("filterCol");
  const applyFilterBtn = document.getElementById("applyFilterBtn");
  const clearFilterBtn = document.getElementById("clearFilterBtn");

  const exportFilteredBtn = document.getElementById("exportFilteredBtn");
  const exportReportBtn = document.getElementById("exportReportBtn");

  reloadBtn.addEventListener("click", refreshAll);

  numCol.addEventListener("change", updateChartsAndStats);
  catCol.addEventListener("change", updateChartsAndStats);

  // switch filter UI when column changes
  filterCol.addEventListener("change", onFilterColumnChange);

  // pagination
  prevBtn.addEventListener("click", async () => {
    const pageNum = document.getElementById("pageNum");
    pageNum.value = String(Math.max(1, Number(pageNum.value || 1) - 1));
    await loadPreviewPage();
  });

  nextBtn.addEventListener("click", async () => {
    const pageNum = document.getElementById("pageNum");
    pageNum.value = String(Math.max(1, Number(pageNum.value || 1) + 1));
    await loadPreviewPage();
  });

  goBtn.addEventListener("click", loadPreviewPage);

  // filtering apply
  applyFilterBtn.addEventListener("click", () => {
    const table = document.getElementById("dsTable");
    const head = document.getElementById("dsHead");
    const body = document.getElementById("dsBody");
    const pageInfo = document.getElementById("pageInfo");

    applyFilterToCurrentPage();
    renderTable(table, head, body, dsColumns, dsRowsShown);

    pageInfo.textContent =
      `Сторінка: ${currentPage} | offset: ${currentOffset} | rows on page: ${dsRowsRaw.length} | показано після фільтра: ${dsRowsShown.length}`;
  });

  clearFilterBtn.addEventListener("click", () => {
    document.getElementById("filterCol").value = "";
    document.getElementById("filterText").value = "";
    document.getElementById("filterMin").value = "";
    document.getElementById("filterMax").value = "";
    onFilterColumnChange();

    const table = document.getElementById("dsTable");
    const head = document.getElementById("dsHead");
    const body = document.getElementById("dsBody");
    const pageInfo = document.getElementById("pageInfo");

    dsRowsShown = dsRowsRaw.slice();
    renderTable(table, head, body, dsColumns, dsRowsShown);

    pageInfo.textContent =
      `Сторінка: ${currentPage} | offset: ${currentOffset} | rows on page: ${dsRowsRaw.length} | показано після фільтра: ${dsRowsShown.length}`;
  });

  // export
  exportFilteredBtn.addEventListener("click", async () => {
    try { await exportFiltered(); } catch (e) { console.error(e); alert("Export failed. See console."); }
  });

  exportReportBtn.addEventListener("click", async () => {
    try {
      if (!lastNumericCol) {
        const ok = confirm("Для звіту з гістограмою бажано вибрати числову колонку. Експортувати все одно?");
        if (!ok) return;
      }
      await exportReport();
    } catch (e) {
      console.error(e);
      alert("Report export failed. See console.");
    }
  });

  // upload
  upload.addEventListener("change", async () => {
    const f = upload.files?.[0];
    if (!f) return;

    const fd = new FormData();
    fd.append("file", f);

    const res = await fetch("/api/dataset/upload", { method: "POST", body: fd });
    if (!res.ok) {
      alert("Upload error: HTTP " + res.status);
      return;
    }

    document.getElementById("pageNum").value = "1";
    document.getElementById("filterCol").value = "";
    document.getElementById("filterText").value = "";
    document.getElementById("filterMin").value = "";
    document.getElementById("filterMax").value = "";
    onFilterColumnChange();

    await refreshAll();
  });

  refreshAll();
});