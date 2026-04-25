"use strict";

/* -------------------------------------------------------------------
 * operad dashboard - client state + renderers
 * One-file app: state, event stream (SSE), view rendering, SVG charts.
 * ------------------------------------------------------------------*/

mermaid.initialize({ startOnLoad: false, theme: "dark", themeVariables: {
  background: "#12151e",
  primaryColor: "#1f2432",
  primaryTextColor: "#e7e9f1",
  primaryBorderColor: "#46a7ff",
  lineColor: "#5a6275",
  secondaryColor: "#2a1f4a",
  tertiaryColor: "#1b2e3f",
}});

const $ = (id) => document.getElementById(id);

/* ---------- state ---------- */

const state = {
  runs: new Map(),                 // run_id -> summary object (from /runs)
  currentRunId: null,
  currentTab: "overview",
  filter: "all",                   // all | algorithms | agents
  autoFollow: true,
  eventsFollow: true,
  eventKindFilter: "all",          // all | agent | algo | error
  eventSearch: "",
  selectedEventIdx: -1,            // index into current run's events (full list index)
  slotOccupancy: [],
  costTotals: {},
  globalStats: null,
  latestEnvelope: null,
  liveGenerations: [],             // generation envelopes accumulated in-browser
  runEvents: new Map(),            // run_id -> recent events array (fetched on select)
  runSummaries: new Map(),         // run_id -> full summary payload
};

/* ---------- connection ---------- */

