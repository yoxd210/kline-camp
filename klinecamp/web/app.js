/* K线训练营前端
 *
 * 版式参考同花顺：主图 + 等高副图，每块左上角有「名称 + 数值」，
 * 十字光标在主图上移动时，竖线延续到所有副图，副图左上角同步显示当日的值。
 * 所有数字以后端为准（/api/session/*），前端只负责画和发指令。
 */

const S = {
  id: null,
  state: null,
  chart: null,
  candle: null,
  panels: [],          // 所有副图的 chart（跟随主图时间轴 + 十字光标）
  volChart: null,
  volSeries: null,
  macdChart: null,
  macdHist: null,
  macdDif: null,
  macdDea: null,
  forms: [],           // [{el, chart, line, name, formula}]
  data: { vol: [], bars: [] },
  formulas: [],
  timer: null,
  playing: false,
  finished: false,
};

const MAX_FORMULA_PANELS = 3;
const $ = (sel) => document.querySelector(sel);
const money = (v) => (v == null ? "—" : Number(v).toLocaleString("zh-CN", { maximumFractionDigits: 2 }));
const pct = (v) => (v == null ? "—" : (v >= 0 ? "+" : "") + Number(v).toFixed(2) + "%");

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.detail || d.error || `HTTP ${r.status}`);
  return d;
}

function msg(text, cls = "") {
  const el = $("#msg");
  if (!el) return;
  el.textContent = text || "";
  el.className = "msg " + cls;
  if (text) setTimeout(() => { if (el.textContent === text) el.textContent = ""; }, 4000);
}

/* ------------------------------------------------------------ 布局 */

const LAYOUT = { main: 460, panel: 92, width: 1180, shown: [] };
let layoutTimer = null;

function applyLayout(patch) {
  Object.assign(LAYOUT, patch || {});
  document.documentElement.style.setProperty("--main-h", LAYOUT.main + "px");
  document.documentElement.style.setProperty("--panel-h", LAYOUT.panel + "px");
  document.documentElement.style.setProperty("--chart-w", LAYOUT.width + "px");
  requestAnimationFrame(() => {
    for (const c of S.panels) c.timeScale().fitContent();
    syncPanels();
  });
}

function saveLayoutSoon() {
  clearTimeout(layoutTimer);
  layoutTimer = setTimeout(async () => {
    try {
      await api("/api/layout", { method: "POST", body: JSON.stringify(LAYOUT) });
    } catch (err) {
      msg("布局没存上：" + err.message, "err");
    }
  }, 500);
}

async function loadLayout() {
  try {
    const d = await api("/api/layout");
    Object.assign(LAYOUT, d.layout || {});
  } catch (err) {
    /* 用默认 */
  }
}

function bindGrips() {
  document.querySelectorAll("[data-grip]").forEach((grip) => {
    const key = grip.dataset.grip;   // main / panel
    grip.addEventListener("mousedown", (ev) => {
      ev.preventDefault();
      const startY = ev.clientY;
      const cssKey = key === "main" ? "--main-h" : "--panel-h";
      const startH = parseInt(getComputedStyle(document.documentElement).getPropertyValue(cssKey), 10) || 200;
      const move = (e) => {
        const h = Math.max(key === "main" ? 240 : 48, Math.min(key === "main" ? 900 : 300,
          Math.round(startH + (e.clientY - startY))));
        LAYOUT[key] = h;
        document.documentElement.style.setProperty(cssKey, h + "px");
        for (const c of S.panels) c.timeScale().fitContent();
        syncPanels();
      };
      const up = () => {
        document.removeEventListener("mousemove", move);
        document.removeEventListener("mouseup", up);
        saveLayoutSoon();
      };
      document.addEventListener("mousemove", move);
      document.addEventListener("mouseup", up);
    });
  });

  const v = $("#vdiv");
  if (v) {
    v.addEventListener("mousedown", (ev) => {
      ev.preventDefault();
      const startX = ev.clientX;
      const startW = LAYOUT.width;
      const move = (e) => {
        const w = Math.max(720, Math.min(1700, Math.round(startW + (e.clientX - startX))));
        LAYOUT.width = w;
        document.documentElement.style.setProperty("--chart-w", w + "px");
      };
      const up = () => {
        document.removeEventListener("mousemove", move);
        document.removeEventListener("mouseup", up);
        saveLayoutSoon();
      };
      document.addEventListener("mousemove", move);
      document.addEventListener("mouseup", up);
    });
  }

  $("#btnResetLayout").addEventListener("click", () => {
    applyLayout({ main: 460, panel: 92, width: 1180 });
    saveLayoutSoon();
    msg("布局已恢复默认", "ok");
  });
}

