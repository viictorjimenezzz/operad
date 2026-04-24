"use strict";

mermaid.initialize({ startOnLoad: false, theme: "dark" });

const $ = (id) => document.getElementById(id);
const statusEl = $("status");
const eventsEl = $("events");
const runSelect = $("run-select");
const graphEl = $("graph");
const runsBody = $("runs-table").querySelector("tbody");
const slotsBody = $("slots-table").querySelector("tbody");
const costBody = $("cost-table").querySelector("tbody");

let currentRunId = "";
let knownRuns = new Map();

function fmtTime(ts) {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleTimeString();
}

function appendEvent(env) {
  const li = document.createElement("li");
  if (env.type === "algo_event") {
    li.className = "algo";
    li.textContent = `[algo] ${env.algorithm_path} ${env.kind} ${JSON.stringify(env.payload || {})}`;
  } else {
    if (env.kind === "error") li.className = "error";
    else if (env.kind === "chunk") li.className = "chunk";
    li.textContent = `[${env.kind}] ${env.agent_path} run=${env.run_id?.slice(0, 8)}`;
    if (env.error) li.textContent += `  ${env.error.type}: ${env.error.message}`;
  }
  eventsEl.appendChild(li);
  while (eventsEl.children.length > 500) {
    eventsEl.removeChild(eventsEl.firstChild);
  }
  eventsEl.scrollTop = eventsEl.scrollHeight;
}

async function refreshRuns() {
  try {
    const r = await fetch("/runs");
    const items = await r.json();
    knownRuns = new Map(items.map((it) => [it.run_id, it]));
    runsBody.innerHTML = "";
    for (const it of items) {
      const tr = document.createElement("tr");
      const shortId = it.run_id.slice(0, 8);
      tr.innerHTML = `<td><a href="/runs/${it.run_id}">${shortId}</a></td><td>${it.state}</td><td>${fmtTime(it.last_event_at)}</td>`;
      runsBody.appendChild(tr);
    }
    const previous = currentRunId;
    runSelect.innerHTML = '<option value="">— none —</option>';
    for (const it of items) {
      const opt = document.createElement("option");
      opt.value = it.run_id;
      opt.textContent = `${it.run_id.slice(0, 12)} (${it.state})`;
      runSelect.appendChild(opt);
    }
    if (previous && knownRuns.has(previous)) runSelect.value = previous;
    else if (items.length > 0) {
      runSelect.value = items[0].run_id;
      await selectRun(items[0].run_id);
    }
  } catch (_) {}
}

async function selectRun(runId) {
  currentRunId = runId;
  if (!runId) {
    graphEl.innerHTML = "flowchart LR\n    placeholder[\"select a run\"]";
    await mermaid.run({ nodes: [graphEl] });
    return;
  }
  try {
    const r = await fetch(`/graph/${runId}`);
    if (!r.ok) {
      graphEl.innerHTML = `flowchart LR\n    none["no graph for ${runId.slice(0, 8)}"]`;
    } else {
      const j = await r.json();
      graphEl.innerHTML = j.mermaid;
    }
    graphEl.removeAttribute("data-processed");
    await mermaid.run({ nodes: [graphEl] });
  } catch (_) {}
}

runSelect.addEventListener("change", () => selectRun(runSelect.value));

function paintSlots(snapshot) {
  slotsBody.innerHTML = "";
  for (const s of snapshot || []) {
    const tr = document.createElement("tr");
    const conc = `${s.concurrency_used}/${s.concurrency_cap ?? "∞"}`;
    const rpm = s.rpm_cap == null ? "—" : `${s.rpm_used}/${s.rpm_cap}`;
    const tpm = s.tpm_cap == null ? "—" : `${s.tpm_used}/${s.tpm_cap}`;
    tr.innerHTML = `<td>${s.backend}</td><td>${s.host}</td><td>${conc}</td><td>${rpm}</td><td>${tpm}</td>`;
    slotsBody.appendChild(tr);
  }
}

function paintCost(totals) {
  costBody.innerHTML = "";
  for (const [runId, t] of Object.entries(totals || {})) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${runId.slice(0, 8)}</td><td>${t.prompt_tokens}</td><td>${t.completion_tokens}</td><td>$${(t.cost_usd ?? 0).toFixed(4)}</td>`;
    costBody.appendChild(tr);
  }
}

function connect() {
  const es = new EventSource("/stream");
  es.addEventListener("open", () => {
    statusEl.textContent = "live";
    statusEl.className = "badge live";
  });
  es.addEventListener("error", () => {
    statusEl.textContent = "disconnected";
    statusEl.className = "badge error";
  });
  es.addEventListener("message", (e) => {
    let env;
    try { env = JSON.parse(e.data); } catch (_) { return; }
    if (env.type === "agent_event" || env.type === "algo_event") {
      appendEvent(env);
      const seen = knownRuns.has(env.run_id);
      if (!seen) refreshRuns();
    } else if (env.type === "slot_occupancy") {
      paintSlots(env.snapshot);
    } else if (env.type === "cost_update") {
      paintCost(env.totals);
    }
  });
}

refreshRuns();
setInterval(refreshRuns, 5000);
connect();
