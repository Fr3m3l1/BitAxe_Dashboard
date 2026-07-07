/* BitAxe Dashboard frontend */
"use strict";

const CSS = getComputedStyle(document.documentElement);
const C = {
  s1: CSS.getPropertyValue("--series-1").trim(),
  s2: CSS.getPropertyValue("--series-2").trim(),
  s3: CSS.getPropertyValue("--series-3").trim(),
  muted: CSS.getPropertyValue("--muted").trim(),
  grid: CSS.getPropertyValue("--grid").trim(),
  ink2: CSS.getPropertyValue("--ink-2").trim(),
  critical: CSS.getPropertyValue("--critical").trim(),
  warning: CSS.getPropertyValue("--warning").trim(),
  good: CSS.getPropertyValue("--good").trim(),
};

const state = {
  miners: [],
  selected: localStorage.getItem("selectedMiner") || null,
  hours: 6,
  settings: null,
  charts: {},
};

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (res.status === 401) { location.href = "/login"; throw new Error("unauthenticated"); }
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return res.json();
}

const fmt = {
  num: (v, d = 1) => (v == null ? "—" : Number(v).toFixed(d)),
  ts: (iso) => new Date(iso + "Z").toLocaleString([], { dateStyle: "short", timeStyle: "medium" }),
  timeShort(iso, hours) {
    const d = new Date(iso + "Z");
    if (hours > 48) return d.toLocaleString([], { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  },
  uptime(sec) {
    if (sec == null) return "—";
    const d = Math.floor(sec / 86400), h = Math.floor((sec % 86400) / 3600), m = Math.floor((sec % 3600) / 60);
    return d > 0 ? `${d}d ${h}h` : h > 0 ? `${h}h ${m}m` : `${m}m`;
  },
};

/* ---------------- tabs ---------------- */
document.querySelectorAll("nav button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("nav button").forEach((b) => b.classList.toggle("active", b === btn));
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.id === `tab-${btn.dataset.tab}`));
    if (btn.dataset.tab === "alerts") loadAlerts();
    if (btn.dataset.tab === "tuner") loadTunerTab();
    if (btn.dataset.tab === "settings") loadSettingsTab();
  });
});

document.getElementById("logout-btn").addEventListener("click", async () => {
  await fetch("/logout", { method: "POST" });
  location.href = "/login";
});

/* ---------------- overview ---------------- */
function currentMiner() {
  return state.miners.find((m) => m.mac === state.selected) || state.miners[0] || null;
}

function renderChips() {
  const el = document.getElementById("miner-chips");
  el.innerHTML = "";
  for (const m of state.miners) {
    const chip = document.createElement("button");
    chip.className = "chip" + (currentMiner() === m ? " active" : "");
    chip.innerHTML = `<span class="dot ${m.online ? "online" : "offline"}"></span>${m.hostname}`;
    chip.title = `${m.asic_model || ""} · last seen ${fmt.ts(m.last_seen)}`;
    chip.addEventListener("click", () => {
      state.selected = m.mac;
      localStorage.setItem("selectedMiner", m.mac);
      renderChips();
      renderTiles();
      loadHistory();
    });
    el.appendChild(chip);
  }
}

function tile(label, valueHtml, sub = "") {
  return `<div class="tile"><div class="label">${label}</div><div class="value">${valueHtml}</div>${sub ? `<div class="sub">${sub}</div>` : ""}</div>`;
}

function tempStatus(v, limit) {
  if (v == null) return C.muted;
  if (v > limit) return "var(--critical)";
  if (v > limit - 5) return "var(--warning)";
  return "var(--good)";
}