function fmtTime(ts) {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleTimeString();
}
function fmtDuration(ms) {
  if (ms == null || !isFinite(ms)) return "—";
  if (ms < 1000) return `${ms.toFixed(0)} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(2)} s`;
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}m${s % 60}s`;
}
function fmtNum(n) {
  if (n == null) return "—";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "k";
  return String(n);
}
function fmtCost(usd) {
  if (usd == null) return "$0.00";
  if (usd >= 100) return `$${usd.toFixed(2)}`;
  if (usd >= 1) return `$${usd.toFixed(3)}`;
  return `$${usd.toFixed(4)}`;
}
function shortId(id) { return String(id || "").slice(0, 8); }

function connect() {
  const es = new EventSource("/stream");
  es.addEventListener("open", () => {
    $("status").textContent = "live";
    $("status").className = "badge live";
  });
  es.addEventListener("error", () => {
    $("status").textContent = "disconnected";
    $("status").className = "badge error";
  });
  es.addEventListener("message", (e) => {
    let env;
    try { env = JSON.parse(e.data); } catch (_) { return; }
    onEnvelope(env);
  });
}

function onEnvelope(env) {
  state.latestEnvelope = env;
  if (env.type === "agent_event" || env.type === "algo_event") {
    ingestEvent(env);
  } else if (env.type === "slot_occupancy") {
    state.slotOccupancy = env.snapshot || [];
    if (state.currentTab === "metrics") renderSlots();
  } else if (env.type === "cost_update") {
    state.costTotals = env.totals || {};
    paintGlobalStats();
    if (state.currentTab === "metrics") renderCost();
    if (state.currentTab === "overview") renderOverview();
  } else if (env.type === "stats_update") {
    state.globalStats = env.stats || null;
    paintGlobalStats();
  }
  if (state.currentTab === "raw") renderRaw();
}

function ingestEvent(env) {
  const runId = env.run_id;
  if (!runId) return;
  const isNew = !state.runs.has(runId);

  // accumulate in-browser list for this run (in case we selected it but don't have full history)
  const list = state.runEvents.get(runId) || [];
  list.push(env);
  if (list.length > 500) list.splice(0, list.length - 500);
  state.runEvents.set(runId, list);

  if (env.type === "algo_event" && env.kind === "generation") {
    state.liveGenerations.push({
      ...env.payload,
      run_id: runId,
      algorithm_path: env.algorithm_path,
      timestamp: env.started_at,
    });
    if (state.liveGenerations.length > 200) {
      state.liveGenerations.splice(0, state.liveGenerations.length - 200);
    }
    if (state.currentTab === "evolution") renderEvolution();
    if (state.currentTab === "overview" && !state.currentRunId) renderOverview();
    if (state.currentTab === "graph" && runId === state.currentRunId) renderGraph();
  }

  if (isNew || state.autoFollow) {
    refreshRuns();
  } else if (runId === state.currentRunId) {
    renderCurrent(env);
  }

  if (state.currentTab === "events" && runId === state.currentRunId) {
    appendEventRow(env);
  }
}

/* ---------- runs list ---------- */

async function refreshRuns() {
  try {
    const resp = await fetch("/runs");
    const items = await resp.json();
    state.runs = new Map(items.map((r) => [r.run_id, r]));
    renderRunsList();
    paintGlobalStats();
    if (state.currentTab === "metrics") renderAllRunsTable();

    if (!state.currentRunId && items.length > 0 && state.autoFollow) {
      // auto-select an algorithm run if one exists, else the newest.
      const interesting = items.find((r) => r.is_algorithm) || items[0];
      if (interesting) selectRun(interesting.run_id);
    } else if (state.autoFollow && items.length > 0) {
      // If we're following and the newest run just changed, jump to it.
      const newest = items[0];
      if (newest && newest.run_id !== state.currentRunId) {
        selectRun(newest.run_id);
      }
    }
  } catch (_) {}
}

function renderRunsList() {
  const ul = $("runs-list");
  ul.innerHTML = "";
  const visible = [...state.runs.values()].filter((r) => {
    if (state.filter === "algorithms") return r.is_algorithm;
    if (state.filter === "agents") return !r.is_algorithm;
    return true;
  });
  $("runs-count").textContent = `${visible.length} of ${state.runs.size}`;
  for (const r of visible) {
    const li = document.createElement("li");
    if (r.run_id === state.currentRunId) li.className = "active";
    const tag = r.is_algorithm ? "algorithm" : "agent";
    const sub = [];
    if (r.algorithm_path) sub.push(r.algorithm_path);
    else if (r.root_agent_path) sub.push(r.root_agent_path);
    sub.push(`${r.event_total} ev`);
    if (r.generations && r.generations.length > 0) {
      const best = r.generations[r.generations.length - 1].best;
      if (best != null) sub.push(`best=${best.toFixed(3)}`);
    }
    sub.push(fmtTime(r.last_event_at));
    li.innerHTML = `
      <div class="run-title">
        <span class="run-state-dot ${r.state}"></span>
        <span>${shortId(r.run_id)}</span>
      </div>
      <span class="run-tag ${tag}">${tag}</span>
      <div class="run-sub">${sub.join(" · ")}</div>
    `;
    li.addEventListener("click", () => {
      state.autoFollow = false;
      $("auto-follow").checked = false;
      selectRun(r.run_id);
    });
    ul.appendChild(li);
  }
}

async function selectRun(runId) {
  state.currentRunId = runId;
  state.selectedEventIdx = -1;
  renderRunsList();
  if (runId) {
    await Promise.all([fetchRunSummary(runId), fetchRunEvents(runId)]);
  }
  renderCurrent();
}

async function fetchRunSummary(runId) {
  try {
    const r = await fetch(`/runs/${encodeURIComponent(runId)}/summary`);
    if (!r.ok) return;
    const data = await r.json();
    state.runSummaries.set(runId, data);
  } catch (_) {}
}

async function fetchRunEvents(runId) {
  try {
    const r = await fetch(`/runs/${encodeURIComponent(runId)}/events?limit=500`);
    if (!r.ok) return;
    const data = await r.json();
    state.runEvents.set(runId, data.events || []);
  } catch (_) {}
}

/* ---------- tabs ---------- */

function setTab(name) {
  state.currentTab = name;
  for (const el of document.querySelectorAll(".tab"))
    el.classList.toggle("active", el.dataset.tab === name);
  for (const el of document.querySelectorAll(".pane"))
    el.classList.toggle("active", el.id === `pane-${name}`);
  renderCurrent();
}

function renderCurrent(incomingEnvelope = null) {
  switch (state.currentTab) {
    case "overview":  renderOverview(); break;
    case "evolution": renderEvolution(); break;
    case "graph":     renderGraph(); break;
    case "events":    renderEvents(); break;
    case "io":        renderIO(); break;
    case "metrics":   renderMetricsTab(); break;
    case "raw":       renderRaw(); break;
  }
}

/* ---------- overview ---------- */

function renderOverview() {
  const rid = state.currentRunId;
  const empty = $("overview-empty");
  const body = $("overview-body");
  if (!rid) {
    empty.hidden = false;
    body.hidden = true;
    renderMiniGlobal();
    return;
  }
  empty.hidden = true;
  body.hidden = false;
  const summary = state.runSummaries.get(rid) || state.runs.get(rid) || {};
  const state_ = summary.state || "running";
  const kpiStatus = $("kpi-status");
  kpiStatus.className = `card kpi ${state_}`;
  $("ov-status").textContent = state_;
  $("ov-duration").textContent = fmtDuration(summary.duration_ms);
  $("ov-events").textContent = fmtNum(summary.event_total || 0);

  const counts = summary.event_counts || {};
  const breakdown = Object.entries(counts)
    .map(([k, v]) => `${k}:${v}`)
    .join(" · ");
  $("ov-events-breakdown").textContent = breakdown || "—";

  const prompt = summary.prompt_tokens || 0;
  const completion = summary.completion_tokens || 0;
  $("ov-tokens").textContent = fmtNum(prompt + completion);
  $("ov-token-split").textContent = `${prompt} prompt · ${completion} completion`;

  const cost = (summary.cost && summary.cost.cost_usd) || 0;
  $("ov-cost").textContent = fmtCost(cost);
  $("ov-cost-sub").textContent = cost > 0 ? `from ${summary.algorithm_path || summary.root_agent_path || "run"}` : "no billable tokens";

  const meta = $("ov-meta");
  meta.innerHTML = "";
  const metaPairs = [
    ["run_id", rid],
    ["kind", summary.is_algorithm ? (summary.algorithm_path || "algorithm") : (summary.root_agent_path || "agent")],
    ["started", fmtTime(summary.started_at)],
    ["last event", fmtTime(summary.last_event_at)],
  ];
  if (summary.algorithm_terminal_score != null) {
    metaPairs.push(["score", summary.algorithm_terminal_score.toFixed(4)]);
  }
  if (summary.error) metaPairs.push(["error", summary.error]);
  for (const [k, v] of metaPairs) {
    const dt = document.createElement("dt"); dt.textContent = k;
    const dd = document.createElement("dd"); dd.textContent = v;
    meta.appendChild(dt); meta.appendChild(dd);
  }

  const fitnessSlot = $("ov-fitness");
  const gens = summary.generations || [];
  if (gens.length === 0) {
    fitnessSlot.innerHTML = '<p class="empty-inline muted">no algorithm events yet for this run</p>';
  } else {
    renderFitnessChart(fitnessSlot, gens);
  }
}

function renderMiniGlobal() {
  const slot = $("overview-global-chart");
  const gens = state.liveGenerations;
  if (!gens.length) {
    slot.innerHTML = '<p class="empty-inline muted">waiting for algorithm events — the agent_evolution demo streams one per generation.</p>';
    return;
  }
  renderFitnessChart(slot, gens);
}

/* ---------- evolution tab ---------- */

function renderEvolution() {
  const scopeEl = $("evo-scope");
  const scope = scopeEl.value;
  let gens = [];
  if (scope === "run" && state.currentRunId) {
    const summary = state.runSummaries.get(state.currentRunId);
    if (summary) gens = summary.generations || [];
  } else {
    gens = state.liveGenerations;
  }

  const statsEl = $("evo-stats");
  if (!gens.length) {
    statsEl.innerHTML = '<span class="muted small">no generation events yet</span>';
  } else {
    const best = Math.max(...gens.map((g) => g.best ?? -Infinity));
    const latest = gens[gens.length - 1];
    statsEl.innerHTML = `
      <div class="stat"><label>generations</label><b>${gens.length}</b></div>
      <div class="stat"><label>best ever</label><b>${best.toFixed(4)}</b></div>
      <div class="stat"><label>latest best</label><b>${(latest.best ?? 0).toFixed(4)}</b></div>
      <div class="stat"><label>latest mean</label><b>${(latest.mean ?? 0).toFixed(4)}</b></div>
    `;
  }

  const chartSlot = $("evo-chart");
  const scatterSlot = $("evo-scatter");
  if (!gens.length) {
    chartSlot.innerHTML = '<p class="empty-inline muted">waiting for generation events…</p>';
    scatterSlot.innerHTML = '<p class="empty-inline muted">waiting…</p>';
  } else {
    renderFitnessChart(chartSlot, gens);
    renderScatter(scatterSlot, gens);
  }

  const opsBody = $("evo-ops").querySelector("tbody");
  const ops = aggregateOps(gens);
  opsBody.innerHTML = "";
  if (!ops.length) {
    opsBody.innerHTML = '<tr><td colspan="4" class="muted">—</td></tr>';
  } else {
    for (const row of ops) {
      const tr = document.createElement("tr");
      const rate = row.attempts ? (row.successes / row.attempts) * 100 : 0;
      tr.innerHTML = `<td>${row.op}</td><td>${row.attempts}</td><td>${row.successes}</td><td>${rate.toFixed(0)}%</td>`;
      opsBody.appendChild(tr);
    }
  }

  const gensBody = $("evo-gens").querySelector("tbody");
  gensBody.innerHTML = "";
  for (const g of gens) {
    const tr = document.createElement("tr");
    const maxScore = Math.max(...(g.scores || [0]), 0.0001);
    const survivors = new Set(g.survivor_indices || []);
    const bars = (g.scores || []).map((s, i) => {
      const pct = Math.max(2, (s / maxScore) * 100);
      const cls = survivors.has(i) ? "survivor" : "";
      return `<span class="${cls}" style="height:${pct}%"></span>`;
    }).join("");
    tr.innerHTML = `
      <td>${g.gen_index ?? "—"}</td>
      <td>${g.best != null ? g.best.toFixed(4) : "—"}</td>
      <td>${g.mean != null ? g.mean.toFixed(4) : "—"}</td>
      <td><div class="sparkbar">${bars}</div></td>
    `;
    gensBody.appendChild(tr);
  }
}

function aggregateOps(gens) {
  const attempts = {};
  const successes = {};
  for (const g of gens) {
    for (const [op, n] of Object.entries(g.op_attempt_counts || {})) {
      attempts[op] = (attempts[op] || 0) + n;
    }
    for (const [op, n] of Object.entries(g.op_success_counts || {})) {
      successes[op] = (successes[op] || 0) + n;
    }
  }
  const rows = Object.keys(attempts).map((op) => ({
    op, attempts: attempts[op], successes: successes[op] || 0,
  }));
  rows.sort((a, b) => b.attempts - a.attempts);
  return rows;
}

/* ---------- SVG charts ---------- */

function renderFitnessChart(slot, gens) {
  const W = slot.clientWidth || 600;
  const H = slot.clientHeight || 200;
  const pad = { l: 36, r: 12, t: 12, b: 24 };
  const iw = W - pad.l - pad.r;
  const ih = H - pad.t - pad.b;

  const xs = gens.map((_, i) => i);
  const bests = gens.map((g) => g.best ?? 0);
  const means = gens.map((g) => g.mean ?? 0);
  const allY = bests.concat(means);
  const yMin = Math.min(...allY, 0);
  const yMax = Math.max(...allY, 1);
  const yRange = yMax - yMin || 1;

  const sx = (i) => pad.l + (xs.length > 1 ? (i / (xs.length - 1)) * iw : iw / 2);
  const sy = (v) => pad.t + ih - ((v - yMin) / yRange) * ih;

  const line = (vals) =>
    vals.map((v, i) => `${i === 0 ? "M" : "L"} ${sx(i).toFixed(1)} ${sy(v).toFixed(1)}`).join(" ");

  const area = (vals) => {
    if (!vals.length) return "";
    return `M ${sx(0)} ${sy(yMin)} ` +
      vals.map((v, i) => `L ${sx(i).toFixed(1)} ${sy(v).toFixed(1)}`).join(" ") +
      ` L ${sx(vals.length - 1)} ${sy(yMin)} Z`;
  };

  const gridLines = [0, 0.25, 0.5, 0.75, 1].map((t) => {
    const y = pad.t + ih - t * ih;
    const v = yMin + t * yRange;
    return `<line x1="${pad.l}" y1="${y}" x2="${pad.l + iw}" y2="${y}" stroke="#262c3b" stroke-width="1" />
            <text x="${pad.l - 6}" y="${y + 3}" text-anchor="end" fill="#5a6275" font-size="9">${v.toFixed(2)}</text>`;
  }).join("");

  const xTicks = xs.map((i) => {
    if (xs.length > 12 && i % Math.ceil(xs.length / 8) !== 0 && i !== xs.length - 1) return "";
    return `<text x="${sx(i)}" y="${pad.t + ih + 14}" text-anchor="middle" fill="#5a6275" font-size="9">${gens[i].gen_index ?? i}</text>`;
  }).join("");

  const dots = bests.map((v, i) =>
    `<circle cx="${sx(i).toFixed(1)}" cy="${sy(v).toFixed(1)}" r="3" fill="#46a7ff" />`
  ).join("");

  slot.innerHTML = `
  <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
    ${gridLines}
    <path d="${area(bests)}" fill="#46a7ff" fill-opacity="0.1" />
    <path d="${line(means)}" stroke="#b794f4" stroke-width="1.5" fill="none" stroke-dasharray="4,3" />
    <path d="${line(bests)}" stroke="#46a7ff" stroke-width="2" fill="none" />
    ${dots}
    ${xTicks}
    <g transform="translate(${pad.l + 6}, ${pad.t + 10})">
      <rect width="68" height="32" fill="#12151e" fill-opacity="0.8" rx="3" />
      <circle cx="8" cy="10" r="3" fill="#46a7ff" />
      <text x="16" y="13" fill="#e7e9f1" font-size="10">best</text>
      <line x1="4" y1="24" x2="12" y2="24" stroke="#b794f4" stroke-width="1.5" stroke-dasharray="4,3" />
      <text x="16" y="27" fill="#e7e9f1" font-size="10">mean</text>
    </g>
  </svg>`;
}

function renderScatter(slot, gens) {
  const W = slot.clientWidth || 600;
  const H = slot.clientHeight || 150;
  const pad = { l: 36, r: 12, t: 10, b: 22 };
  const iw = W - pad.l - pad.r;
  const ih = H - pad.t - pad.b;

  const points = [];
  for (let g = 0; g < gens.length; g++) {
    const scores = gens[g].scores || [];
    const survivors = new Set(gens[g].survivor_indices || []);
    for (let i = 0; i < scores.length; i++) {
      points.push({ g, i, s: scores[i], survivor: survivors.has(i) });
    }
  }
  if (!points.length) {
    slot.innerHTML = '<p class="empty-inline muted">no population data</p>';
    return;
  }
  const yMin = Math.min(...points.map((p) => p.s), 0);
  const yMax = Math.max(...points.map((p) => p.s), 1);
  const yRange = yMax - yMin || 1;
  const sx = (g) => pad.l + (gens.length > 1 ? (g / (gens.length - 1)) * iw : iw / 2);
  const sy = (v) => pad.t + ih - ((v - yMin) / yRange) * ih;
  const dots = points.map((p) => {
    const color = p.survivor ? "#43c871" : "#46a7ff";
    const opacity = p.survivor ? 0.9 : 0.45;
    return `<circle cx="${sx(p.g) + (Math.random() - 0.5) * 6}" cy="${sy(p.s).toFixed(1)}" r="3" fill="${color}" fill-opacity="${opacity}" />`;
  }).join("");

  const gridLines = [0, 0.5, 1].map((t) => {
    const y = pad.t + ih - t * ih;
    const v = yMin + t * yRange;
    return `<line x1="${pad.l}" y1="${y}" x2="${pad.l + iw}" y2="${y}" stroke="#262c3b" stroke-width="1" />
            <text x="${pad.l - 6}" y="${y + 3}" text-anchor="end" fill="#5a6275" font-size="9">${v.toFixed(2)}</text>`;
  }).join("");

  slot.innerHTML = `
  <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
    ${gridLines}
    ${dots}
    <text x="${pad.l + iw / 2}" y="${H - 4}" text-anchor="middle" fill="#5a6275" font-size="9">generation →</text>
  </svg>`;
}

/* ---------- graph tab ---------- */

/**
 * Aggregate per-path mutation activity from generation events for `runId`.
 * Returns a Map<dotted_path, {attempts, successes}>.
 *
 * Mutation entries come from EvoGradient's `generation` AlgorithmEvent payload
 * (`mutations: [{individual_id, op, path, improved}]`). Identity / unattributed
 * entries with empty path are ignored — they represent the unmutated root or
 * fallback clones, not a graph-node-level signal.
 */
function aggregatePathMutations(runId) {
  const acc = new Map();
  for (const gen of state.liveGenerations) {
    if (gen.run_id !== runId) continue;
    for (const m of gen.mutations || []) {
      const path = m.path || "";
      if (!path) continue;
      const cur = acc.get(path) || { attempts: 0, successes: 0 };
      cur.attempts += 1;
      if (m.improved) cur.successes += 1;
      acc.set(path, cur);
    }
  }
  return acc;
}

/**
 * Append Mermaid `style` directives that tint nodes which were the target
 * of mutations during this run. Node IDs in the Mermaid source replace `.`
 * with `_` (see operad/core/graph.py::_mermaid_id), and mutation paths are
 * relative to the root agent — so the full graph-node path is
 * `${rootName}.${mutation.path}` (or `${rootName}` when path is empty).
 */
function tintGraphFromMutations(mermaidSrc, rootName, pathMutations) {
  if (!rootName || pathMutations.size === 0) return mermaidSrc;
  const lines = [mermaidSrc];
  for (const [path, counts] of pathMutations) {
    const fullPath = `${rootName}.${path}`;
    const nodeId = fullPath.replaceAll(".", "_");
    if (counts.successes > 0) {
      lines.push(`style ${nodeId} fill:#1b3a2a,stroke:#46e09a,stroke-width:2px`);
    } else if (counts.attempts > 0) {
      lines.push(`style ${nodeId} fill:#3a2f1b,stroke:#e0a946,stroke-width:2px`);
    }
  }
  return lines.join("\n");
}

