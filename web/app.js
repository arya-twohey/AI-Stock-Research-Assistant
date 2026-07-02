const state = {
  preview: null,
  research: null,
};

const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 4 });

function $(id) {
  return document.getElementById(id);
}

function formatMoney(value) {
  return value === null || value === undefined || Number.isNaN(Number(value)) ? "--" : money.format(Number(value));
}

function formatNumber(value) {
  return value === null || value === undefined || Number.isNaN(Number(value)) ? "--" : number.format(Number(value));
}

function toast(message) {
  const node = $("toast");
  node.textContent = message;
  node.classList.add("show");
  window.setTimeout(() => node.classList.remove("show"), 2600);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok || payload.error) {
    throw new Error(payload.error || "Request failed");
  }
  return payload;
}

function statusLabel(value) {
  return String(value || "").replace(/^[^.]+\./, "");
}

function rowsOrEmpty(items, columns, emptyText) {
  if (!items.length) {
    return `<tr><td colspan="${columns}" class="empty">${emptyText}</td></tr>`;
  }
  return "";
}

async function loadDashboard() {
  const [account, positions, orders] = await Promise.all([
    api("/api/account"),
    api("/api/positions"),
    api("/api/orders?status=all&limit=8"),
  ]);

  $("cash").textContent = formatMoney(account.cash);
  $("buyingPower").textContent = formatMoney(account.buyingPower);
  $("portfolioValue").textContent = formatMoney(account.portfolioValue);
  $("accountStatus").textContent = statusLabel(account.status);
  $("marketStatus").textContent = account.marketOpen
    ? `Market open until ${new Date(account.nextClose).toLocaleString()}`
    : `Market closed · opens ${new Date(account.nextOpen).toLocaleString()}`;

  $("positionsBody").innerHTML =
    rowsOrEmpty(positions, 4, "No open positions.") +
    positions
      .map((p) => {
        const plClass = Number(p.unrealizedPl) >= 0 ? "positive" : "negative";
        return `<tr>
          <td>${p.symbol}</td>
          <td>${formatNumber(p.qty)}</td>
          <td>${formatMoney(p.marketValue)}</td>
          <td class="${plClass}">${formatMoney(p.unrealizedPl)}</td>
        </tr>`;
      })
      .join("");

  $("recentOrdersBody").innerHTML =
    rowsOrEmpty(orders, 4, "No recent orders.") +
    orders
      .map(
        (o) => `<tr>
          <td>${o.symbol}</td>
          <td>${statusLabel(o.side)}</td>
          <td>${formatNumber(o.qty)}</td>
          <td>${statusLabel(o.status)}</td>
        </tr>`,
      )
      .join("");
}

function drawChart(bars) {
  const canvas = $("priceChart");
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.max(640, Math.floor(rect.width * dpr));
  canvas.height = Math.floor(360 * dpr);
  ctx.scale(dpr, dpr);

  const width = canvas.width / dpr;
  const height = canvas.height / dpr;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);

  if (!bars.length) {
    ctx.fillStyle = "#667085";
    ctx.font = "14px system-ui";
    ctx.fillText("No chart data available.", 24, 40);
    return;
  }

  const pad = { top: 20, right: 18, bottom: 34, left: 54 };
  const closes = bars.map((bar) => bar.close);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;
  const xStep = (width - pad.left - pad.right) / Math.max(1, bars.length - 1);
  const y = (price) => pad.top + (height - pad.top - pad.bottom) * (1 - (price - min) / range);
  const x = (index) => pad.left + index * xStep;

  ctx.strokeStyle = "#dde3ea";
  ctx.lineWidth = 1;
  for (let i = 0; i < 4; i += 1) {
    const yy = pad.top + ((height - pad.top - pad.bottom) / 3) * i;
    ctx.beginPath();
    ctx.moveTo(pad.left, yy);
    ctx.lineTo(width - pad.right, yy);
    ctx.stroke();
  }

  ctx.strokeStyle = "#089e9a";
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  bars.forEach((bar, index) => {
    const xx = x(index);
    const yy = y(bar.close);
    if (index === 0) ctx.moveTo(xx, yy);
    else ctx.lineTo(xx, yy);
  });
  ctx.stroke();

  const gradient = ctx.createLinearGradient(0, pad.top, 0, height - pad.bottom);
  gradient.addColorStop(0, "rgba(8, 158, 154, 0.18)");
  gradient.addColorStop(1, "rgba(18, 119, 184, 0)");
  ctx.lineTo(x(bars.length - 1), height - pad.bottom);
  ctx.lineTo(x(0), height - pad.bottom);
  ctx.closePath();
  ctx.fillStyle = gradient;
  ctx.fill();

  ctx.fillStyle = "#667085";
  ctx.font = "12px system-ui";
  ctx.fillText(formatMoney(max), 8, y(max) + 4);
  ctx.fillText(formatMoney(min), 8, y(min) + 4);
  ctx.fillText(bars[0].date, pad.left, height - 10);
  ctx.fillText(bars[bars.length - 1].date, Math.max(pad.left, width - 110), height - 10);
}

function list(items) {
  return items.map((item) => `<li>${item}</li>`).join("");
}

function riskCards(items) {
  if (!items.length) {
    return `<p class="brief">No risk notes returned for this symbol.</p>`;
  }
  const labels = ["Trend Risk", "Price Location", "Execution Risk", "Catalyst Risk"];
  return items
    .map(
      (item, index) => `<article class="risk-item">
        <span>${labels[index] || "Risk Note"}</span>
        <p>${item}</p>
      </article>`,
    )
    .join("");
}

