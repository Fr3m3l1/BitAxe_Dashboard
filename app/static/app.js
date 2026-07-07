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
  // Parse a difficulty that may be raw ("745151943982") or suffixed ("745.15G").
  parseDiff(v) {
    if (v == null) return 0;
    const m = String(v).trim().match(/^([\d.]+)\s*([kKMGTPE]?)$/);
    if (!m) return 0;
    const mult = { k: 1e3, K: 1e3, M: 1e6, G: 1e9, T: 1e12, P: 1e15, E: 1e18 }[m[2]] || 1;
    return parseFloat(m[1]) * mult;
  },
  // Compact SI representation: 745151943982 -> "745.15 G"
  si(n, d = 2) {
    if (n == null || !isFinite(n) || n === 0) return n === 0 ? "0" : "—";
    const units = ["", "K", "M", "G", "T", "P", "E", "Z"];
    let i = 0, v = Math.abs(n);
    while (v >= 1000 && i < units.length - 1) { v /= 1000; i++; }
    return `${(Math.sign(n) * v).toFixed(v >= 100 ? 1 : d)}${i ? " " + units[i] : ""}`;
  },
  // Human duration from seconds, with cosmic context for absurd values.
  dur(sec) {
    if (sec == null || !isFinite(sec)) return "—";
    if (sec < 90) return `${sec.toFixed(0)} seconds`;
    if (sec < 5400) return `${(sec / 60).toFixed(0)} minutes`;
    if (sec < 172800) return `${(sec / 3600).toFixed(1)} hours`;
    if (sec < 63072000) return `${(sec / 86400).toFixed(1)} days`;
    const years = sec / 31557600;
    if (years < 1000) return `${years.toFixed(0)} years`;
    if (years < 1e6) return `${(years / 1000).toFixed(1)} thousand years`;
    if (years < 1e9) return `${(years / 1e6).toFixed(1)} million years`;
    const universe = years / 13.8e9;
    return `${(years / 1e9).toFixed(1)} billion years (${universe.toFixed(1)}× the age of the universe)`;
  },
  odds(p) {
    if (!p || p <= 0) return "—";
    return `1 in ${fmt.si(1 / p, 1)}`;
  },
  era(y) {
    if (y == null) return null;
    const year = Math.floor(y);
    const month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][Math.min(11, Math.floor((y - year) * 12))];
    return `${month} ${year}`;
  },
};

/* ---------------- tabs ---------------- */
document.querySelectorAll("nav button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("nav button").forEach((b) => b.classList.toggle("active", b === btn));
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.id === `tab-${btn.dataset.tab}`));
    if (btn.dataset.tab === "alerts") loadAlerts();
    if (btn.dataset.tab === "nerd") loadNerd();
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
    tile("Best difficulty", `${fmt.si(fmt.parseDiff(d.best_diff))}`,
      d.best_session_diff ? `session ${fmt.si(fmt.parseDiff(d.best_session_diff))}` : "") +
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