/* ------------------------------------------------------------ 图表 */

function chartOpts(extra = {}) {
  return {
    layout: { background: { color: "#0b1220" }, textColor: "#9fb3c8", fontSize: 11 },
    grid: { vertLines: { color: "#132033" }, horzLines: { color: "#132033" } },
    rightPriceScale: { borderColor: "#1d3049", scaleMargins: { top: 0.14, bottom: 0.1 } },
    timeScale: { borderColor: "#1d3049", rightOffset: 3, visible: false },
    crosshair: {
      mode: 0,
      vertLine: { color: "rgba(200,220,240,.55)", width: 1, style: 2, labelVisible: false },
      horzLine: { color: "rgba(200,220,240,.35)", width: 1, style: 2, labelVisible: false },
    },
    handleScroll: false,
    handleScale: false,
    ...extra,
  };
}

function mkChart(el, extra) {
  const chart = LightweightCharts.createChart(el, chartOpts(extra));
  const fit = () => chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
  fit();
  new ResizeObserver(fit).observe(el);
  return chart;
}

function ensureChart() {
  if (S.chart) return;
  const el = $("#chart");
  S.chart = LightweightCharts.createChart(el, chartOpts({
    timeScale: { borderColor: "#1d3049", rightOffset: 3, visible: true },
  }));
  const fit = () => S.chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
  fit();
  new ResizeObserver(fit).observe(el);

  S.candle = S.chart.addCandlestickSeries({
    upColor: "#ef4444", downColor: "#22c55e",
    borderUpColor: "#ef4444", borderDownColor: "#22c55e",
    wickUpColor: "#ef4444", wickDownColor: "#22c55e",
  });

  S.chart.timeScale().subscribeVisibleLogicalRangeChange((r) => {
    if (!r) return;
    for (const c of S.panels) c.timeScale().setVisibleLogicalRange(r);
  });
  S.chart.subscribeCrosshairMove(onCrosshair);
}

function ensurePanels() {
  if (S.volChart) return;
  S.volChart = mkChart($("#volChart"));
  S.volSeries = S.volChart.addHistogramSeries({ priceFormat: { type: "volume" } });
  S.panels.push(S.volChart);

  S.macdChart = mkChart($("#macdChart"));
  S.macdHist = S.macdChart.addHistogramSeries({ priceFormat: { type: "price", precision: 3 } });
  S.macdDif = S.macdChart.addLineSeries({ color: "#f5a524", lineWidth: 1 });
  S.macdDea = S.macdChart.addLineSeries({ color: "#4ea1ff", lineWidth: 1 });
  S.panels.push(S.macdChart);
}

function draw(bars) {
  ensureChart();
  ensurePanels();
  S.data.bars = bars;
  S.candle.setData(bars.map((b) => ({ time: b.time, open: b.open, high: b.high, low: b.low, close: b.close })));
  S.data.vol = bars.map((b) => ({
    time: b.time, value: b.volume,
    color: b.close >= b.open ? "rgba(239,68,68,.5)" : "rgba(34,197,94,.5)",
  }));
  S.volSeries.setData(S.data.vol);
  refreshMacd();
  refreshFormulas();
  syncPanels();
  updateLegend(null);
}

function syncPanels() {
  if (!S.chart) return;
  const r = S.chart.timeScale().getVisibleLogicalRange();
  if (!r) return;
  for (const c of S.panels) c.timeScale().setVisibleLogicalRange(r);
}

/* 十字光标：竖线贯通所有副图，左上角显示当天的值 */
function onCrosshair(param) {
  if (!param || !param.time) {
    for (const c of S.panels) c.clearCrosshairPosition();
    updateLegend(null);
    return;
  }
  const t = param.time;
  for (const c of S.panels) {
    try { c.setCrosshairPosition(valueOfPanel(c, t), t, seriesOf(c)); } catch (e) { /* 忽略 */ }
  }
  updateLegend(t);
}

function seriesOf(chart) {
  if (chart === S.volChart) return S.volSeries;
  if (chart === S.macdChart) return S.macdHist;
  const f = S.forms.find((x) => x.chart === chart);
  return f ? f.line : S.macdHist;
}