function analysisCards(items) {
  if (!items.length) {
    return `<p class="brief">Preview a trade to generate setup analysis.</p>`;
  }
  return items
    .map(
      (item) => `<article class="analysis-item">
        <p>${item}</p>
      </article>`,
    )
    .join("");
}

async function runResearch() {
  const symbol = $("researchSymbol").value.trim().toUpperCase() || "AAPL";
  $("researchTitle").textContent = `${symbol} Research`;
  toast(`Researching ${symbol}...`);
  const payload = await api(`/api/research?symbol=${encodeURIComponent(symbol)}`);
  state.research = payload;

  $("researchTitle").textContent = `${payload.symbol} Research`;
  $("stockBrief").textContent = payload.summary;
  $("researchChange").textContent = payload.indicators
    ? `${payload.indicators.periodChangePct >= 0 ? "+" : ""}${payload.indicators.periodChangePct.toFixed(2)}%`
    : "--";
  $("indicators").innerHTML = payload.indicators
    ? [
        ["Last Close", formatMoney(payload.indicators.lastClose)],
        ["20D SMA", formatMoney(payload.indicators.sma20)],
        ["50D SMA", formatMoney(payload.indicators.sma50)],
        ["20D Avg Volume", formatNumber(payload.indicators.avgVolume20)],
      ]
        .map(([label, value]) => `<div class="indicator"><span>${label}</span><strong>${value}</strong></div>`)
        .join("")
    : "";
  $("riskList").innerHTML = riskCards(payload.risks || []);
  $("newsList").innerHTML = payload.news.length
    ? payload.news
        .map(
          (item) => `<article class="news-item">
            <a href="${item.url}" target="_blank" rel="noreferrer">${item.headline}</a>
            <p>${item.summary || item.source || ""}</p>
          </article>`,
        )
        .join("")
    : `<p class="brief">No recent Alpaca news returned for this symbol.</p>`;
  drawChart(payload.bars || []);

  $("planSymbol").value = payload.symbol;
}

async function previewTrade() {
  const body = {
    symbol: $("planSymbol").value.trim().toUpperCase() || "AAPL",
    side: $("planSide").value,
    qty: Number($("planQty").value || 1),
  };
  const payload = await api("/api/trade/preview", { method: "POST", body: JSON.stringify(body) });
  state.preview = payload;
  $("planEntry").textContent = formatMoney(payload.entry);
  $("planStop").textContent = formatMoney(payload.stop);
  $("planTarget").textContent = formatMoney(payload.target);
  $("planSize").textContent = formatMoney(payload.estimatedNotional);
  $("planConfidence").textContent = payload.confidence;
  $("planVerdict").textContent = payload.verdict || "Trade read";
  $("planScore").textContent = payload.score === undefined ? "--" : `${payload.score}/100`;
  $("planAnalysis").textContent = payload.analysis || "";
  $("planReasons").innerHTML = analysisCards(payload.reasons || []);
  $("submitTrade").disabled = false;
}

async function submitTrade() {
  if (!state.preview) return;
  const message = `${state.preview.side.toUpperCase()} ${state.preview.qty} ${state.preview.symbol} as a paper market order?`;
  if (!window.confirm(message)) return;
  const payload = await api("/api/trade/submit", { method: "POST", body: JSON.stringify(state.preview) });
  toast(`Submitted ${payload.symbol}: ${statusLabel(payload.status)}`);
  await Promise.all([loadDashboard(), loadOrders()]);
}

async function loadOrders() {
  const status = $("ordersStatus").value;
  const orders = await api(`/api/orders?status=${encodeURIComponent(status)}&limit=50`);
  $("ordersBody").innerHTML =
    rowsOrEmpty(orders, 6, "No matching orders.") +
    orders
      .map(
        (o) => `<tr>
          <td>${o.submittedAt ? new Date(o.submittedAt).toLocaleString() : "--"}</td>
          <td>${o.symbol}</td>
          <td>${statusLabel(o.side)}</td>
          <td>${formatNumber(o.qty)}</td>
          <td>${statusLabel(o.status)}</td>
          <td>${formatMoney(o.filledAvgPrice)}</td>
        </tr>`,
      )
      .join("");
}

function bindTabs() {
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((node) => node.classList.remove("active"));
      document.querySelectorAll(".view").forEach((node) => node.classList.remove("active"));
      button.classList.add("active");
      $(button.dataset.tab).classList.add("active");
    });
  });
}

function bindActions() {
  $("refreshDashboard").addEventListener("click", () => loadDashboard().catch((error) => toast(error.message)));
  $("runResearch").addEventListener("click", () => runResearch().catch((error) => toast(error.message)));
  $("previewTrade").addEventListener("click", () => previewTrade().catch((error) => toast(error.message)));
  $("submitTrade").addEventListener("click", () => submitTrade().catch((error) => toast(error.message)));
  $("refreshOrders").addEventListener("click", () => loadOrders().catch((error) => toast(error.message)));
  $("ordersStatus").addEventListener("change", () => loadOrders().catch((error) => toast(error.message)));
  window.addEventListener("resize", () => state.research && drawChart(state.research.bars || []));
}

async function boot() {
  bindTabs();
  bindActions();
  await Promise.all([loadDashboard(), loadOrders()]);
  await runResearch();
}

boot().catch((error) => toast(error.message));