async function renderGraph() {
  const rid = state.currentRunId;
  const graphEl = $("graph");
  const title = $("graph-title");
  if (!rid) {
    title.textContent = "no run selected";
    graphEl.innerHTML = "flowchart LR\n  placeholder[\"select a run from the sidebar\"]";
    graphEl.removeAttribute("data-processed");
    await mermaid.run({ nodes: [graphEl] });
    return;
  }
  title.textContent = `run ${shortId(rid)}`;
  try {
    const r = await fetch(`/graph/${encodeURIComponent(rid)}`);
    if (!r.ok) {
      graphEl.innerHTML = `flowchart LR\n  none["no graph captured for this run"]`;
    } else {
      const j = await r.json();
      let src = j.mermaid;
      const summary = state.runSummaries.get(rid) || state.runs.get(rid);
      const rootName = summary && summary.root_agent_path;
      const pathMutations = aggregatePathMutations(rid);
      src = tintGraphFromMutations(src, rootName, pathMutations);
      graphEl.innerHTML = src;
    }
    graphEl.removeAttribute("data-processed");
    await mermaid.run({ nodes: [graphEl] });
  } catch (_) {
    graphEl.innerHTML = `flowchart LR\n  err["failed to load graph"]`;
    graphEl.removeAttribute("data-processed");
    try { await mermaid.run({ nodes: [graphEl] }); } catch (_) {}
  }
}