function valueOfPanel(chart, t) {
  if (chart === S.volChart) {
    const hit = S.data.vol.find((x) => x.time === t);
    return hit ? hit.value : 0;
  }
  if (chart === S.macdChart) {
    const hit = (S.data.macdHist || []).find((x) => x.time === t);
    return hit ? hit.value : 0;
  }
  const f = S.forms.find((x) => x.chart === chart);
  if (f) {
    const hit = (f.data || []).find((x) => x.time === t);
    return hit ? hit.value : 0;
  }
  return 0;
}

function fmt(n, d = 2) {
  return n == null || n !== n ? "—" : Number(n).toFixed(d);
}

function updateLegend(time) {
  const bars = S.data.bars || [];
  if (!bars.length) return;
  const bar = time ? bars.find((b) => b.time === time) : bars[bars.length - 1];
  if (!bar) return;
  const chg = bar.close - bar.open;
  const cls = chg >= 0 ? "up" : "down";
  const d = time || bar.time;
  $("#legMain").innerHTML =
    `<b>K线</b><span class="lg">${d}　` +
    `开 <i>${fmt(bar.open)}</i> 高 <i>${fmt(bar.high)}</i> 低 <i>${fmt(bar.low)}</i> ` +
    `收 <i class="${cls}">${fmt(bar.close)}</i> ` +
    `涨跌 <i class="${cls}">${chg >= 0 ? "+" : ""}${fmt((chg / bar.open) * 100)}%</i></span>`;

  const vol = time ? (S.data.vol.find((x) => x.time === time) || {}) : (S.data.vol[S.data.vol.length - 1] || {});
  $("#legVol").innerHTML = `<b>成交量</b><span class="lg">${d}　量 <i>${vol.value ? (vol.value / 1e4).toFixed(0) + " 万" : "—"}</i></span>`;

  const hist = time ? ((S.data.macdHist || []).find((x) => x.time === time) || {}) : last(S.data.macdHist);
  const dif = time ? ((S.data.macdDif || []).find((x) => x.time === time) || {}) : last(S.data.macdDif);
  const dea = time ? ((S.data.macdDea || []).find((x) => x.time === time) || {}) : last(S.data.macdDea);
  $("#legMacd").innerHTML =
    `<b>MACD(12,26,9)</b><span class="lg">${d}　` +
    `DIF <i class="${(dif.value || 0) >= 0 ? "up" : "down"}">${fmt(dif.value, 3)}</i> ` +
    `DEA <i class="${(dea.value || 0) >= 0 ? "up" : "down"}">${fmt(dea.value, 3)}</i> ` +
    `MACD <i class="${(hist.value || 0) >= 0 ? "up" : "down"}">${fmt(hist.value, 3)}</i></span>`;

  S.forms.forEach((f) => {
    const hit = time ? ((f.data || []).find((x) => x.time === time) || {}) : last(f.data);
    const el = f.el.querySelector(".legend");
    if (el) {
      el.innerHTML = `<b>${f.name}</b><span class="lg">${d}　<i>${fmt(hit.value, 3)}</i></span>`;
    }
  });
}

const last = (arr) => (arr && arr.length ? arr[arr.length - 1] : {});

/* ------------------------------------------------------------ MACD */

async function refreshMacd() {
  if (!S.id) return;
  try {
    const d = await api(`/api/session/${S.id}/macd`);
    S.data.macdDif = d.dif || [];
    S.data.macdDea = d.dea || [];
    S.data.macdHist = (d.hist || []).map((x) => ({
      time: x.time, value: x.value,
      color: x.value >= 0 ? "rgba(239,68,68,.6)" : "rgba(34,197,94,.6)",
    }));
    S.macdDif.setData(S.data.macdDif);
    S.macdDea.setData(S.data.macdDea);
    S.macdHist.setData(S.data.macdHist);
  } catch (err) {
    /* 算不出来不影响主流程 */
  }
}

/* ------------------------------------------------------------ 公式副图 */

function addFormulaPanel(item) {
  if (S.forms.length >= MAX_FORMULA_PANELS) return;
  const el = document.createElement("div");
  el.className = "pane";
  el.innerHTML = `<div class="legend"><b>${item.name}</b><span class="lg"></span></div>
                  <div class="fchart"></div>`;
  $("#formulaRows").appendChild(el);

  const chart = mkChart(el.querySelector(".fchart"));
  const line = chart.addLineSeries({ color: "#f5a524", lineWidth: 2 });
  S.panels.push(chart);

  const rec = { el, chart, line, name: item.name, formula: item.formula, data: [] };
  S.forms.push(rec);
  applyFormula(rec);
}

