function esc(v) { // escape HTML (захист від XSS + коректний HTML)
  return String(v ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function fmtNum(x, digits = 2) { // формат числа до N знаків або "-"
  if (x === null || x === undefined) return "—";
  const n = Number(x);
  if (!Number.isFinite(n)) return "—";
  return n.toFixed(digits);
}

let histChart = null; // Chart.js гістограми
let topChart = null; // Chart.js top-значеня

async function apiGet(url) { // GET -> JSON з вимкненим кешем
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

async function apiPostBlob(url, payload) { // POST JSON -> Blob (Excel)
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.blob();
}

function downloadBlob(blob, filename = "export.xlsx") { // завантаження Blob як файл
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function renderCards(cardsEl, cards) { // рендер метрик
  cardsEl.innerHTML = (cards || [])
    .map(c => `
      <div class="a-card">
        <div class="a-title">${esc(c.title)}</div>
        <div class="a-value">${esc(c.value)}</div>
      </div>
    `).join("");
  cardsEl.style.display = "flex";
}

function fillSelect(selectEl, items, placeholder) { // заповнює select опціями + placeholder
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

function fillFilterSelect(selectEl, columns) { // оновлює select фільтра, зберігаючи поточне значення
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

function renderTable(tableEl, headEl, bodyEl, columns, rows) { // рендер таблиці з columns + rows
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
      td.innerHTML = esc(r[c]); // значення клітинки
      tr.appendChild(td);
    });
    bodyEl.appendChild(tr);
  });

  tableEl.style.display = "table";
}

function buildHistogramBins(values, bins = 12) { // будує біни гістограми (labels + counts)
  const nums = (values || []).map(Number).filter(v => Number.isFinite(v));
  if (!nums.length) return { labels: [], counts: [] };

  const mn = Math.min(...nums);
  const mx = Math.max(...nums);
  if (mn === mx) return { labels: [`${mn}`], counts: [nums.length] }; // всі однакові

  const step = (mx - mn) / bins;
  const counts = Array(bins).fill(0);

  nums.forEach(v => { // рахуємо, в який бін попадає число
    let idx = Math.floor((v - mn) / step);
    if (idx >= bins) idx = bins - 1;
    if (idx < 0) idx = 0;
    counts[idx] += 1;
  });

  const labels = counts.map((_, i) => { // підписи бінів "a-b"
    const a = mn + i * step;
    const b = mn + (i + 1) * step;
    return `${a.toFixed(0)}-${b.toFixed(0)}`;
  });

  return { labels, counts };
}

function renderCharts(chartsBox, histCanvas, topCanvas, histData, topData) { // малює 2 графіки (hist + top)
  chartsBox.style.display = "grid";

  if (window.Chart && histCanvas) { // гістограма
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

  if (window.Chart && topCanvas) { // top-значення
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

function isMissingToken(s) { // перевірка "порожніх" маркерів (NA/null/—/...)
  const x = String(s ?? "").trim().toLowerCase();
  return x === "" || x === "na" || x === "n/a" || x === "nan" || x === "null" || x === "none" || x === "-" || x === "--" || x === "—";
}

function tryParseNumber(v) { // парсить число з рядка (зчищає пробіли, коми, символи)
  if (v === null || v === undefined) return null;
  if (isMissingToken(v)) return null;

  let s = String(v).trim();
  s = s.replaceAll(",", "").replaceAll(" ", ""); // прибрати коми/пробіли
  s = s.replace(/[^0-9.\-]/g, ""); // лишити цифри/./-
  if (!s || s === "-" || s === "." || s === "-.") return null;

  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

// state
let dsColumns = []; // всі колонки таблиці
let dsRowsRaw = []; // рядки, отримані з API (без фільтра)
let dsRowsShown = []; // рядки після фільтра
let currentPage = 1; // поточна сторінка
let pageSize = 50; // рядків на сторінку
let currentOffset = 0; // offset для API

let datasetName = ""; // назва датасету
let modeText = ""; // текст режиму (default/upload)

let numericColsSet = new Set(); // множина numeric колонок (для range-фільтра)

let lastColStats = null; // останні stats вибраної numeric колонки
let lastHist = { labels: [], counts: [] }; // остання гістограма
let lastTop = { labels: [], counts: [] };  // останній top
let lastNumericCol = ""; // остання обрана numeric колонка
let lastCatCol = ""; // остання обрана categorical колонка

// filter UI
function setFilterMode(isNumeric) { // перемикає UI фільтра: текст або min/max
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

function onFilterColumnChange() { // викликається при зміні колонки фільтра
  const col = document.getElementById("filterCol").value || "";
  const isNumeric = col && numericColsSet.has(col);
  setFilterMode(Boolean(isNumeric));
}

function applyFilterToCurrentPage() { // застосовує фільтр до dsRowsRaw і пише в dsRowsShown
  const filterCol = document.getElementById("filterCol").value || "";

  const isNumeric = filterCol && numericColsSet.has(filterCol); // чи numeric колонка

  if (isNumeric) { // range-фільтр
    const minRaw = document.getElementById("filterMin").value;
    const maxRaw = document.getElementById("filterMax").value;

    const minV = tryParseNumber(minRaw);
    const maxV = tryParseNumber(maxRaw);

    if (minV === null && maxV === null) { // якщо нічого не задано
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

  // contains-фільтр (текстовий)
  const filterText = (document.getElementById("filterText").value || "").trim().toLowerCase();
  if (!filterText) {
    dsRowsShown = dsRowsRaw.slice();
    return;
  }

  const colsToCheck = filterCol ? [filterCol] : dsColumns; // або одна колонка, або всі

  dsRowsShown = dsRowsRaw.filter((row) => {
    for (const c of colsToCheck) {
      const v = String(row?.[c] ?? "").toLowerCase();
      if (v.includes(filterText)) return true;
    }
    return false;
  });
}

async function loadPreviewPage() { // завантажує сторінку таблиці preview (offset/limit)
  const table = document.getElementById("dsTable");
  const head = document.getElementById("dsHead");
  const body = document.getElementById("dsBody");
  const err = document.getElementById("dsErr");
  const pageInfo = document.getElementById("pageInfo");
  const filterColSel = document.getElementById("filterCol");

  err.style.display = "none";
  err.textContent = "";

  pageSize = Math.max(10, Math.min(500, Number(document.getElementById("pageSize").value || 50))); // clamp 10..500
  currentPage = Math.max(1, Number(document.getElementById("pageNum").value || 1)); // min 1
  currentOffset = (currentPage - 1) * pageSize; // offset

  try {
    const preview = await apiGet(`/api/dataset/preview?offset=${currentOffset}&limit=${pageSize}`);

    dsColumns = preview.columns || [];
    dsRowsRaw = preview.rows || [];

    fillFilterSelect(filterColSel, dsColumns); // оновити select колонок

    onFilterColumnChange(); // відновити правильний режим фільтра
    applyFilterToCurrentPage(); // застосувати фільтр до поточної сторінки
    renderTable(table, head, body, dsColumns, dsRowsShown); // намалювати таблицю

    pageInfo.textContent =
      `Сторінка: ${currentPage} | offset: ${currentOffset} | rows on page: ${dsRowsRaw.length} | показано після фільтра: ${dsRowsShown.length}`;

  } catch (e) {
    err.textContent = "Помилка завантаження таблиці. Перевір консоль.";
    err.style.display = "block";
    console.error(e);
  }
}

// summary
async function refreshAll() { // повне оновлення: summary + таблиця
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

    numericColsSet = new Set(summary.numeric_columns || []); // кеш numeric колонок для range-фільтра

    dsNameEl.value = datasetName; // показати назву файлу
    dsModeEl.textContent = modeText; // показати режим (default/upload)

    dsMeta.textContent = `Рядків (скан): ${summary.row_count}, Колонок: ${(summary.columns||[]).length} | numeric threshold: ${(summary.numeric_threshold * 100).toFixed(0)}%`;

    renderCards(dsCards, [ // карточки загальної статистики
      { title: "Рядків (скан)", value: summary.row_count ?? "—" },
      { title: "Колонок", value: (summary.columns || []).length },
      { title: "Числових колонок", value: (summary.numeric_columns || []).length },
      { title: "Категоріальних колонок", value: (summary.categorical_columns || []).length },
    ]);

    fillSelect(numColSel, summary.numeric_columns || [], "— обери колонку —"); // select numeric
    fillSelect(catColSel, summary.categorical_columns || [], "— обери колонку —"); // select categorical

    chartsBox.style.display = "none"; // графіки до вибору

    onFilterColumnChange(); // виставити режим фільтра
    await loadPreviewPage(); // завантажити таблицю preview

  } catch (e) {
    err.textContent = "Помилка завантаження датасету. Перевір консоль.";
    err.style.display = "block";
    console.error(e);
  }
}

async function updateChartsAndStats() { // оновлює графіки + cards для вибраних колонок
  const chartsBox = document.getElementById("dsCharts");
  const histCanvas = document.getElementById("histChart");
  const topCanvas = document.getElementById("topChart");

  const numCol = document.getElementById("numCol").value; // вибрана numeric колонка
  const catCol = document.getElementById("catCol").value; // вибрана categorical колонка

  const dsMeta = document.getElementById("dsMeta");
  const dsCards = document.getElementById("dsCards");

  lastNumericCol = numCol || "";
  lastCatCol = catCol || "";
  lastColStats = null;
  lastHist = { labels: [], counts: [] };
  lastTop = { labels: [], counts: [] };

  if (!numCol && !catCol) { // нічого не обрано - сховати графіки
    chartsBox.style.display = "none";
    return;
  }

  if (numCol) { // якщо є numeric колонка -> stats + histogram
    const cs = await apiGet(`/api/dataset/colstats?name=${encodeURIComponent(numCol)}`);
    lastColStats = cs;
    const st = cs.stats || {};

    dsMeta.textContent =
      `Колонка: ${numCol} | parsed: ${cs.parsed_count} | missing: ${cs.missing_count} | unparsable: ${cs.unparsable_count} | parse ratio: ${(cs.parse_ratio * 100).toFixed(1)}%`;

    renderCards(dsCards, [ // статистика numeric колонки
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

    const histValues = await apiGet(`/api/dataset/column?name=${encodeURIComponent(numCol)}&limit=20000`); // значення для гістограми
    const histData = buildHistogramBins(histValues.values || [], 12);
    lastHist = histData;

    let topData = { labels: [], counts: [] };
    if (catCol) { // якщо ще й categorical - top values
      const top = await apiGet(`/api/dataset/top?name=${encodeURIComponent(catCol)}&limit=10`);
      topData = { labels: top.labels || [], counts: top.counts || [] };
      lastTop = topData;
    }

    renderCharts(chartsBox, histCanvas, topCanvas, histData, topData);
    return;
  }

  if (catCol) { // якщо тільки categorical (без numeric) - тільки top графік
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

function getFilterState() { // зчитує поточний стан фільтра з UI
  const filter_col = document.getElementById("filterCol").value || "";
  const isNumeric = filter_col && numericColsSet.has(filter_col);

  if (isNumeric) { // range-mode
    return {
      filter_col,
      filter_text: "",
      filter_min: document.getElementById("filterMin").value || "",
      filter_max: document.getElementById("filterMax").value || "",
      filter_mode: "range",
    };
  }

  // contains-mode
  return {
    filter_col,
    filter_text: document.getElementById("filterText").value || "",
    filter_min: "",
    filter_max: "",
    filter_mode: "contains",
  };
}

async function exportFiltered() { // експорт таблиці (поточна сторінка + фільтр) в Excel
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

async function exportReport() { // експорт звіту (таблиця + stats + графіки) в Excel
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

document.addEventListener("DOMContentLoaded", () => { // ініціалізація після завантаження DOM
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

  reloadBtn.addEventListener("click", refreshAll); // ручне оновлення

  numCol.addEventListener("change", updateChartsAndStats); // оновити stats при зміні numeric
  catCol.addEventListener("change", updateChartsAndStats); // оновити top при зміні categorical

  filterCol.addEventListener("change", onFilterColumnChange); // перемикнути режим фільтра

  // pagination: попередня сторінка
  prevBtn.addEventListener("click", async () => {
    const pageNum = document.getElementById("pageNum");
    pageNum.value = String(Math.max(1, Number(pageNum.value || 1) - 1));
    await loadPreviewPage();
  });

  // pagination: наступна сторінка
  nextBtn.addEventListener("click", async () => {
    const pageNum = document.getElementById("pageNum");
    pageNum.value = String(Math.max(1, Number(pageNum.value || 1) + 1));
    await loadPreviewPage();
  });

  goBtn.addEventListener("click", loadPreviewPage); // перейти на сторінку

  // застосувати фільтр
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

  // очистити фільтр
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

  // export filtered
  exportFilteredBtn.addEventListener("click", async () => {
    try { await exportFiltered(); } catch (e) { console.error(e); alert("Export failed. See console."); }
  });

  // export report
  exportReportBtn.addEventListener("click", async () => {
    try {
      if (!lastNumericCol) { // якщо не вибрано numeric колонки
        const ok = confirm("Для звіту з гістограмою бажано обрати числову колонку. Експортувати все одно?");
        if (!ok) return;
      }
      await exportReport();
    } catch (e) {
      console.error(e);
      alert("Report export failed. See console.");
    }
  });

  // CSV
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

    // reset UI після аплоаду
    document.getElementById("pageNum").value = "1";
    document.getElementById("filterCol").value = "";
    document.getElementById("filterText").value = "";
    document.getElementById("filterMin").value = "";
    document.getElementById("filterMax").value = "";
    onFilterColumnChange();

    await refreshAll(); // підтягнути новий датасет
  });

  refreshAll(); // стартове завантаження
});