/* ---------- events tab ---------- */

function renderEvents() {
  const ul = $("events");
  ul.innerHTML = "";
  const rid = state.currentRunId;
  if (!rid) {
    ul.innerHTML = '<li><span class="muted">select a run to inspect events</span></li>';
    return;
  }
  const events = state.runEvents.get(rid) || [];
  const filtered = events.filter(passesEventFilter);
  for (let i = 0; i < filtered.length; i++) appendEventRow(filtered[i], i);
  if (state.eventsFollow) ul.scrollTop = ul.scrollHeight;
  renderEventDetail();
}

function passesEventFilter(env) {
  if (state.eventKindFilter === "agent" && env.type !== "agent_event") return false;
  if (state.eventKindFilter === "algo" && env.type !== "algo_event") return false;
  if (state.eventKindFilter === "error") {
    const isErr = env.kind === "error" || env.kind === "algo_error";
    if (!isErr) return false;
  }
  if (state.eventSearch) {
    const needle = state.eventSearch.toLowerCase();
    const path = (env.agent_path || env.algorithm_path || "").toLowerCase();
    if (!path.includes(needle) && !String(env.kind).includes(needle)) return false;
  }
  return true;
}

function appendEventRow(env, idx = null) {
  if (env.run_id !== state.currentRunId) return;
  if (!passesEventFilter(env)) return;
  const ul = $("events");
  const li = document.createElement("li");
  li.dataset.kind = env.kind || "";
  const pathCell = env.type === "algo_event"
    ? `<span class="ev-path">${env.algorithm_path || ""}</span>`
    : `<span class="ev-path">${env.agent_path || ""}</span>`;
  li.innerHTML = `
    <span class="ev-time">${fmtTime(env.started_at)}</span>
    <span class="ev-kind">${env.kind || "?"}</span>
    ${pathCell}
    <span class="ev-run">${shortId(env.run_id)}</span>
  `;
  const events = state.runEvents.get(state.currentRunId) || [];
  const realIdx = events.indexOf(env);
  li.addEventListener("click", () => selectEvent(realIdx));
  if (realIdx === state.selectedEventIdx) li.classList.add("selected");
  ul.appendChild(li);
  while (ul.children.length > 800) ul.removeChild(ul.firstChild);
  if (state.eventsFollow) ul.scrollTop = ul.scrollHeight;
}

