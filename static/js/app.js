console.log("AJAX app.js loaded");

function esc(v) {
  return String(v ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

// eBay itemId often like: "v1|110588791102|0" -> "110588791102"
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

document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("#searchForm");
  const qEl = document.querySelector("#q");
  const limitEl = document.querySelector("#limit");
  const pageEl = document.querySelector("#page");
  const sortEl = document.querySelector("#sort");

  const table = document.querySelector("#resultsTable");
  const body = document.querySelector("#resultsBody");
  const metaLine = document.querySelector("#metaLine");
  const errorLine = document.querySelector("#errorLine");

  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    errorLine.style.display = "none";
    errorLine.textContent = "";
    body.innerHTML = "";
    table.style.display = "none";

    const params = new URLSearchParams({
      q: (qEl.value || "").trim(),
      limit: String(limitEl.value || 20),
      page: String(pageEl.value || 1),
    });

    if (sortEl && sortEl.value) params.set("sort", sortEl.value);

    try {
      const res = await fetch("/api/search?" + params.toString(), { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();
      const items = Array.isArray(data.items) ? data.items : [];

      metaLine.textContent = `Знайдено: ${data.total ?? 0}. Показано: ${items.length}`;
      if (!items.length) return;

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
        const totalStr = totalCur ? `${totalNum.toFixed(2)} ${totalCur}` : (totalNum ? totalNum.toFixed(2) : "—");

        const fullId = item.itemId ?? "";
        const niceId = shortItemId(fullId) || "—";

        const openBtn = webUrl
          ? `<a class="btn-open" href="${esc(webUrl)}" target="_blank" rel="noreferrer">
                Відкрити
             </a>`
          : "—";

        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${idx + 1}</td>

          <td>
            <strong>${esc(item.title)}</strong>
          </td>

          <td>${esc(category)}</td>
          <td>${esc(condition)}</td>
          <td>${esc(priceStr)}</td>
          <td>${esc(shipStr)}</td>
          <td><strong>${esc(totalStr)}</strong></td>
          <td>${esc(country)}</td>
          <td>${esc(seller)}</td>

          <td>
            <code class="nowrap" title="${esc(fullId)}">${esc(niceId)}</code>
          </td>

          <td>${openBtn}</td>
        `;

        body.appendChild(tr);
      });

      table.style.display = "table";
    } catch (err) {
      errorLine.textContent = "Помилка запиту (дивись консоль)";
      errorLine.style.display = "block";
      console.error(err);
    }
  });
});