function renderTiles() {
  const m = currentMiner();
  const el = document.getElementById("tiles");
  if (!m || !m.latest) { el.innerHTML = `<div class="empty">No data yet — waiting for the collector…</div>`; return; }
  const d = m.latest;
  const s = state.settings ? state.settings.alerts : { temp_limit: 65, vr_temp_limit: 80 };

  const eff = d.power && d.hash_rate ? d.power / (d.hash_rate / 1000) : null;
  const rejTotal = (d.shares_accepted || 0) + (d.shares_rejected || 0);
  const rejRate = rejTotal ? (100 * (d.shares_rejected || 0)) / rejTotal : null;

  let hrDelta = "";
  if (d.expected_hash_rate && d.hash_rate != null) {
    const pct = (100 * (d.hash_rate - d.expected_hash_rate)) / d.expected_hash_rate;
    hrDelta = `<span class="delta ${pct >= 0 ? "up" : "down"}">${pct >= 0 ? "▲" : "▼"} ${Math.abs(pct).toFixed(1)}% vs expected</span>`;
  }

  el.innerHTML =
    `<div class="tile hero"><div class="label">Hashrate</div>
       <div class="value">${fmt.num(d.hash_rate, 0)}<span class="unit">GH/s</span></div>
       <div class="sub">${hrDelta || (d.expected_hash_rate ? `expected ${fmt.num(d.expected_hash_rate, 0)} GH/s` : "")}</div></div>` +
    tile("ASIC temp", `<span style="color:${tempStatus(d.temp, s.temp_limit)}">${fmt.num(d.temp)}<span class="unit">°C</span></span>`, `limit ${s.temp_limit}°C`) +
    tile("VR temp", `<span style="color:${tempStatus(d.vr_temp, s.vr_temp_limit)}">${fmt.num(d.vr_temp)}<span class="unit">°C</span></span>`, `limit ${s.vr_temp_limit}°C`) +
    tile("Power", `${fmt.num(d.power)}<span class="unit">W</span>`) +
    tile("Efficiency", `${fmt.num(eff)}<span class="unit">J/TH</span>`) +
    tile("Frequency", `${fmt.num(d.frequency, 0)}<span class="unit">MHz</span>`) +
    tile("Core voltage", `${fmt.num(d.core_voltage, 0)}<span class="unit">mV</span>`, d.core_voltage_actual ? `actual ${fmt.num(d.core_voltage_actual, 0)} mV` : "") +
    tile("Fan", `${d.fan_rpm != null ? d.fan_rpm : "—"}<span class="unit">rpm</span>`, d.fan_speed != null ? `${d.fan_speed}%${d.auto_fan ? " · auto" : ""}` : "") +
    tile("Shares", `${d.shares_accepted != null ? d.shares_accepted.toLocaleString() : "—"}`, rejRate != null ? `${d.shares_rejected || 0} rejected (${rejRate.toFixed(2)}%)` : "") +
    tile("Best difficulty", `${d.best_diff || "—"}`, d.best_session_diff ? `session ${d.best_session_diff}` : "") +
    tile("Uptime", fmt.uptime(d.uptime_seconds), d.wifi_rssi != null ? `WiFi ${d.wifi_rssi} dBm` : "") +
    tile("Pool", d.using_fallback ? `<span style="color:var(--warning)">fallback</span>` : "primary", d.stratum_url || "");
}

async function loadOverview() {
  try {
    const data = await api("/api/overview");
    state.miners = data.miners;
    if (!state.selected && state.miners.length) state.selected = state.miners[0].mac;
    renderChips();
    renderTiles();
    const badge = document.getElementById("alerts-badge");
    badge.textContent = `${data.alerts_24h} alerts`;
    badge.classList.toggle("show", data.alerts_24h > 0);
    document.getElementById("last-update").textContent =
      currentMiner()?.latest ? `updated ${fmt.timeShort(currentMiner().last_seen, 1)}` : "";
  } catch (e) { console.error(e); }
}

/* ---------------- charts ---------------- */
const chartBase = {
  animation: false,
  maintainAspectRatio: false,
  interaction: { mode: "index", intersect: false },
  plugins: {
    legend: { display: false, labels: { color: C.ink2, boxWidth: 12, boxHeight: 12, usePointStyle: true, pointStyle: "line" } },
    tooltip: { backgroundColor: "#232322", borderColor: "rgba(255,255,255,0.1)", borderWidth: 1, titleColor: "#fff", bodyColor: C.ink2 },
  },
  scales: {
    x: { ticks: { color: C.muted, maxTicksLimit: 7, maxRotation: 0 }, grid: { color: C.grid, drawTicks: false }, border: { display: false } },
    y: { ticks: { color: C.muted, maxTicksLimit: 6 }, grid: { color: C.grid, drawTicks: false }, border: { display: false } },
  },
};

function lineDS(label, color, opts = {}) {
  return {
    label,
    data: [],
    borderColor: color,
    backgroundColor: color + "1a", // ~10% wash
    borderWidth: 2,
    pointRadius: 0,
    pointHoverRadius: 4,
    pointHoverBackgroundColor: color,
    tension: 0.25,
    fill: opts.fill || false,
    borderDash: opts.dash || undefined,
    ...opts.extra,
  };
}