async function applyFormula(rec) {
  if (!S.id || !rec) return;
  try {
    const d = await api(`/api/session/${S.id}/indicator?formula=${encodeURIComponent(rec.formula)}`);
    rec.data = d.values || [];
    rec.line.setData(rec.data);
    syncPanels();
    updateLegend(null);
  } catch (err) {
    rec.data = [];
    rec.line.setData([]);
    msg(`副图「${rec.name}」算不出来：${err.message}`, "err");
  }
}

function refreshFormulas() {
  S.forms.forEach((rec) => applyFormula(rec));
}

function rebuildFormulaPanels() {
  for (const rec of S.forms) {
    S.panels = S.panels.filter((c) => c !== rec.chart);
    rec.chart.remove();
    rec.el.remove();
  }
  S.forms = [];
  const shown = (LAYOUT.shown || []).slice(0, MAX_FORMULA_PANELS);
  shown.forEach((name) => {
    const item = S.formulas.find((x) => x.name === name);
    if (item) addFormulaPanel(item);
  });
}

/* ------------------------------------------------------------ 公式管理 */

async function openFormulaMgr() {
  $("#fmModal").classList.remove("hidden");
  await loadFormulas();
  renderFormulaMgr();
}

function renderFormulaMgr() {
  const shown = new Set(LAYOUT.shown || []);
  $("#fmShow").innerHTML = S.formulas
    .map((x) => `<label><input type="checkbox" value="${x.name}" ${shown.has(x.name) ? "checked" : ""}/>${x.name}</label>`)
    .join("");
  $("#fmShow").querySelectorAll("input").forEach((cb) => {
    cb.addEventListener("change", () => {
      const picked = [...$("#fmShow").querySelectorAll("input:checked")].map((x) => x.value);
      if (picked.length > MAX_FORMULA_PANELS) {
        cb.checked = false;
        msg(`最多只能同时显示 ${MAX_FORMULA_PANELS} 个公式副图`, "err");
        return;
      }
      LAYOUT.shown = picked;
      saveLayoutSoon();
      rebuildFormulaPanels();
      if (S.state) updateLegend(null);
    });
  });

  $("#fmList").innerHTML = S.formulas
    .map(
      (x) => `<div class="fm-item">
        <span>${x.name}</span>
        <code title="${x.hint || ""}">${x.formula}</code>
        <button class="ghost tiny fmdel" data-name="${x.name}">删除</button>
      </div>`
    )
    .join("");
  $("#fmList").querySelectorAll(".fmdel").forEach((b) => {
    b.addEventListener("click", async () => {
      try {
        const d = await api(`/api/formulas/${encodeURIComponent(b.dataset.name)}`, { method: "DELETE" });
        S.formulas = d.items || [];
        LAYOUT.shown = (LAYOUT.shown || []).filter((n) => n !== b.dataset.name);
        saveLayoutSoon();
        rebuildFormulaPanels();
        renderFormulaMgr();
        msg("已删除", "ok");
      } catch (err) {
        msg("删除失败：" + err.message, "err");
      }
    });
  });
}

async function saveFormulaFromMgr() {
  const name = ($("#fmName").value || "").trim();
  const formula = ($("#fmFormula").value || "").trim();
  const hint = ($("#fmHint").value || "").trim();
  const box = $("#fmMsg");
  if (!name || !formula) {
    box.textContent = "名称和公式都要填";
    return;
  }
  try {
    const d = await api("/api/formulas", {
      method: "POST",
      body: JSON.stringify({ name, formula, hint }),
    });
    S.formulas = d.items || [];
    if (!(LAYOUT.shown || []).includes(name) && (LAYOUT.shown || []).length < MAX_FORMULA_PANELS) {
      LAYOUT.shown = [...(LAYOUT.shown || []), name];
      saveLayoutSoon();
      rebuildFormulaPanels();
    }
    renderFormulaMgr();
    $("#fmName").value = "";
    $("#fmHint").value = "";
    box.textContent = `已保存到 ${d.saved_to.split("\\").pop()}`;
  } catch (err) {
    box.textContent = "保存失败：" + err.message;
  }
}

