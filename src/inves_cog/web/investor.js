/* Investor page interactions. No network, no framework. */
function textW(s, fs) {
  fs = fs || 11;
  var w = 0;
  for (var i = 0; i < s.length; i++) {
    var ch = s.charCodeAt(i);
    w += (ch >= 0x3000 && ch <= 0x9fff) || (ch >= 0xff00 && ch <= 0xffef) ? fs : fs * 0.61;
  }
  return w;
}
function usd(v) {
  if (v == null) return "暂缺";
  return "$" + Number(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function ruler(h, w) {
  w = w || 470;
  var pts = [];
  if (h.stop) pts.push({ k: "stop", n: h.stop.n, p: h.stop.p });
  (h.tp || []).forEach(function (x) { pts.push({ k: "tp", n: x.n, p: x.p, reached: x.reached }); });
  if (h.ma200 && h.type !== "观察波段仓") pts.push({ k: "ref", n: "200 日线", p: h.ma200 });
  if (h.cost != null) pts.push({ k: "cost", n: "成本", p: h.cost });
  pts.push({ k: "cur", n: "现价", p: h.px });
  var lo = Math.min.apply(null, pts.map(function (x) { return x.p; }));
  var hi = Math.max.apply(null, pts.map(function (x) { return x.p; }));
  var pad = (hi - lo) * 0.05 || 1;
  lo -= pad; hi += pad;
  var L = 10, R = w - 10, Y = 54, H = 112;
  function X(p) { return L + (p - lo) / (hi - lo) * (R - L); }
  var lanes = { t0: 32, t1: 19, t2: 7, b0: 78, b1: 92, b2: 106 };
  var used = { t0: [], t1: [], t2: [], b0: [], b1: [], b2: [] };
  function free(ln, a, b) { return used[ln].every(function (pair) { return b + 6 < pair[0] || a > pair[1] + 6; }); }
  var trig = pts.filter(function (x) { return (x.k === "stop" || x.k === "tp") && !x.reached; });
  var near = null;
  trig.forEach(function (x) {
    var d = Math.abs(x.p - h.px) / h.px;
    if (!near || d < near.d) near = Object.assign({}, x, { d: d });
  });
  var svg = '<svg width="' + w + '" height="' + H + '" viewBox="0 0 ' + w + " " + H + '" style="max-width:100%;height:auto" role="img">';
  svg += '<line x1="' + L + '" y1="' + Y + '" x2="' + R + '" y2="' + Y + '" stroke="#E2DDD3" stroke-width="4" stroke-linecap="round"/>';
  var distTxt = "";
  if (near) {
    var c = near.k === "stop" ? "var(--r-hi-line)" : "var(--tp-line)";
    var x1 = X(h.px), x2 = X(near.p), dist = (near.p / h.px - 1) * 100;
    svg += '<line x1="' + x1 + '" y1="' + Y + '" x2="' + x2 + '" y2="' + Y + '" stroke="' + c + '" stroke-width="5" stroke-linecap="round" opacity=".85"/>';
    var lab = (dist > 0 ? "+" : "−") + Math.abs(dist).toFixed(1) + "%";
    var lw = textW(lab), mid = (x1 + x2) / 2, a = Math.max(2, Math.min(w - 2 - lw, mid - lw / 2));
    distTxt = '<text x="' + a + '" y="' + (Y - 8) + '" font-size="11" fill="' + c + '" font-weight="700" paint-order="stroke" stroke="#fff" stroke-width="3">' + lab + "</text>";
  } else {
    var ref = pts.filter(function (x) { return x.k === "ref"; })[0];
    if (ref) {
      var rx1 = X(h.px), rx2 = X(ref.p), below = h.px < ref.p;
      var rdist = below ? (1 - h.px / ref.p) * 100 : (1 - ref.p / h.px) * 100;
      var warm = below || rdist < 10;
      var rc = warm ? "var(--r-mid-line)" : "#B9B2A4";
      svg += '<line x1="' + rx1 + '" y1="' + Y + '" x2="' + rx2 + '" y2="' + Y + '" stroke="' + rc + '" stroke-width="' + (warm ? 4 : 3) + '" stroke-dasharray="5 3" opacity=".8"/>';
      var rlab = below ? "已低于 200 日线 " + rdist.toFixed(1) + "%" : "再跌 " + rdist.toFixed(1) + "% 跌破 200 日线";
      var rlw = textW(rlab), rmid = (rx1 + rx2) / 2, ra = Math.max(2, Math.min(w - 2 - rlw, rmid - rlw / 2));
      distTxt = '<text x="' + ra + '" y="' + (Y - 8) + '" font-size="11" fill="' + (warm ? "var(--r-mid)" : "var(--ref)") + '" font-weight="' + (warm ? 700 : 400) + '" paint-order="stroke" stroke="#fff" stroke-width="3">' + rlab + "</text>";
    }
  }
  var pref = {
    cur: ["b0", "b1", "b2", "t0"], cost: ["b0", "b1", "b2", "t0", "t1"], ref: ["b0", "b1", "b2", "t0", "t1", "t2"],
    stop: ["t0", "t1", "t2", "b0", "b1", "b2"], tp: ["t0", "t1", "t2", "b0", "b1", "b2"]
  };
  var order = pts.map(function (x) { return Object.assign({}, x, { x: X(x.p) }); });
  order.sort(function (a, b) { return a.k === "cur" ? -1 : b.k === "cur" ? 1 : a.x - b.x; });
  order.forEach(function (o) {
    o.lab = o.n + " " + usd(o.p) + (o.reached ? " ✓" : "");
    var lw = textW(o.lab);
    var a = Math.max(2, Math.min(w - 2 - lw, o.x - lw / 2));
    o.lane = pref[o.k].filter(function (ln) { return free(ln, a, a + lw); })[0] || pref[o.k][pref[o.k].length - 1];
    used[o.lane].push([a, a + lw]);
    o.a = a;
  });
  order.forEach(function (o) {
    var col = o.k === "stop" ? "var(--r-hi)" : o.k === "tp" ? "var(--tp)" : o.k === "cur" ? "var(--ink)" : "var(--ref)";
    var ly = lanes[o.lane], top = o.lane[0] === "t";
    svg += '<line x1="' + o.x + '" y1="' + Y + '" x2="' + o.x + '" y2="' + (top ? ly + 3 : ly - 11) + '" stroke="' + col + '" stroke-width="1" ' + (o.k === "ref" ? 'stroke-dasharray="2 2" ' : "") + 'opacity=".55"/>';
    if (o.k === "ref") svg += '<line x1="' + o.x + '" y1="' + (Y - 10) + '" x2="' + o.x + '" y2="' + (Y + 10) + '" stroke="' + col + '" stroke-width="2" stroke-dasharray="3 2"/>';
    else svg += '<circle cx="' + o.x + '" cy="' + Y + '" r="' + (o.k === "cur" ? 6 : 4.5) + '" fill="' + (o.k === "cur" ? "#1F2A2A" : (o.reached ? "#fff" : col)) + '" stroke="' + col + '" stroke-width="' + (o.reached ? 2 : 0) + '"/>';
    svg += '<text x="' + o.a + '" y="' + ly + '" font-size="11" fill="' + col + '"' + (o.k === "cur" ? ' font-weight="700"' : "") + ">" + o.lab + "</text>";
  });
  return svg + distTxt + "</svg>";
}
function paintRulers() {
  document.querySelectorAll("[data-ruler]").forEach(function (el) {
    var spec = JSON.parse(el.getAttribute("data-ruler"));
    var width = el.clientWidth || 470;
    if (width < 280) width = innerWidth < 760 ? innerWidth - 44 : 470;
    el.innerHTML = ruler(spec, Math.round(width));
  });
}
function toggleRow(t, force) {
  var d = document.getElementById("det-" + t);
  var r = document.getElementById("row-" + t);
  if (!d || !r) return;
  var on = force == null ? !d.classList.contains("show") : force;
  d.classList.toggle("show", on);
  r.classList.toggle("open", on);
}
function bindAccount() {
  document.querySelectorAll("[data-row]").forEach(function (row) {
    row.onclick = function () { toggleRow(row.getAttribute("data-row")); };
  });
  document.querySelectorAll("[data-close]").forEach(function (node) {
    node.onclick = function (event) { event.stopPropagation(); toggleRow(node.getAttribute("data-close"), false); };
  });
  document.querySelectorAll("[data-go]").forEach(function (node) {
    node.onclick = function () {
      var t = node.getAttribute("data-go");
      if (!document.getElementById("row-" + t)) return;
      toggleRow(t, true);
      var row = document.getElementById("row-" + t);
      row.scrollIntoView({ block: "center" });
      var det = document.getElementById("det-" + t);
      det.classList.remove("flash");
      void det.offsetWidth;
      det.classList.add("flash");
    };
  });
  var hash = (location.hash || "").replace("#", "").toUpperCase();
  if (hash && document.getElementById("row-" + hash)) {
    toggleRow(hash, true);
    document.getElementById("row-" + hash).scrollIntoView({ block: "start" });
  }
}
function bindIntra() {
  document.querySelectorAll("[data-m]").forEach(function (button) {
    button.onclick = function () {
      var on = button.getAttribute("data-m") === "intra";
      document.body.classList.toggle("intra", on);
      document.querySelectorAll("[data-m]").forEach(function (item) {
        item.classList.toggle("on", item === button);
      });
    };
  });
}
function cellValue(row, key) {
  var raw = row.getAttribute("data-" + key);
  if (raw == null || raw === "") return null;
  var num = Number(raw);
  return Number.isNaN(num) ? raw : num;
}
function bindStocks() {
  var body = document.getElementById("stable");
  if (!body) return;
  var state = { k: "all", theme: "", q: "", c: "chg", d: 1 };
  function apply() {
    var rows = Array.prototype.slice.call(body.querySelectorAll("tr[data-ticker]"));
    rows.forEach(function (row) {
      var ok = state.k === "all"
        || (state.k === "held" && row.getAttribute("data-held") === "1")
        || (state.k === "buy" && row.getAttribute("data-buy") === "1")
        || (state.k === "move" && row.getAttribute("data-move") === "1")
        || (state.k === "crowd" && row.getAttribute("data-crowd") === "1");
      var theme = row.getAttribute("data-theme") || "";
      var ticker = row.getAttribute("data-ticker") || "";
      if (state.theme && theme !== state.theme) ok = false;
      if (state.q && ticker.indexOf(state.q) < 0) ok = false;
      row.hidden = !ok;
    });
    var shown = rows.filter(function (row) { return !row.hidden; });
    shown.sort(function (a, b) {
      var x = cellValue(a, state.c), y = cellValue(b, state.c);
      if (x == null) return 1;
      if (y == null) return -1;
      if (x > y) return state.d;
      if (x < y) return -state.d;
      return 0;
    });
    shown.forEach(function (row) { body.appendChild(row); });
    var count = document.getElementById("scount");
    if (count) count.textContent = shown.length + " / " + rows.length;
  }
  document.querySelectorAll("[data-sf]").forEach(function (button) {
    button.onclick = function () {
      state.k = button.getAttribute("data-sf");
      document.querySelectorAll("[data-sf]").forEach(function (item) { item.classList.toggle("on", item === button); });
      apply();
    };
  });
  var theme = document.getElementById("sth");
  if (theme) theme.onchange = function () { state.theme = theme.value; apply(); };
  var query = document.getElementById("sq");
  if (query) query.oninput = function () { state.q = query.value.toUpperCase(); apply(); };
  document.querySelectorAll("[data-sc]").forEach(function (head) {
    head.onclick = function () {
      var key = head.getAttribute("data-sc");
      state.d = state.c === key ? -state.d : 1;
      state.c = key;
      apply();
    };
  });
  document.querySelectorAll("[data-th]").forEach(function (row) {
    row.onclick = function () {
      var name = row.getAttribute("data-th");
      var extra = row.nextElementSibling;
      if (extra && extra.classList.contains("members")) extra.hidden = !extra.hidden;
    };
  });
  document.querySelectorAll("[data-only]").forEach(function (link) {
    link.onclick = function (event) {
      event.preventDefault();
      event.stopPropagation();
      state.theme = link.getAttribute("data-only");
      if (theme) theme.value = state.theme;
      apply();
    };
  });
}
function bindMore() {
  document.querySelectorAll("[data-more]").forEach(function (link) {
    link.onclick = function () {
      var list = document.getElementById("rmore-list");
      if (list) list.hidden = false;
      link.remove();
    };
  });
}
function bindFold() {
  document.querySelectorAll("[data-ev]").forEach(function (head) {
    head.onclick = function () { head.parentElement.classList.toggle("open"); };
  });
  document.querySelectorAll("[data-stat]").forEach(function (card) {
    card.onclick = function () { card.classList.toggle("open"); };
  });
}
function bindHoldings() {
  var list = document.getElementById("hlist");
  if (!list) return;
  var state = { k: "all", s: "risk" };
  function rows() { return Array.prototype.slice.call(list.querySelectorAll("[data-row]")); }
  function show() {
    rows().forEach(function (row) {
      var lv = row.getAttribute("data-lv") || "";
      var kind = row.getAttribute("data-kind") || "";
      var ok = state.k === "all"
        || (state.k === "down" && (lv === "hi" || lv === "mid"))
        || (state.k === "tp" && row.getAttribute("data-tp") === "1")
        || (state.k === "core" && kind !== "观察波段仓")
        || (state.k === "swing" && kind === "观察波段仓");
      row.hidden = !ok;
      var det = document.getElementById("det-" + row.getAttribute("data-row"));
      if (det) det.hidden = !ok;
    });
    var shown = rows().filter(function (row) { return !row.hidden; });
    shown.sort(function (a, b) {
      if (state.s === "pnl") return Number(b.getAttribute("data-pnl") || 0) - Number(a.getAttribute("data-pnl") || 0);
      if (state.s === "day") return Number(a.getAttribute("data-day") || 99) - Number(b.getAttribute("data-day") || 99);
      return Number(a.getAttribute("data-rank") || 9) - Number(b.getAttribute("data-rank") || 9);
    });
    shown.forEach(function (row) {
      list.appendChild(row);
      var det = document.getElementById("det-" + row.getAttribute("data-row"));
      if (det) list.appendChild(det);
    });
  }
  document.querySelectorAll("[data-hf]").forEach(function (button) {
    button.onclick = function () {
      state.k = button.getAttribute("data-hf");
      document.querySelectorAll("[data-hf]").forEach(function (item) { item.classList.toggle("on", item === button); });
      show();
    };
  });
  document.querySelectorAll("[data-s]").forEach(function (button) {
    button.onclick = function () {
      state.s = button.getAttribute("data-s");
      document.querySelectorAll("[data-s]").forEach(function (item) { item.classList.toggle("on", item === button); });
      show();
    };
  });
}
function boot() {
  paintRulers();
  bindAccount();
  bindHoldings();
  bindIntra();
  bindStocks();
  bindFold();
  bindMore();
}
if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", boot);
  window.addEventListener("resize", paintRulers);
}
if (typeof module !== "undefined") module.exports = { ruler: ruler, textW: textW };

/* B-064: news language toggle, feed expand, auto-refresh. */
(function () {
  var KEY = "news-lang";
  function apply(lang) {
    var zh = lang === "zh";
    document.querySelectorAll(".nzh").forEach(function (e) { e.hidden = !zh; });
    document.querySelectorAll(".nen").forEach(function (e) { e.hidden = zh; });
    var b = document.getElementById("lang-toggle");
    if (b) b.textContent = zh ? "中文 / 英文" : "英文 / 中文";
  }
  window.__setLang = function () {
    var cur = localStorage.getItem(KEY) === "en" ? "zh" : "en";
    localStorage.setItem(KEY, cur);
    apply(cur);
  };
  apply(localStorage.getItem(KEY) === "en" ? "en" : "zh");
          if (location.hash.indexOf("#theme-") === 0) {
            var row = doc.getElementById(location.hash.slice(1));
            var live = document.getElementById(location.hash.slice(1));
            if (live && !live.classList.contains("open")) live.click();
          }

  var more = document.querySelector("[data-feed-more]");
  if (more) {
    more.addEventListener("click", function () {
      document.querySelectorAll("#feed .nrow.x").forEach(function (e) { e.hidden = false; });
      more.remove();
    });
  }

  var meta = document.querySelector('meta[name="refresh-today"]');
  if (meta) {
    setInterval(function () {
      var et = new Date(new Date().toLocaleString("en-US", { timeZone: "America/New_York" }));
      if (et.getHours() >= 20) return;
      fetch(location.href, { credentials: "same-origin" })
        .then(function (r) { return r.text(); })
        .then(function (html) {
          var doc = new DOMParser().parseFromString(html, "text/html");
          ["movers", "themes", "feed", "mstrip", "sstrip"].forEach(function (id) {
            var oldEl = document.getElementById(id), newEl = doc.getElementById(id);
            if (oldEl && newEl) oldEl.innerHTML = newEl.innerHTML;
          });
          apply(localStorage.getItem(KEY) === "en" ? "en" : "zh");
          if (location.hash.indexOf("#theme-") === 0) {
            var row = doc.getElementById(location.hash.slice(1));
            var live = document.getElementById(location.hash.slice(1));
            if (live && !live.classList.contains("open")) live.click();
          }
        })
        .catch(function () {});
    }, 60 * 1000);
  }
})();

// B-073 search box: Enter jumps to /search; /search embeds candidates inline.
(function () {
  var q = document.getElementById("q");
  if (!q) return;
  q.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && q.value.trim()) {
      location.href = "/search?q=" + encodeURIComponent(q.value.trim());
    }
  });
})();