function selectEvent(idx) {
  state.selectedEventIdx = idx;
  for (const li of document.querySelectorAll("#events li"))
    li.classList.remove("selected");
  const ul = $("events");
  const events = state.runEvents.get(state.currentRunId) || [];
  const env = events[idx];
  for (const li of ul.children) {
    const match = li.querySelector(".ev-run")?.textContent === shortId(env?.run_id)
      && li.querySelector(".ev-kind")?.textContent === (env?.kind || "?")
      && li.querySelector(".ev-time")?.textContent === fmtTime(env?.started_at);
    if (match) { li.classList.add("selected"); break; }
  }
  renderEventDetail();
}

function renderEventDetail() {
  const box = $("event-detail");
  const events = state.runEvents.get(state.currentRunId) || [];
  const env = events[state.selectedEventIdx];
  if (!env) {
    box.innerHTML = '<h4>event detail</h4><p class="muted small">click any event to inspect</p>';
    return;
  }
  const blocks = [];
  const header = `
    <div class="detail-block">
      <label>kind</label>
      <div>${env.kind || "?"} · ${env.type || "?"}</div>
    </div>
    <div class="detail-block">
      <label>path</label>
      <div>${env.agent_path || env.algorithm_path || "—"}</div>
    </div>
    <div class="detail-block">
      <label>run_id</label>
      <div>${env.run_id || "—"}</div>
    </div>
    <div class="detail-block">
      <label>started / finished</label>
      <div>${fmtTime(env.started_at)} → ${fmtTime(env.finished_at) || "…"}</div>
    </div>`;
  if (env.input !== undefined && env.input !== null) {
    blocks.push(`<div class="detail-block"><label>input</label>${renderJson(env.input)}</div>`);
  }
  if (env.output !== undefined && env.output !== null) {
    blocks.push(`<div class="detail-block"><label>output</label>${renderJson(env.output)}</div>`);
  }
  if (env.payload) {
    blocks.push(`<div class="detail-block"><label>payload</label>${renderJson(env.payload)}</div>`);
  }
  if (env.metadata && Object.keys(env.metadata).length) {
    blocks.push(`<div class="detail-block"><label>metadata</label>${renderJson(env.metadata)}</div>`);
  }
  if (env.error) {
    blocks.push(`<div class="detail-block"><label>error</label>${renderJson(env.error)}</div>`);
  }
  box.innerHTML = `<h4>event detail</h4>${header}${blocks.join("")}`;
}