async function testFormula() {
  const formula = ($("#fmFormula").value || "").trim();
  const box = $("#fmMsg");
  if (!S.id) {
    box.textContent = "先开一局，才能用真实数据试算";
    return;
  }
  try {
    const d = await api(`/api/session/${S.id}/indicator?formula=${encodeURIComponent(formula)}`);
    box.textContent = `算出来了：${d.values.length} 个点`;
  } catch (err) {
    box.textContent = "算不出来：" + err.message;
  }
}

/* ------------------------------------------------------------ 会话 */

function render() {
  const st = S.state;
  if (!st) return;
  $("#nowDate").textContent = st.date;
  $("#equity").textContent = money(st.equity);
  $("#retLine").textContent = `收益率 ${pct(st.return_pct)} · 已练 ${st.cursor} 根 · 还剩 ${st.bars_left} 根`;
  $("#retLine").className = "sub " + (st.return_pct > 0 ? "up" : st.return_pct < 0 ? "down" : "");
  $("#cash").textContent = money(st.cash);
  $("#shares").textContent = st.shares + (st.locked ? `（${st.locked} 股 T+1）` : "");
  $("#cost").textContent = st.cost == null ? "—" : Number(st.cost).toFixed(3);
  $("#mv").textContent = money(st.market_value);
  $("#price").textContent = Number(st.price).toFixed(2);
  $("#tradeCount").textContent = st.trades;
  $("#pendingLine").textContent = st.pending
    ? `挂着：${st.pending.side === "buy" ? "买" : "卖"} ${st.pending.shares} 股，下一根开盘成交`
    : "";
}

async function openSession(body) {
  try {
    const d = await api("/api/session", { method: "POST", body: JSON.stringify(body) });
    S.id = d.id;
    S.state = d.state;
    S.finished = false;
    $("#caseName").textContent = d.case.name;
    $("#caseInfo").textContent =
      `${d.case.start_date} 起 · 前面 ${d.case.warmup_bars} 根可看 · 后面还有 ${d.case.future_bars} 根`;
    draw(d.bars);
    rebuildFormulaPanels();
    render();
    stopPlay();
    msg(d.mode === "blind" ? "盲盒已开：先看图，再决定下一根买不买" : "已开局", "ok");
  } catch (err) {
    msg("开局失败：" + err.message, "err");
  }
}

async function step() {
  if (!S.id || S.finished) return;
  try {
    const d = await api(`/api/session/${S.id}/step`, { method: "POST" });
    S.state = d.state;
    draw(d.bars);
    render();
    if (d.state.bars_left <= 0) {
      stopPlay();
      msg("已经走到最后一根，点「结算这一局」看成绩", "ok");
    }
  } catch (err) {
    stopPlay();
    msg(err.message, "err");
  }
}

async function order(side) {
  if (!S.id || S.finished) return;
  const shares = Number($("#shareInput").value || 0);
  try {
    const d = await api(`/api/session/${S.id}/order`, {
      method: "POST",
      body: JSON.stringify({ side, shares }),
    });
    S.state = d.state;
    if (d.bars) draw(d.bars);
    render();
    const word = side === "buy" ? "买入" : "卖出";
    if (d.filled) {
      msg(`已${word} ${d.filled.shares} 股 @ ${d.filled.price}（${d.filled.date} 开盘）`, "ok");
    } else {
      msg(`已挂${word}单 ${shares} 股，已经是最后一根，没有下一根可成交`, "err");
    }
    if (d.state.bars_left <= 0) {
      stopPlay();
      msg("已经走到最后一根，点「结算这一局」看成绩", "ok");
    }
  } catch (err) {
    stopPlay();
    msg(err.message, "err");
  }
}

/* 持仓不动 = 这一根不操作，直接走下一根 */
async function holdOne() {
  if (!S.id || S.finished) return;
  try {
    const d = await api(`/api/session/${S.id}/hold`, { method: "POST" });
    S.state = d.state;
    draw(d.bars);
    render();
    if (d.state.bars_left <= 0) {
      stopPlay();
      msg("已经走到最后一根，点「结算这一局」看成绩", "ok");
    }
  } catch (err) {
    msg(err.message, "err");
  }
}

async function finish() {
  if (!S.id || S.finished) return;
  try {
    const d = await api(`/api/session/${S.id}/finish`, { method: "POST" });
    S.finished = true;
    stopPlay();
    showResult(d.result);
    loadHistory();
  } catch (err) {
    msg(err.message, "err");
  }
}

