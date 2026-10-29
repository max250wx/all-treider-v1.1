const API = "";

const state = {
    category: "stocks",
    ticker: "SBER",
    name: "Сбербанк",
    board: "TQBR",
    timeframe: "M1",
    mode: "manual",
    token: localStorage.getItem("auth_token") || null,
    notifyEnabled: false,
    lastNewsIds: new Set(),
};

let grid = null;
let portfolio = JSON.parse(localStorage.getItem("portfolio") || "[]");
let prices = {};
let instruments = null;

async function fetchJSON(path, useAuth = false) {
    try {
        const headers = {};
        if (useAuth && state.token) headers["Authorization"] = "Bearer " + state.token;
        const r = await fetch(API + path, { headers });
        if (!r.ok) return null;
        return await r.json();
    } catch (e) { return null; }
}

function timeAgo(iso) {
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60) return "сейчас";
    if (diff < 3600) return Math.floor(diff / 60) + "м";
    if (diff < 86400) return Math.floor(diff / 3600) + "ч";
    return new Date(iso).toLocaleDateString();
}

function sentBadge(s) {
    let cls = "neu", text = "0.00";
    if (s > 0.3) { cls = "pos"; text = "+" + s.toFixed(2); }
    else if (s < -0.3) { cls = "neg"; text = s.toFixed(2); }
    return `<span class="sent-badge ${cls}">${text}</span>`;
}

async function doLogin() {
    const login = document.getElementById("login-user").value.trim();
    const password = document.getElementById("login-pass").value;
    const errEl = document.getElementById("login-error");
    if (!login || !password) { errEl.textContent = "Заполните оба поля"; return; }
    const r = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ login, password }),
    });
    if (!r.ok) { errEl.textContent = "Неверный логин или пароль"; return; }
    const data = await r.json();
    state.token = data.token;
    localStorage.setItem("auth_token", data.token);
    showApp();
}

function logout() {
    if (state.token) {
        fetch("/api/logout", {
            method: "POST",
            headers: { "Authorization": "Bearer " + state.token },
        });
    }
    state.token = null;
    localStorage.removeItem("auth_token");
    location.reload();
}

function showApp() {
    document.getElementById("login-screen").style.display = "none";
    document.getElementById("app").style.display = "flex";
    document.getElementById("app").style.flexDirection = "column";
    document.getElementById("app").style.height = "100vh";
    startApp();
}

function toggleNotifications() {
    if (!("Notification" in window)) { alert("Браузер не поддерживает уведомления"); return; }
    if (state.notifyEnabled) {
        state.notifyEnabled = false;
        document.getElementById("btn-notify").classList.remove("active");
        return;
    }
    Notification.requestPermission().then(p => {
        if (p === "granted") {
            state.notifyEnabled = true;
            document.getElementById("btn-notify").classList.add("active");
            new Notification("Уведомления включены", { body: "Оповещения при |sentiment| > 0.85" });
        }
    });
}

function checkNewImportantNews(news) {
    if (!state.notifyEnabled || !news) return;
    news.forEach(n => {
        const id = n.title.slice(0, 60);
        if (state.lastNewsIds.has(id)) return;
        state.lastNewsIds.add(id);
        if (Math.abs(n.sentiment) > 0.85) {
            const emoji = n.sentiment > 0 ? "🟢" : "🔴";
            new Notification(`${emoji} Важная новость`, { body: n.title.slice(0, 150), tag: id });
        }
    });
}

async function exportNews() {
    if (!state.token) return;
    const r = await fetch("/api/export/news", { headers: { "Authorization": "Bearer " + state.token } });
    if (!r.ok) { alert("Ошибка экспорта"); return; }
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "news_export.csv";
    a.click();
    URL.revokeObjectURL(url);
}

