// PromptDrift timeline — one entry per epoch with hash delta + changed params.
"use strict";

window.operadInit_drift = async function(runId) {
  const panel = document.getElementById("panel-drift");
  const timeline = document.getElementById("drift-timeline");
  if (!panel || !timeline) return;

  const seenEpochs = new Set();

  function renderEntry(entry, prepend) {
    if (seenEpochs.has(entry.epoch)) return;
    seenEpochs.add(entry.epoch);
    const li = document.createElement("li");
    if (seenEpochs.size === 1) li.classList.add("first");
    const hashLine = document.createElement("div");
    hashLine.className = "drift-hash";
    const before = (entry.hash_before || "").slice(0, 8);
    const after = (entry.hash_after || "").slice(0, 8);
    hashLine.textContent = `epoch ${entry.epoch}: ${before} → ${after} (${entry.delta_count} changed)`;
    li.appendChild(hashLine);

    if (entry.changed_params && entry.changed_params.length) {
      const details = document.createElement("details");
      details.className = "drift-changed";
      const summary = document.createElement("summary");
      summary.textContent = `${entry.changed_params.length} parameter(s)`;
      details.appendChild(summary);
      const ul = document.createElement("ul");
      for (const p of entry.changed_params) {
        const l = document.createElement("li");
        l.textContent = p;
        ul.appendChild(l);
      }
      details.appendChild(ul);
      li.appendChild(details);
    }

    if (prepend && timeline.firstChild) {
      timeline.insertBefore(li, timeline.firstChild);
    } else {
      timeline.appendChild(li);
    }
    panel.hidden = false;
  }

  async function seed() {
    try {
      const r = await fetch(`/runs/${runId}/drift.json`);
      if (!r.ok) return;
      const entries = await r.json();
      for (const entry of entries) renderEntry(entry, false);
    } catch (_) {}
  }

  function connect() {
    const es = new EventSource(`/runs/${runId}/drift.sse`);
    es.addEventListener("message", (e) => {
      let entry;
      try { entry = JSON.parse(e.data); } catch (_) { return; }
      renderEntry(entry, true);
    });
    es.addEventListener("error", () => {
      es.close();
      setTimeout(connect, 5000);
    });
  }

  await seed();
  connect();
};