function makeCharts() {
  const mk = (id, datasets, opts = {}) => {
    const options = JSON.parse(JSON.stringify(chartBase));
    options.plugins.legend.display = datasets.length > 1;
    if (opts.suggestedMin != null) options.scales.y.suggestedMin = opts.suggestedMin;
    const chart = new Chart(document.getElementById(id), { type: "line", data: { labels: [], datasets }, options });
    // JSON round-trip drops function-valued options; none used, colors are strings.
    chart.options.plugins.legend.labels.usePointStyle = true;
    chart.options.plugins.legend.labels.pointStyle = "line";
    chart.options.plugins.legend.labels.color = C.ink2;
    return chart;
  };

  state.charts.hashrate = mk("c-hashrate", [
    lineDS("Actual", C.s1, { fill: true }),
    lineDS("Expected", C.muted, { dash: [4, 4] }),
  ]);
  state.charts.temp = mk("c-temp", [
    lineDS("ASIC", C.s1),
    lineDS("VR", C.s2),
    lineDS("Limit", C.critical, { dash: [4, 4] }),
  ]);
  state.charts.power = mk("c-power", [lineDS("Power", C.s1, { fill: true })]);
  state.charts.eff = mk("c-eff", [lineDS("Efficiency", C.s1)]);
  state.charts.freq = mk("c-freq", [lineDS("Frequency", C.s1, { extra: { stepped: true } })]);
  state.charts.volt = mk("c-volt", [
    lineDS("Set", C.s1, { extra: { stepped: true } }),
    lineDS("Actual", C.s2),
  ]);
}

async function loadHistory() {
  const m = currentMiner();
  if (!m) return;
  const chartsEl = document.getElementById("charts");
  chartsEl.classList.add("loading");
  try {
    const [hist, stats] = await Promise.all([
      api(`/api/history?mac=${encodeURIComponent(m.mac)}&hours=${state.hours}`),
      api(`/api/stats?mac=${encodeURIComponent(m.mac)}&hours=${state.hours}`),
    ]);
    const pts = hist.points;
    const labels = pts.map((p) => fmt.timeShort(p.ts, state.hours));
    const tempLimit = state.settings ? state.settings.alerts.temp_limit : 65;

    const set = (chart, seriesArr) => {
      chart.data.labels = labels;
      seriesArr.forEach((s, i) => (chart.data.datasets[i].data = s));
      chart.update();
    };

    set(state.charts.hashrate, [pts.map((p) => p.hash_rate), pts.map((p) => p.expected_hash_rate)]);
    set(state.charts.temp, [pts.map((p) => p.temp), pts.map((p) => p.vr_temp), pts.map(() => tempLimit)]);
    set(state.charts.power, [pts.map((p) => p.power)]);
    set(state.charts.eff, [pts.map((p) => (p.power && p.hash_rate ? p.power / (p.hash_rate / 1000) : null))]);
    set(state.charts.freq, [pts.map((p) => p.frequency)]);
    set(state.charts.volt, [pts.map((p) => p.core_voltage), pts.map((p) => p.core_voltage_actual)]);

    if (stats.n) {
      document.getElementById("stats-hint").textContent =
        `${state.hours}h: avg ${fmt.num(stats.hash_rate.avg, 0)} GH/s · ` +
        `${fmt.num(stats.efficiency_avg)} J/TH · temp ${fmt.num(stats.temp.min, 0)}–${fmt.num(stats.temp.max, 0)}°C · ` +
        `${stats.shares.accepted.toLocaleString()} shares`;
    } else {
      document.getElementById("stats-hint").textContent = "";
    }
  } catch (e) { console.error(e); }
  chartsEl.classList.remove("loading");
}

document.querySelectorAll(".range-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".range-btn").forEach((b) => b.classList.toggle("active", b === btn));
    state.hours = Number(btn.dataset.hours);
    loadHistory();
  });
});

/* ---------------- alerts tab ---------------- */
async function loadAlerts() {
  const body = document.getElementById("alerts-body");
  try {
    const data = await api("/api/alerts?hours=168");
    if (!data.alerts.length) { body.innerHTML = `<tr><td colspan="5" class="empty">No alerts in the last 7 days 🎉</td></tr>`; return; }
    body.innerHTML = data.alerts.map((a) => `
      <tr>
        <td style="white-space:nowrap">${fmt.ts(a.ts)}</td>
        <td>${a.hostname || "—"}</td>
        <td><span class="sev ${a.severity}">${a.severity}</span></td>
        <td>${a.type}</td>
        <td>${a.message.replace(/<[^>]+>/g, "")}</td>
      </tr>`).join("");
  } catch (e) { body.innerHTML = `<tr><td colspan="5" class="empty">Failed to load alerts</td></tr>`; }
}