/* ------------------------------------------------------------ 结算 */

function showResult(r) {
  $("#resultTitle").textContent = `本局结果 · ${r.name}（${r.code}）`;
  const rows = (r.trades || [])
    .map(
      (t) => `<tr>
        <td>${t.date}</td>
        <td class="${t.side === "buy" ? "up" : "down"}">${t.side === "buy" ? "买" : "卖"}</td>
        <td>${t.shares}</td><td>${t.price}</td><td>${t.fee}</td><td>${t.tax}</td>
        <td class="${(t.pnl || 0) > 0 ? "up" : (t.pnl || 0) < 0 ? "down" : ""}">${t.pnl == null ? "—" : t.pnl}</td>
      </tr>`
    )
    .join("");
  const b = r.benchmarks || {};
  const diff = (x) => (r.return_pct - x).toFixed(2);
  $("#resultBody").innerHTML = `
    <div class="sum">
      <div><span class="k">你的收益</span><b class="${r.return_pct >= 0 ? "up" : "down"}">${pct(r.return_pct)}</b></div>
      <div><span class="k">买入持有</span><b>${pct(b.buy_hold_pct)}</b><span class="meta">你 ${diff(b.buy_hold_pct)}%</span></div>
      <div><span class="k">MA20 纪律</span><b>${pct(b.ma20_pct)}</b><span class="meta">你 ${diff(b.ma20_pct)}%</span></div>
      <div><span class="k">最大回撤</span><b>${pct(-Math.abs(r.max_drawdown_pct))}</b></div>
      <div><span class="k">交易</span><b>${r.trades.length} 笔 / ${r.round_trips} 回合</b></div>
      <div><span class="k">胜率</span><b>${r.win_rate == null ? "—" : r.win_rate + "%"}</b></div>
    </div>
    <div class="meta">${r.start_date} → ${r.end_date}，共 ${r.bars_played} 根；起始 ${money(r.cash0)}，结束 ${money(r.equity_end)}</div>
    <div class="table-wrap"><table>
      <thead><tr><th>日期</th><th>方向</th><th>股数</th><th>成交价</th><th>佣金</th><th>印花税</th><th>盈亏</th></tr></thead>
      <tbody>${rows || `<tr><td colspan="7" class="meta">这一局一笔没做</td></tr>`}</tbody>
    </table></div>
    <div class="verdict">${verdict(r)}</div>
    <div class="meta" style="margin-top:8px">
      这一局只代表这段历史里的操作，不构成任何投资建议；据此交易，风险自负。
    </div>`;
  $("#resultModal").classList.remove("hidden");
}

function verdict(r) {
  const b = r.benchmarks || {};
  const mine = r.return_pct;
  if (!r.trades.length) return "一句话：这一局你一股没动。练的是「忍住」，也要记下你当时为什么不动。";
  if (mine > (b.buy_hold_pct ?? 0) && mine > (b.ma20_pct ?? 0)) return "一句话：你跑赢了「躺着拿」和「MA20 纪律」，这一局的操作是真有加的。";
  if (mine < (b.buy_hold_pct ?? 0) && mine < (b.ma20_pct ?? 0)) return "一句话：两头都没跑赢 —— 说明这几笔交易在减分，不如不做。回看是哪一笔开始偏的。";
  if (mine < (b.buy_hold_pct ?? 0)) return "一句话：不如买入持有。你多做的这些动作，净效果是负的。";
  return "一句话：比买入持有强，但不如机械执行 MA20。人主观的择时还不够稳。";
}

/* ------------------------------------------------------------ 记录 / 条件 */

async function loadHistory() {
  try {
    const d = await api("/api/history?limit=8");
    const s = d.summary || {};
    const rows = (d.items || [])
      .map(
        (x) => `<div class="h-row">
          <span class="h-date">${(x.created_at || "").slice(5, 16)}</span>
          <span class="h-name">${x.name || x.code}</span>
          <span class="${x.return_pct >= 0 ? "up" : "down"}">${pct(x.return_pct)}</span>
          <span class="meta">持 ${x.buy_hold_pct == null ? "—" : pct(x.buy_hold_pct)}</span>
        </div>`
      )
      .join("");
    $("#history").innerHTML =
      `<div class="meta">共 ${s.rounds || 0} 局 · 平均 ${pct(s.avg_return_pct)} · 胜局 ${s.win_round_pct || 0}%</div>` +
      (rows || `<div class="meta">还没有记录，开一局吧。</div>`);
  } catch (err) {
    $("#history").innerHTML = `<span class="meta">读取失败：${err.message}</span>`;
  }
}