const WIDGET_TEMPLATES = {
    chart: `
        <div class="tf-bar" style="display:flex;gap:4px;margin-bottom:8px;flex-wrap:wrap;">
            <button class="tf-btn active" data-tf="M1" style="padding:3px 8px;background:var(--yellow);color:#000;border:none;border-radius:4px;cursor:pointer;font-size:11px;font-weight:700;">1м</button>
            <button class="tf-btn" data-tf="M5" style="padding:3px 8px;background:var(--panel2);color:var(--dim);border:none;border-radius:4px;cursor:pointer;font-size:11px;">5м</button>
            <button class="tf-btn" data-tf="M15" style="padding:3px 8px;background:var(--panel2);color:var(--dim);border:none;border-radius:4px;cursor:pointer;font-size:11px;">15м</button>
            <button class="tf-btn" data-tf="H1" style="padding:3px 8px;background:var(--panel2);color:var(--dim);border:none;border-radius:4px;cursor:pointer;font-size:11px;">1ч</button>
            <button class="tf-btn" data-tf="D1" style="padding:3px 8px;background:var(--panel2);color:var(--dim);border:none;border-radius:4px;cursor:pointer;font-size:11px;">1д</button>
        </div>
        <canvas id="chart-canvas" style="width:100%;height:calc(100% - 30px);"></canvas>
    `,
    orderbook: `<div id="ob-content" style="font-size:12px;">Загрузка...</div>`,
    trades: `<div id="trades-content">Загрузка...</div>`,
    signals: `<div id="signals-content">Загрузка...</div>`,
    news: `<div id="news-content">Загрузка...</div>`,
    tg: `<div id="tg-content">Загрузка...</div>`,
    rvi: `<div id="rvi-content"></div>`,
    portfolio: `
        <div class="portfolio-form">
            <input id="pf-ticker" placeholder="Тикер" maxlength="10">
            <input id="pf-qty" type="number" placeholder="Кол-во" min="1">
            <input id="pf-price" type="number" placeholder="Цена" step="0.01">
            <button onclick="addPosition()">+</button>
        </div>
        <div id="pf-content"></div>
    `,
};

function initGrid() {
    // Проверяем, что GridStack загружен
    if (typeof GridStack === "undefined") {
        console.error("GridStack не загружен! Проверьте CDN.");
        return;
    }

    let saved = null;
    try {
        const raw = localStorage.getItem("grid-layout");
        if (raw) {
            const parsed = JSON.parse(raw);
            // Важно: если массив пустой, считаем layout несохранённым
            if (Array.isArray(parsed) && parsed.length > 0) {
                saved = parsed;
            }
        }
    } catch (e) {
        console.warn("Ошибка чтения localStorage", e);
    }

    grid = GridStack.init({
        column: 12,
        cellHeight: 70,
        margin: 6,
        animate: true,
        draggable: { handle: ".widget-header" },
        resizable: { handles: "all" },
        float: true,
        disableOneColumnMode: false,
    });

    grid.on("change", () => {
        localStorage.setItem("grid-layout", JSON.stringify(grid.save()));
    });

    if (saved) {
        try {
            grid.load(saved);
            // Проверяем, что что-то реально загрузилось
            if (grid.engine.nodes.length === 0) {
                console.warn("Layout пустой после загрузки — создаём дефолтный");
                createDefaultLayout();
            } else {
                setTimeout(loadAllWidgetsData, 200);
            }
        } catch (e) {
            console.error("Ошибка загрузки layout", e);
            createDefaultLayout();
        }
    } else {
        createDefaultLayout();
    }

    setInterval(loadAllWidgetsData, 30000);
    setInterval(refreshLiveData, 5000);
}

function resetLayout() {
    if (!confirm("Сбросить раскладку виджетов?")) return;
    localStorage.removeItem("grid-layout");
    location.reload();
}

function createDefaultLayout() {
    grid.removeAll();
    addWidget("chart",     "📈 График",        0, 0,  8, 6);
    addWidget("orderbook", "📊 Стакан",        8, 0,  4, 6);
    addWidget("trades",    "💱 Сделки",        8, 6,  4, 4);
    addWidget("signals",   "🎯 Сигналы",       0, 6,  4, 4);
    addWidget("news",      "📰 RSS-новости",   4, 6,  4, 4);
    addWidget("tg",        "📱 Telegram",      0, 10, 6, 4);
    addWidget("rvi",       "😱 RVI",           6, 10, 3, 4);
    addWidget("portfolio", "💼 Портфель",      9, 10, 3, 4);
    localStorage.setItem("grid-layout", JSON.stringify(grid.save()));
}