function renderJson(value) {
  return `<pre class="json-view">${escapeHtml(JSON.stringify(value, null, 2))}</pre>`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

/* ---------- i/o tab ---------- */

function renderIO() {
  const rid = state.currentRunId;
  const inputBox = $("io-input");
  const outputBox = $("io-output");
  const tblBody = $("io-table").querySelector("tbody");
  tblBody.innerHTML = "";
  if (!rid) {
    inputBox.textContent = "—";
    outputBox.textContent = "—";
    return;
  }
  const events = state.runEvents.get(rid) || [];
  const rootEvents = events.filter((e) => e.type === "agent_event" && e.metadata && e.metadata.is_root);
  const starts = rootEvents.filter((e) => e.kind === "start");
  const ends = rootEvents.filter((e) => e.kind === "end" || e.kind === "error");
  const lastStart = starts[starts.length - 1];
  const lastEnd = ends[ends.length - 1];
  inputBox.innerHTML = lastStart?.input !== undefined
    ? escapeHtml(JSON.stringify(lastStart.input, null, 2))
    : "—";
  outputBox.innerHTML = lastEnd?.output !== undefined
    ? escapeHtml(JSON.stringify(lastEnd.output, null, 2))
    : "—";
  // Build matched start/end table
  for (const e of rootEvents) {
    const tr = document.createElement("tr");
    const dur = (e.finished_at && e.started_at) ? (e.finished_at - e.started_at) * 1000 : null;
    const tokens = e.output && (e.output.prompt_tokens || e.output.completion_tokens)
      ? `${e.output.prompt_tokens || 0}/${e.output.completion_tokens || 0}`
      : "—";
    tr.innerHTML = `
      <td>${e.kind}</td>
      <td>${e.agent_path}</td>
      <td>${fmtTime(e.started_at)}</td>
      <td>${dur != null ? dur.toFixed(1) : "—"}</td>
      <td>${tokens}</td>`;
    tblBody.appendChild(tr);
  }
  if (!tblBody.children.length) {
    tblBody.innerHTML = '<tr><td colspan="5" class="muted">no root-level invocations on this run</td></tr>';
  }
}

/* ---------- metrics tab ---------- */

function renderMetricsTab() {
  renderSlots();
  renderCost();
  renderAllRunsTable();
}

function renderSlots() {
  const body = $("slots-table").querySelector("tbody");
  body.innerHTML = "";
  const snap = state.slotOccupancy || [];
  if (!snap.length) {
    body.innerHTML = '<tr><td colspan="5" class="muted">no active slots</td></tr>';
    return;
  }
  for (const s of snap) {
    const tr = document.createElement("tr");
    const conc = `${s.concurrency_used}/${s.concurrency_cap ?? "∞"}`;
    const rpm = s.rpm_cap == null ? "—" : `${s.rpm_used}/${s.rpm_cap}`;
    const tpm = s.tpm_cap == null ? "—" : `${s.tpm_used}/${s.tpm_cap}`;
    tr.innerHTML = `<td>${s.backend}</td><td>${s.host}</td><td>${conc}</td><td>${rpm}</td><td>${tpm}</td>`;
    body.appendChild(tr);
  }
}

function renderCost() {
  const body = $("cost-table").querySelector("tbody");
  body.innerHTML = "";
  const totals = state.costTotals || {};
  const rows = Object.entries(totals);
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="4" class="muted">no billable events yet</td></tr>';
    return;
  }
  for (const [rid, t] of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${shortId(rid)}</td>
      <td>${t.prompt_tokens}</td>
      <td>${t.completion_tokens}</td>
      <td>${fmtCost(t.cost_usd)}</td>`;
    body.appendChild(tr);
  }
}

function renderAllRunsTable() {
  const body = $("runs-table").querySelector("tbody");
  body.innerHTML = "";
  const runs = [...state.runs.values()];
  if (!runs.length) {
    body.innerHTML = '<tr><td colspan="6" class="muted">no runs yet</td></tr>';
    return;
  }
  for (const r of runs) {
    const tr = document.createElement("tr");
    const kind = r.is_algorithm ? (r.algorithm_path || "algorithm") : (r.root_agent_path || "agent");
    tr.innerHTML = `
      <td>${shortId(r.run_id)}</td>
      <td>${r.state}</td>
      <td>${kind}</td>
      <td>${r.event_total}</td>
      <td>${fmtDuration(r.duration_ms)}</td>
      <td>${fmtTime(r.last_event_at)}</td>`;
    tr.style.cursor = "pointer";
    tr.addEventListener("click", () => { selectRun(r.run_id); setTab("overview"); });
    body.appendChild(tr);
  }
}

/* ---------- raw tab ---------- */

function renderRaw() {
  const latest = $("raw-latest");
  latest.textContent = state.latestEnvelope
    ? JSON.stringify(state.latestEnvelope, null, 2)
    : "no events yet";
  const sum = $("raw-summary");
  const s = state.currentRunId ? state.runSummaries.get(state.currentRunId) : null;
  sum.textContent = s ? JSON.stringify(s, null, 2) : "select a run";
}

/* ---------- global stats paint ---------- */

function paintGlobalStats() {
  const s = state.globalStats || {};
  $("g-runs").textContent = s.runs_total ?? state.runs.size;
  $("g-live").textContent = s.runs_running ?? [...state.runs.values()].filter((r) => r.state === "running").length;
  $("g-ended").textContent = s.runs_ended ?? [...state.runs.values()].filter((r) => r.state === "ended").length;
  $("g-error").textContent = s.runs_error ?? [...state.runs.values()].filter((r) => r.state === "error").length;
  $("g-events").textContent = fmtNum(s.event_total ?? [...state.runs.values()].reduce((a, r) => a + (r.event_total || 0), 0));
  const totalTokens = (s.prompt_tokens || 0) + (s.completion_tokens || 0);
  $("g-tokens").textContent = fmtNum(totalTokens);
  const totalUsd = Object.values(state.costTotals || {}).reduce((a, t) => a + (t.cost_usd || 0), 0);
  $("g-cost").textContent = fmtCost(totalUsd);
  $("subs").textContent = s.subscribers ? `${s.subscribers} subs` : "";
}

/* ---------- wire up ---------- */

function bind() {
  for (const btn of document.querySelectorAll(".tab")) {
    btn.addEventListener("click", () => setTab(btn.dataset.tab));
  }
  for (const btn of document.querySelectorAll("#filters .chip")) {
    btn.addEventListener("click", () => {
      state.filter = btn.dataset.filter;
      for (const b of document.querySelectorAll("#filters .chip"))
        b.classList.toggle("active", b === btn);
      renderRunsList();
    });
  }
  $("auto-follow").addEventListener("change", (e) => {
    state.autoFollow = e.target.checked;
  });
  $("events-follow").addEventListener("change", (e) => {
    state.eventsFollow = e.target.checked;
  });
  $("events-search").addEventListener("input", (e) => {
    state.eventSearch = e.target.value || "";
    renderEvents();
  });
  for (const btn of document.querySelectorAll(".events-filters .chip")) {
    btn.addEventListener("click", () => {
      state.eventKindFilter = btn.dataset.kind;
      for (const b of document.querySelectorAll(".events-filters .chip"))
        b.classList.toggle("active", b === btn);
      renderEvents();
    });
  }
  $("graph-refresh").addEventListener("click", renderGraph);
  $("evo-scope").addEventListener("change", renderEvolution);
}

bind();
refreshRuns();
setInterval(refreshRuns, 5000);
connect();