async function loadConditions() {
  const sel = $("#condSelect");
  if (!sel) return;
  try {
    const d = await api("/api/conditions");
    sel.innerHTML = (d.items || [])
      .map((x) => `<option value="${x.id}">${x.name}</option>`)
      .join("");
    if (sel.options.length) countCondition();
  } catch (err) {
    sel.innerHTML = `<option value="">条件读取失败</option>`;
  }
}

async function countCondition() {
  const sel = $("#condSelect");
  if (!sel || !sel.value) return;
  const hint = sel.selectedOptions[0]?.textContent || "";
  try {
    const d = await api(`/api/conditions/${encodeURIComponent(sel.value)}/count`);
    $("#metaLine").textContent = `${hint}：命中 ${d.count} 只`;
  } catch (err) {
    $("#metaLine").textContent = `统计失败：${err.message}`;
  }
}

async function loadFormulas() {
  try {
    const d = await api("/api/formulas");
    S.formulas = d.items || [];
  } catch (err) {
    S.formulas = [];
  }
}

/* ------------------------------------------------------------ 播放 */

function stopPlay() {
  S.playing = false;
  if (S.timer) clearInterval(S.timer);
  S.timer = null;
  $("#btnPlay").textContent = "▶ 自动播放";
  $("#btnPlay").classList.remove("on");
}

function togglePlay() {
  if (S.playing) return stopPlay();
  if (!S.id || S.finished) return;
  S.playing = true;
  $("#btnPlay").textContent = "⏸ 暂停";
  $("#btnPlay").classList.add("on");
  const ms = Number($("#speed").value || 600);
  S.timer = setInterval(() => {
    if (!S.playing) return;
    if (S.state && S.state.bars_left <= 0) return stopPlay();
    step();
  }, ms);
}

/* ------------------------------------------------------------ 事件 */

$("#btnBlind").addEventListener("click", () => openSession({ mode: "blind" }));
$("#btnScreen").addEventListener("click", () => {
  const cond = $("#condSelect").value;
  if (!cond) return msg("先选一个条件", "err");
  openSession({ mode: "screen", condition: cond });
});
$("#condSelect").addEventListener("change", countCondition);
$("#btnCustom").addEventListener("click", () => {
  const code = ($("#codeInput").value || "").trim();
  if (!/^\d{6}$/.test(code)) return msg("请输入 6 位代码", "err");
  openSession({ mode: "custom", code });
});
$("#btnBuy").addEventListener("click", () => order("buy"));
$("#btnSell").addEventListener("click", () => order("sell"));
$("#btnHold").addEventListener("click", holdOne);
$("#btnPlay").addEventListener("click", togglePlay);
$("#btnFinish").addEventListener("click", finish);
$("#btnFormulaMgr").addEventListener("click", openFormulaMgr);
$("#fmClose").addEventListener("click", () => $("#fmModal").classList.add("hidden"));
$("#fmMask").addEventListener("click", () => $("#fmModal").classList.add("hidden"));
$("#fmSave").addEventListener("click", saveFormulaFromMgr);
$("#fmTest").addEventListener("click", testFormula);
$("#resultClose").addEventListener("click", () => $("#resultModal").classList.add("hidden"));
$("#resultMask").addEventListener("click", () => $("#resultModal").classList.add("hidden"));

document.addEventListener("keydown", (ev) => {
  if (["INPUT", "TEXTAREA", "SELECT"].includes(ev.target.tagName)) return;
  if (ev.code === "Space") { ev.preventDefault(); togglePlay(); }
  else if (ev.key === "b" || ev.key === "B") { ev.preventDefault(); order("buy"); }
  else if (ev.key === "s" || ev.key === "S") { ev.preventDefault(); order("sell"); }
});

(async () => {
  await loadLayout();
  bindGrips();
  await loadFormulas();
  try {
    const m = await api("/api/meta");
    $("#metaLine").textContent = `本地日线 ${m.tradable} 只`;
  } catch (err) {
    $("#metaLine").textContent = "读不到数据：" + err.message;
  }
  loadConditions();
  loadHistory();
})();