function addWidget(id, title, x, y, w, h) {
    const el = document.createElement("div");
    el.className = "grid-stack-item";
    el.setAttribute("gs-id", id);
    el.setAttribute("gs-x", x);
    el.setAttribute("gs-y", y);
    el.setAttribute("gs-w", w);
    el.setAttribute("gs-h", h);

    el.innerHTML = `
        <div class="grid-stack-item-content">
            <div class="widget-header">
                <div class="widget-title">${title}</div>
                <div class="widget-tools">
                    <button class="w-close" data-id="${id}" title="Скрыть">✕</button>
                </div>
            </div>
            <div class="widget-body">${WIDGET_TEMPLATES[id]}</div>
        </div>
    `;

    grid.makeWidget(el);

    el.querySelector(".w-close").onclick = () => {
        grid.removeWidget(el);
        localStorage.setItem("grid-layout", JSON.stringify(grid.save()));
    };

    if (id === "chart") {
        el.querySelectorAll(".tf-btn").forEach(btn => {
            btn.onclick = () => {
                el.querySelectorAll(".tf-btn").forEach(b => {
                    b.style.background = "var(--panel2)";
                    b.style.color = "var(--dim)";
                    b.style.fontWeight = "normal";
                });
                btn.style.background = "var(--yellow)";
                btn.style.color = "#000";
                btn.style.fontWeight = "700";
                state.timeframe = btn.dataset.tf;
                loadChart();
            };
        });
    }

    if (id === "portfolio") renderPortfolio();
    return el;
}

async function loadAllWidgetsData() {
    await Promise.all([
        loadChart(), loadOrderbook(), loadTrades(),
        loadSignals(), loadNews(), loadTelegram(),
        loadRVI(), loadPortfolioPrices(),
    ]);
}

async function refreshLiveData() {
    await Promise.all([loadOrderbook(), loadTrades()]);
}

async function loadChart() {
    const canvas = document.getElementById("chart-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    canvas.width = canvas.offsetWidth * dpr;
    canvas.height = canvas.offsetHeight * dpr;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const r = await fetchJSON(`/api/candles/${state.board}/${state.ticker}?timeframe=${state.timeframe}&count=150`);
    if (!r || !r.candles || !r.candles.length) {
        ctx.fillStyle = "#8e8e93";
        ctx.font = `${14 * dpr}px sans-serif`;
        ctx.textAlign = "center";
        ctx.fillText("Нет данных", canvas.width / 2, canvas.height / 2);
        return;
    }
    const candles = r.candles;
    const allPrices = candles.flatMap(c => [c.high, c.low]);
    const min = Math.min(...allPrices), max = Math.max(...allPrices);
    const range = max - min || 1;
    const W = canvas.width, H = canvas.height;
    const pad = { top: 15 * dpr, bottom: 15 * dpr, left: 5, right: 55 * dpr };
    const chartW = W - pad.left - pad.right;
    const chartH = H - pad.top - pad.bottom;
    const stepW = chartW / candles.length;
    const candleW = stepW * 0.7;
    const yFor = p => pad.top + (1 - (p - min) / range) * chartH;
    ctx.strokeStyle = "#1c1c1e";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
        const y = pad.top + (i / 4) * chartH;
        ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(W - pad.right, y); ctx.stroke();
        ctx.fillStyle = "#8e8e93";
        ctx.font = `${10 * dpr}px sans-serif`;
        ctx.textAlign = "right";
        ctx.fillText((max - (i / 4) * range).toFixed(2), W - 5, y + 4);
    }
    candles.forEach((c, i) => {
        const x = pad.left + i * stepW + stepW / 2;
        const color = c.close >= c.open ? "#26a69a" : "#ef5350";
        ctx.strokeStyle = color;
        ctx.fillStyle = color;
        ctx.lineWidth = dpr;
        ctx.beginPath();
        ctx.moveTo(x, yFor(c.high));
        ctx.lineTo(x, yFor(c.low));
        ctx.stroke();
        const bodyTop = Math.min(yFor(c.open), yFor(c.close));
        const bodyH = Math.max(Math.abs(yFor(c.close) - yFor(c.open)), dpr);
        ctx.fillRect(x - candleW / 2, bodyTop, candleW, bodyH);
    });
}