/* ---------------- settings helpers ---------------- */
const ALERT_FIELDS = ["temp_limit", "vr_temp_limit", "power_limit", "hashrate_drop_pct", "reject_rate_limit",
  "offline_minutes", "cooldown_minutes", "daily_summary_hour"];
const ALERT_CHECKS = ["telegram_enabled", "daily_summary_enabled", "achievement_alerts"];
const TUNER_FIELDS = ["target_temp", "max_temp", "max_vr_temp", "max_power", "freq_min", "freq_max", "freq_step",
  "volt_min", "volt_max", "volt_step", "settle_seconds", "dwell_seconds"];
const TUNER_CHECKS = ["enabled", "allow_restart"];

async function fetchSettings() {
  state.settings = await api("/api/settings");
  return state.settings;
}

function fillForm(prefix, fields, checks, values) {
  for (const f of fields) document.getElementById(`${prefix}_${f}`).value = values[f];
  for (const c of checks) document.getElementById(`${prefix}_${c}`).checked = !!values[c];
}

function readForm(prefix, fields, checks) {
  const out = {};
  for (const f of fields) out[f] = Number(document.getElementById(`${prefix}_${f}`).value);
  for (const c of checks) out[c] = document.getElementById(`${prefix}_${c}`).checked;
  return out;
}

function flashNote(id, ok, msg) {
  const el = document.getElementById(id);
  el.textContent = msg || (ok ? "Saved ✓" : "Save failed");
  el.classList.toggle("err", !ok);
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2500);
}

/* ---------------- tuner tab ---------------- */
async function loadTunerTab() {
  try {
    const s = await fetchSettings();
    fillForm("t", TUNER_FIELDS, TUNER_CHECKS, s.tuner);
    document.getElementById("t_mode").value = s.tuner.mode;
    const badge = document.getElementById("tuner-badge");
    badge.textContent = s.tuner.enabled ? "on" : "off";
    badge.className = `tuner-state-badge ${s.tuner.enabled ? "on" : "off"}`;

    const events = await api("/api/tuner/events");
    const body = document.getElementById("tuner-events-body");
    if (events.events.length) {
      body.innerHTML = events.events.map((e) => `
        <tr>
          <td style="white-space:nowrap">${fmt.ts(e.ts)}</td>
          <td>${e.hostname || "—"}</td>
          <td>${e.action}</td>
          <td class="num">${e.frequency != null ? fmt.num(e.frequency, 0) : "—"}</td>
          <td class="num">${e.core_voltage != null ? fmt.num(e.core_voltage, 0) : "—"}</td>
          <td>${e.reason || ""}</td>
        </tr>`).join("");
    } else {
      body.innerHTML = `<tr><td colspan="6" class="empty">No tuner activity yet</td></tr>`;
    }
  } catch (e) { console.error(e); }
}

document.getElementById("save-tuner").addEventListener("click", async () => {
  const tuner = readForm("t", TUNER_FIELDS, TUNER_CHECKS);
  tuner.mode = document.getElementById("t_mode").value;
  try {
    await api("/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tuner }) });
    flashNote("tuner-note", true);
    loadTunerTab();
  } catch (e) { flashNote("tuner-note", false); }
});

/* ---------------- settings tab ---------------- */
async function loadSettingsTab() {
  try {
    const s = await fetchSettings();
    fillForm("a", ALERT_FIELDS, ALERT_CHECKS, s.alerts);
    document.getElementById("test-telegram").disabled = !s.telegram_configured;
    if (!s.telegram_configured) document.getElementById("test-telegram").title = "Set TELEGRAM_TOKEN / TELEGRAM_CHAT_ID on the server";
  } catch (e) { console.error(e); }
}

document.getElementById("save-alerts").addEventListener("click", async () => {
  const alerts = readForm("a", ALERT_FIELDS, ALERT_CHECKS);
  try {
    await api("/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ alerts }) });
    flashNote("alerts-note", true);
    renderTiles();
  } catch (e) { flashNote("alerts-note", false); }
});

document.getElementById("test-telegram").addEventListener("click", async () => {
  try {
    const r = await api("/api/telegram/test", { method: "POST" });
    flashNote("alerts-note", r.ok, r.ok ? "Test sent ✓" : "Test failed");
  } catch (e) { flashNote("alerts-note", false, "Test failed"); }
});

/* ---------------- boot ---------------- */
async function boot() {
  makeCharts();
  await fetchSettings().catch(() => {});
  await loadOverview();
  await loadHistory();
  setInterval(loadOverview, 10_000);
  setInterval(loadHistory, 60_000);
}
boot();
