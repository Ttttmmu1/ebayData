console.log("AJAX app.js loaded");

function esc(v) {
  return String(v ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function shortItemId(itemId) {
  if (!itemId) return "";
  const s = String(itemId);
  if (s.includes("|")) {
    const parts = s.split("|");
    return parts[1] ?? s;
  }
  return s;
}

function money(value, currency) {
  const v = value ?? "";
  const c = currency ?? "";
  const s = `${v} ${c}`.trim();
  return s || "—";
}

function toNumber(x) {
  const n = Number(x);
  return Number.isFinite(n) ? n : 0;
}

function fmtNum(x, digits = 2) {
  if (x === null || x === undefined) return "—";
  const n = Number(x);
  if (!Number.isFinite(n)) return "—";
  return n.toFixed(digits);
}

function renderAnalytics(boxEl, payload) {
  const analytics = payload?.analytics || {};
  const cur = analytics.currency_most_common || "";

  const price = analytics.price || {};
  const ship = analytics.shipping || {};
  const total = analytics.total || {};
  const seller = analytics.seller_feedback || {};

  const cards = [
    { title: "Валюта (найчастіша)", value: cur || "—" },
    { title: "Ціна avg / median", value: `${fmtNum(price.avg)} / ${fmtNum(price.median)} ${cur}`.trim() },
    { title: "Доставка avg / median", value: `${fmtNum(ship.avg)} / ${fmtNum(ship.median)} ${cur}`.trim() },
    { title: "Total avg / median", value: `${fmtNum(total.avg)} / ${fmtNum(total.median)} ${cur}`.trim() },
    { title: "Ціна min / max", value: `${fmtNum(price.min)} / ${fmtNum(price.max)} ${cur}`.trim() },
    { title: "Seller feedback avg", value: fmtNum(seller.avg, 0) },
  ];

  boxEl.innerHTML = cards
    .map(
      (c) => `
      <div class="a-card">
        <div class="a-title">${esc(c.title)}</div>
        <div class="a-value">${esc(c.value)}</div>
      </div>`
    )
    .join("");

  boxEl.style.display = "flex";
}

document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("#searchForm");
  const qEl = document.querySelector("#q");
  const limitEl = document.querySelector("#limit");
  const pageEl = document.querySelector("#page");
  const sortEl = document.querySelector("#sort");

  const exportBtn = document.querySelector("#exportBtn");
  const analyticsBox = document.querySelector("#analyticsBox");

  const table = document.querySelector("#resultsTable");
  const body = document.querySelector("#resultsBody");
  const metaLine = document.querySelector("#metaLine");
  const errorLine = document.querySelector("#errorLine");

  const loadingBox = document.querySelector("#loadingBox");
  const idleAnim = document.querySelector("#idleAnim");

  let lastParams = null;
  let hasSearched = false;

  if (!form) return;

  function buildParams() {
    const params = new URLSearchParams({
      q: (qEl.value || "").trim(),
      limit: String(limitEl.value || 20),
      page: String(pageEl.value || 1),
    });
    if (sortEl && sortEl.value) params.set("sort", sortEl.value);
    return params;
  }

  function showLoading() {
    if (loadingBox) loadingBox.style.display = "block";
  }

  function hideLoading() {
    if (loadingBox) loadingBox.style.display = "none";
  }

  function hideIdleAnimForever() {
    if (!idleAnim) return;
    idleAnim.style.display = "none";
  }

  async function loadAnalytics(params) {
    if (!analyticsBox) return;
    analyticsBox.style.display = "none";
    analyticsBox.innerHTML = "";
    try {
      const res = await fetch("/api/analytics?" + params.toString(), { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      renderAnalytics(analyticsBox, data);
    } catch (e) {
      console.warn("Analytics failed:", e);
      analyticsBox.style.display = "none";
    }
  }

  if (exportBtn) {
    exportBtn.addEventListener("click", () => {
      if (!lastParams) return;
      const url = "/api/export?" + lastParams.toString();
      window.location.href = url;
    });
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    // ✅ перший пошук — прибираємо красиву idle-анімацію
    if (!hasSearched) {
      hasSearched = true;
      hideIdleAnimForever();
    }

    errorLine.style.display = "none";
    errorLine.textContent = "";
    body.innerHTML = "";
    table.style.display = "none";

    if (analyticsBox) {
      analyticsBox.style.display = "none";
      analyticsBox.innerHTML = "";
    }

    if (exportBtn) exportBtn.disabled = true;

    const params = buildParams();
    showLoading();

    try {
      const res = await fetch("/api/search?" + params.toString(), { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();
      const items = Array.isArray(data.items) ? data.items : [];

      metaLine.textContent = `Знайдено: ${data.total ?? 0}. Показано: ${items.length}`;

      if (!items.length) {
        hideLoading();
        return;
      }

      items.forEach((item, idx) => {
        const title = item.title ?? "—";
        const webUrl = item.web_url ?? "";
        const category = item.category ?? "—";
        const condition = item.condition ?? "—";
        const country = item.location_country ?? "—";
        const seller = item.seller_feedback ?? "—";

        const priceStr = money(item.price_value, item.price_currency);
        const shipStr = (item.shipping_value != null)
          ? money(item.shipping_value, item.shipping_currency)
          : "—";

        const totalNum = toNumber(item.price_value) + toNumber(item.shipping_value);
        const totalCur = item.price_currency || item.shipping_currency || "";
        const totalStr = totalCur
          ? `${totalNum.toFixed(2)} ${totalCur}`
          : (totalNum ? totalNum.toFixed(2) : "—");

        const fullId = item.itemId ?? "";
        const niceId = shortItemId(fullId) || "—";

        const openBtn = webUrl
          ? `<a class="btn-open" href="${esc(webUrl)}" target="_blank" rel="noreferrer">Відкрити</a>`
          : "—";

        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${idx + 1}</td>
          <td><strong>${esc(title)}</strong></td>
          <td>${esc(category)}</td>
          <td>${esc(condition)}</td>
          <td>${esc(priceStr)}</td>
          <td>${esc(shipStr)}</td>
          <td><strong>${esc(totalStr)}</strong></td>
          <td>${esc(country)}</td>
          <td>${esc(seller)}</td>
          <td><code class="nowrap" title="${esc(fullId)}">${esc(niceId)}</code></td>
          <td>${openBtn}</td>
        `;
        body.appendChild(tr);
      });

      table.style.display = "table";

      lastParams = params;
      if (exportBtn) exportBtn.disabled = false;

      hideLoading();
      await loadAnalytics(params);

    } catch (err) {
      hideLoading();
      errorLine.textContent = "Помилка запиту (дивись консоль)";
      errorLine.style.display = "block";
      console.error(err);
    }
  });
});