async function loadOrderbook() {
    const el = document.getElementById("ob-content");
    if (!el) return;
    const r = await fetchJSON(`/api/orderbook/${state.ticker}`);
    if (!r) { el.innerHTML = "Нет данных"; return; }
    const asks = (r.asks || []).slice().reverse();
    const bids = r.bids || [];
    const maxQ = Math.max(...asks.map(a => a.qty), ...bids.map(b => b.qty), 1);
    let html = "";
    asks.forEach(a => {
        html += `<div class="ob-row ask"><div class="qty-bar" style="width:${(a.qty / maxQ * 100).toFixed(1)}%"></div><span class="p">${a.price.toFixed(2)}</span><span class="q">${a.qty.toLocaleString()}</span></div>`;
    });
    if (asks.length && bids.length) {
        const spread = (asks[asks.length - 1].price - bids[0].price).toFixed(2);
        html += `<div class="ob-spread-line">Спред ${spread}</div>`;
    }
    bids.forEach(b => {
        html += `<div class="ob-row bid"><div class="qty-bar" style="width:${(b.qty / maxQ * 100).toFixed(1)}%"></div><span class="p">${b.price.toFixed(2)}</span><span class="q">${b.qty.toLocaleString()}</span></div>`;
    });
    el.innerHTML = html || "Нет данных";
}

async function loadTrades() {
    const el = document.getElementById("trades-content");
    if (!el) return;
    const r = await fetchJSON(`/api/trades/${state.ticker}?limit=50`);
    if (!r || !r.trades) { el.innerHTML = "Нет данных"; return; }
    el.innerHTML = r.trades.map(t => `
        <div class="trade-row ${t.side.toLowerCase()}">
            <span class="t">${new Date(t.time).toLocaleTimeString("ru-RU")}</span>
            <span class="p">${t.price.toFixed(2)}</span>
            <span class="q">${t.qty}</span>
        </div>
    `).join("");
}

async function loadSignals() {
    const el = document.getElementById("signals-content");
    if (!el) return;
    const r = await fetchJSON("/api/signals");
    if (!r || !r.signals.length) { el.innerHTML = '<div style="color:var(--dim);padding:10px;">Нет сигналов</div>'; return; }
    el.innerHTML = r.signals.slice(0, 15).map(s => `
        <div class="signal-row">
            <span class="badge ${s.signal.toLowerCase()}">${s.signal}</span>
            <span style="color:var(--dim);font-size:10px;">${timeAgo(s.time)}</span>
            <span class="x">${s.title}</span>
        </div>
    `).join("");
}

async function loadNews() {
    const el = document.getElementById("news-content");
    if (!el) return;
    const r = await fetchJSON("/api/news?limit=30");
    if (!r) { el.innerHTML = "Нет данных"; return; }
    checkNewImportantNews(r.news);
    el.innerHTML = r.news.map(n => `
        <div class="news-item">
            <span class="t">${timeAgo(n.time)}</span>
            <span class="src">[${n.source}]</span>
            ${sentBadge(n.sentiment)}
            <span class="x">${n.title}</span>
        </div>
    `).join("");
}

async function loadTelegram() {
    const el = document.getElementById("tg-content");
    if (!el) return;
    const r = await fetchJSON("/api/telegram?limit=30");
    if (!r) { el.innerHTML = "Нет данных"; return; }
    el.innerHTML = r.news.map(n => `
        <div class="tg-item">
            <span class="t">${timeAgo(n.time)}</span>
            <span class="src">[${n.channel}]</span>
            ${sentBadge(n.sentiment)}
            <span class="x">${n.text}</span>
        </div>
    `).join("");
}