/* ---------------- nerd stats tab ---------------- */
async function loadNerd() {
  const el = document.getElementById("nerd-content");
  const m = currentMiner();
  if (!m) { el.innerHTML = `<div class="empty">No miner yet</div>`; return; }
  try {
    const d = await api(`/api/nerd?mac=${encodeURIComponent(m.mac)}`);
    if (d.error) { el.innerHTML = `<div class="empty">${d.error}</div>`; return; }
    const net = d.network;
    const sections = [];

    // --- block hunting ---
    let hunt = `<div class="tiles">`;
    if (d.exp_block_seconds) {
      hunt += `<div class="tile hero"><div class="label">Expected time to solo-find a block</div>
        <div class="value" style="font-size:34px">${fmt.dur(d.exp_block_seconds)}</div>
        <div class="sub">at ${fmt.num(d.hashrate_ghs, 0)} GH/s vs current network difficulty</div></div>`;
      hunt += tile("Odds per day", fmt.odds(d.block_odds_per_day), "chance of a block in 24h");
      hunt += tile("Odds per year", fmt.odds(d.block_odds_per_day * 365), "keep the dream alive");
    }
    if (d.share_of_network) {
      hunt += tile("Your slice of the network", `${(d.share_of_network * 100).toExponential(2)}<span class="unit">%</span>`,
        `the network ≈ ${fmt.si(1 / d.share_of_network, 1)} of your miner`);
    }
    hunt += `</div>`;
    sections.push(`<div class="card"><h2>🎯 Block hunting</h2>
      <p class="desc">Solo mining is a lottery where you buy ${fmt.si(d.hashrate_ghs * 1e9 || 0, 0)} tickets per second. These are your odds.</p>${hunt}</div>`);

    // --- best difficulty ---
    let bd = `<div class="tiles">`;
    bd += tile("All-time best share", fmt.si(d.best_diff),
      `exactly ${Math.round(d.best_diff).toLocaleString()}`);
    if (d.best_vs_network != null)
      bd += tile("Of a block", `${(d.best_vs_network * 100).toFixed(4)}<span class="unit">%</span>`,
        `a block needs ${fmt.si(net.difficulty)} — you're ${fmt.si(1 / d.best_vs_network, 0)}× short`);
    if (d.best_era_year)
      bd += tile("Time machine", `${fmt.era(d.best_era_year)}`,
        "this share would have solved a real block back then");
    if (d.exp_beat_best_seconds)
      bd += tile("New personal record in…", fmt.dur(d.exp_beat_best_seconds), "expected wait at current hashrate");
    bd += `</div><div class="tiles" style="margin-top:2px">`;
    bd += tile("Session best share", fmt.si(d.session_best_diff),
      `exactly ${Math.round(d.session_best_diff).toLocaleString()}`);
    if (d.exp_beat_session_seconds)
      bd += tile("Session record beaten in…", fmt.dur(d.exp_beat_session_seconds), "expected wait");
    if (d.session_best_era_year)
      bd += tile("Session time machine", `${fmt.era(d.session_best_era_year)}`, "when this was block-worthy");
    bd += `</div>`;
    sections.push(`<div class="card"><h2>🏆 Best difficulty</h2>
      <p class="desc">Every share is a dice roll; the best one shows how lucky you've been. Doubling your best takes as long again, on average.</p>${bd}</div>`);

    // --- network ---
    if (net) {
      let nw = `<div class="tiles">`;
      nw += tile("Network difficulty", fmt.si(net.difficulty), `exactly ${Math.round(net.difficulty).toLocaleString()}`);
      nw += tile("Network hashrate", `${fmt.si(net.network_hashrate)}<span class="unit">H/s</span>`, "");
      if (net.height) nw += tile("Block height", net.height.toLocaleString(), "");
      if (net.adjustment && net.adjustment.estimated_change_pct != null) {
        const a = net.adjustment;
        const chg = a.estimated_change_pct;
        nw += tile("Next difficulty adjustment",
          `<span class="delta ${chg >= 0 ? "down" : "up"}">${chg >= 0 ? "▲" : "▼"} ${Math.abs(chg).toFixed(2)}%</span>`,
          `${(a.progress_pct || 0).toFixed(1)}% through epoch · ${a.remaining_blocks?.toLocaleString() ?? "—"} blocks left` +
          (a.estimated_retarget_ts ? ` · ~${new Date(a.estimated_retarget_ts * 1000).toLocaleDateString()}` : ""));
      }
      if (net.halving_eta_seconds)
        nw += tile("Next halving", fmt.dur(net.halving_eta_seconds),
          `at block ${net.next_halving_height.toLocaleString()} (${net.halving_blocks_left.toLocaleString()} to go)`);
      nw += `</div>`;
      sections.push(`<div class="card"><h2>🌐 Bitcoin network</h2>
        <p class="desc">Live from mempool.space, refreshed every 10 minutes.</p>${nw}</div>`);
    } else {
      sections.push(`<div class="card"><h2>🌐 Bitcoin network</h2><p class="desc">Network data currently unavailable — retrying in the background.</p></div>`);
    }

    // --- the grind ---
    let gr = `<div class="tiles">`;
    if (d.lifetime_hashes) {
      gr += tile("Hashes computed", fmt.si(d.lifetime_hashes),
        `≈ ${d.lifetime_hashes.toExponential(2)} over ${fmt.dur(d.observed_seconds)} observed`);
      if (net) gr += tile("Bad luck insurance", fmt.si(d.lifetime_hashes / (net.difficulty * 4294967296) * 100, 4) + `<span class="unit">%</span>`,
        "of one expected block's work already done");
    }
    if (d.shares_24h) {
      gr += tile("Shares (24h)", d.shares_24h.toLocaleString(),
        d.hashrate_ghs ? `≈ ${fmt.si(d.hashrate_ghs * 1e9 * 86400 / d.shares_24h)} hashes per share` : "");
    }
    gr += `</div>`;
    sections.push(`<div class="card"><h2>⛏️ The grind</h2>
      <p class="desc">What your miner has actually chewed through (since this dashboard started recording).</p>${gr}</div>`);

    el.innerHTML = sections.join("");
  } catch (e) {
    console.error(e);
    el.innerHTML = `<div class="empty">Failed to load nerd stats</div>`;
  }
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