// B-074 §1: lightweight-charts daily OHLC + volume + MA50/200 + markers + 当日 tab
var InvestorChart = (function () {
  var chart, candle, vol, ma50, ma200, markerApi, rows, marks, intraday;

  function ma(win, arr) {
    var out = [];
    for (var i = 0; i < arr.length; i++) {
      var s = 0, c = 0;
      for (var j = Math.max(0, i - win + 1); j <= i; j++) { s += arr[j].c; c++; }
      out.push({ time: arr[i].d, value: s / c });
    }
    return out;
  }

  function setRange(k) {
    if (k === "day") {
      if (!intraday.length) return;
      var pts = intraday.map(function (p) { return { time: Math.floor(new Date(p.t).getTime() / 1000), value: p.p }; });
      candle.setData([]); vol.setData([]); ma50.setData([]); ma200.setData([]);
      markerApi.setMarkers([]);
      if (!chart._line) chart._line = chart.addSeries(LightweightCharts.LineSeries, { color: "#4a7", lineWidth: 2 });
      chart._line.setData(pts);
      chart.timeScale().fitContent();
      return;
    }
    if (chart._line) chart._line.setData([]);
    var sub = k > 0 ? rows.slice(-k) : rows;
    candle.setData(sub.map(function (r) {
      return { time: r.d, open: r.o || r.c, high: r.h || r.c, low: r.l || r.c, close: r.c };
    }));
    vol.setData(sub.map(function (r) {
      return { time: r.d, value: r.v || 0, color: r.c >= (r.o || r.c) ? "rgba(38,140,90,.4)" : "rgba(196,60,60,.4)" };
    }));
    ma50.setData(ma(50, sub)); ma200.setData(ma(200, sub));
    markerApi.setMarkers(sub.map(function (r) {
      var mk = marks[r.d];
      return mk ? { time: r.d, position: "belowBar", color: mk === "财报" ? "#2f7" : "#e55", shape: "circle", text: mk } : null;
    }).filter(Boolean));
    chart.timeScale().fitContent();
  }

  function init() {
    var el = document.getElementById("dchart");
    if (!el || !window.LightweightCharts) return;
    rows = JSON.parse(el.dataset.rows || "[]");
    marks = JSON.parse(el.dataset.marks || "{}");
    intraday = JSON.parse(el.dataset.intraday || "[]");
    if (!rows.length) return;
    chart = LightweightCharts.createChart(el, { height: 360, layout: { attributionLogo: true },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
      rightPriceScale: { visible: true }, timeScale: { rightOffset: 4 } });
    candle = chart.addSeries(LightweightCharts.CandlestickSeries);
    ma50 = chart.addSeries(LightweightCharts.LineSeries, { color: "#3af", lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    ma200 = chart.addSeries(LightweightCharts.LineSeries, { color: "#999", lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    markerApi = LightweightCharts.createSeriesMarkers(candle, []);
    vol = chart.addSeries(LightweightCharts.HistogramSeries, { priceScaleId: "vol", priceFormat: { type: "volume" }, lastValueVisible: false });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });
    chart.subscribeCrosshairMove(function (p) {
      var lg = document.getElementById("dchart-legend");
      if (!lg) return;
      var d = p.seriesData ? p.seriesData.get(candle) : null;
      lg.textContent = d ? p.time + "  开 " + d.open.toFixed(2) + " 高 " + d.high.toFixed(2) + " 低 " + d.low.toFixed(2) + " 收 " + d.close.toFixed(2) + " 涨跌 " + ((d.close / d.open - 1) * 100).toFixed(1) + "%" : "";
    });
    setRange(132);
  }

  return {
    range: function (btn, k) {
      setRange(k);
      btn.parentElement.querySelectorAll(".rc").forEach(function (b) { b.classList.toggle("on", b === btn); });
    },
    init: init
  };
})();
document.addEventListener("DOMContentLoaded", InvestorChart.init);