async function loadRVI() {
    const el = document.getElementById("rvi-content");
    if (!el) return;
    const r = await fetchJSON("/api/rvi");
    if (!r) { el.innerHTML = "Нет данных"; return; }
    const miniEl = document.getElementById("rvi-mini");
    if (miniEl) miniEl.textContent = r.current.toFixed(2);
    let zone = "НЕЙТРАЛЬНО", color = "var(--dim)";
    if (r.current > 60) { zone = "ЭКСТРЕМАЛЬНАЯ ПАНИКА"; color = "var(--red)"; }
    else if (r.current > 40) { zone = "ПАНИКА"; color = "var(--red)"; }
    else if (r.current < 20) { zone = "СПОКОЙСТВИЕ"; color = "var(--green)"; }
    const changeColor = r.change > 0 ? "var(--red)" : "var(--green)";
    const arrow = r.change > 0 ? "↗" : "↘";
    el.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px;">
            <div style="font-size:28px;font-weight:700;color:#fff;">${r.current.toFixed(2)}</div>
            <div style="color:${changeColor};font-size:13px;font-weight:600;">${arrow} ${r.change.toFixed(2)}%</div>
        </div>
        <div style="color:${color};font-size:11px;font-weight:700;margin-bottom:8px;">${zone}</div>
        <canvas id="rvi-chart-canvas" style="width:100%;height:80px;"></canvas>
    `;
    requestAnimationFrame(() => {
        const canvas = document.getElementById("rvi-chart-canvas");
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        const dpr = window.devicePixelRatio || 1;
        canvas.width = canvas.offsetWidth * dpr;
        canvas.height = canvas.offsetHeight * dpr;
        const values = r.history.map(h => h.value);
        if (values.length < 2) return;
        const min = Math.min(...values), max = Math.max(...values);
        const range = max - min || 1;
        const W = canvas.width, H = canvas.height;
        ctx.clearRect(0, 0, W, H);
        const grad = ctx.createLinearGradient(0, 0, 0, H);
        grad.addColorStop(0, "rgba(255, 221, 45, 0.3)");
        grad.addColorStop(1, "rgba(255, 221, 45, 0)");
        ctx.beginPath();
        values.forEach((v, i) => {
            const x = (i / (values.length - 1)) * W;
            const y = H - ((v - min) / range) * (H - 10) - 5;
            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        });
        ctx.strokeStyle = "#ffdd2d";
        ctx.lineWidth = 2 * dpr;
        ctx.stroke();
        ctx.lineTo(W, H); ctx.lineTo(0, H); ctx.closePath();
        ctx.fillStyle = grad; ctx.fill();
    });
}

function addPosition() {
    const t = document.getElementById("pf-ticker").value.trim().toUpperCase();
    const q = parseFloat(document.getElementById("pf-qty").value);
    const p = parseFloat(document.getElementById("pf-price").value);
    if (!t || !q || !p) { alert("Заполните все поля"); return; }
    portfolio.push({ ticker: t, qty: q, buyPrice: p });
    localStorage.setItem("portfolio", JSON.stringify(portfolio));
    document.getElementById("pf-ticker").value = "";
    document.getElementById("pf-qty").value = "";
    document.getElementById("pf-price").value = "";
    loadPortfolioPrices();
}

function removePosition(i) {
    portfolio.splice(i, 1);
    localStorage.setItem("portfolio", JSON.stringify(portfolio));
    renderPortfolio();
}

async function loadPortfolioPrices() {
    if (!portfolio.length) { renderPortfolio(); return; }
    const tickers = portfolio.map(p => p.ticker).join(",");
    const r = await fetchJSON(`/api/portfolio/prices?tickers=${tickers}`);
    if (r && r.prices) prices = r.prices;
    renderPortfolio();
}

function renderPortfolio() {
    const el = document.getElementById("pf-content");
    if (!el) return;
    if (!portfolio.length) {
        el.innerHTML = '<div style="color:var(--dim);padding:10px;font-size:11px;">Добавьте позиции через форму выше</div>';
        return;
    }
    let totalCost = 0, totalValue = 0, rows = "";
    portfolio.forEach((p, i) => {
        const cur = prices[p.ticker] || p.buyPrice;
        const cost = p.qty * p.buyPrice;
        const value = p.qty * cur;
        const pnl = value - cost;
        const pnlPct = cost ? (pnl / cost) * 100 : 0;
        totalCost += cost; totalValue += value;
        rows += `
            <tr>
                <td>${p.ticker}</td>
                <td style="text-align:right;">${p.qty}</td>
                <td style="text-align:right;">${p.buyPrice.toFixed(2)}</td>
                <td style="text-align:right;">${cur.toFixed(2)}</td>
                <td style="text-align:right;" class="${pnl >= 0 ? 'pnl-pos' : 'pnl-neg'}">
                    ${pnl >= 0 ? "+" : ""}${pnl.toFixed(2)} (${pnlPct.toFixed(2)}%)
                </td>
                <td style="text-align:right;"><button class="del" onclick="removePosition(${i})">×</button></td>
            </tr>
        `;
    });
    const totalPnl = totalValue - totalCost;
    const totalPnlPct = totalCost ? (totalPnl / totalCost) * 100 : 0;
    el.innerHTML = `
        <table class="portfolio-table">
            <thead>
                <tr>
                    <th>Тикер</th><th style="text-align:right;">Кол-во</th>
                    <th style="text-align:right;">Покупка</th><th style="text-align:right;">Текущая</th>
                    <th style="text-align:right;">P&L</th><th></th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
        <div class="portfolio-summary">
            <span>Стоимость: <b>${totalValue.toFixed(2)} ₽</b></span>
            <span class="${totalPnl >= 0 ? 'pnl-pos' : 'pnl-neg'}">
                ${totalPnl >= 0 ? "+" : ""}${totalPnl.toFixed(2)} (${totalPnlPct.toFixed(2)}%)
            </span>
        </div>
    `;
}

async function loadInstruments() {
    const r = await fetchJSON("/api/instruments");
    if (!r) return;
    instruments = r.categories;
    renderInstruments();
    document.querySelectorAll(".cat-btn").forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll(".cat-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            state.category = btn.dataset.cat;
            renderInstruments();
        };
    });
}

function renderInstruments() {
    const el = document.getElementById("instr-list");
    if (!instruments || !instruments[state.category]) return;
    el.innerHTML = "";
    instruments[state.category].items.forEach(item => {
        const chip = document.createElement("button");
        chip.className = "instr-chip" + (item.ticker === state.ticker ? " active" : "");
        chip.innerHTML = `${item.ticker} <span class="nm">${item.name}</span>`;
        chip.onclick = () => selectInstrument(item);
        el.appendChild(chip);
    });
}

function selectInstrument(item) {
    state.ticker = item.ticker;
    state.name = item.name;
    state.board = item.board;
    renderInstruments();
    refreshLiveData();
    loadChart();
}

document.querySelectorAll(".mode-btn").forEach(btn => {
    btn.onclick = () => {
        document.querySelectorAll(".mode-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        state.mode = btn.dataset.mode;
        const hints = {
            manual: "Ручной режим: торговлю совершает только пользователь",
            auto: "Автоматический режим: система показывает сигналы, торговлю совершает пользователь",
            advisor: "Советник: система даёт рекомендации, решение за вами",
        };
        document.getElementById("mode-hint").textContent = hints[state.mode];
    };
});

setInterval(() => {
    const el = document.getElementById("clock");
    if (el) el.textContent = new Date().toLocaleTimeString("ru-RU");
}, 1000);

async function loadStatus() {
    const s = await fetchJSON("/api/status");
    if (!s) return;
    document.getElementById("status").textContent =
        `RSS: ${s.rss_count} · TG: ${s.telegram_count} · RVI: ${s.rvi_count}`;
}

function startApp() {
    initGrid();
    loadInstruments();
    loadStatus();
    setInterval(loadStatus, 30000);
    setInterval(loadPortfolioPrices, 60000);
    document.getElementById("btn-notify").onclick = toggleNotifications;
    document.getElementById("btn-export").onclick = exportNews;
}

window.addEventListener("load", () => {
    document.getElementById("login-btn").onclick = doLogin;
    document.getElementById("login-pass").addEventListener("keypress", e => {
        if (e.key === "Enter") doLogin();
    });
    document.getElementById("login-user").addEventListener("keypress", e => {
        if (e.key === "Enter") document.getElementById("login-pass").focus();
    });
    if (state.token) {
        fetchJSON("/api/me", true).then(r => {
            if (r) showApp();
            else {
                state.token = null;
                localStorage.removeItem("auth_token");
            }
        });
    }
});
