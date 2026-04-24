// Training progress widget — outer epoch bar + inner batch bar + ETA line.
"use strict";

window.operadInit_progress = async function(runId) {
  const panel = document.getElementById("panel-progress");
  if (!panel) return;
  const $ = (attr) => panel.querySelector(`[data-progress="${attr}"]`);

  function paint(snapshot) {
    if (!snapshot || (!snapshot.epochs_total && !snapshot.batches_total && !snapshot.batch)) {
      return;
    }
    panel.hidden = false;
    $("epoch-current").textContent = snapshot.epoch;
    $("epoch-total").textContent = snapshot.epochs_total ?? "?";
    $("batch-current").textContent = snapshot.batch;
    $("batch-total").textContent = snapshot.batches_total ?? "?";

    const epochBar = $("epoch-bar");
    if (snapshot.epochs_total && snapshot.epochs_total > 0) {
      epochBar.max = snapshot.epochs_total;
      epochBar.value = snapshot.epoch;
    }
    const batchBar = $("batch-bar");
    if (snapshot.batches_total && snapshot.batches_total > 0) {
      batchBar.max = snapshot.batches_total;
      batchBar.value = snapshot.batch;
    } else if (snapshot.batch > 0) {
      batchBar.max = Math.max(snapshot.batch, 1);
      batchBar.value = snapshot.batch;
    }

    $("rate").textContent = (snapshot.rate_batches_per_s ?? 0).toFixed(1);
    $("eta").textContent = snapshot.eta_s != null ? fmtEta(snapshot.eta_s) : "—";
  }

  function fmtEta(seconds) {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return `${m}m ${s}s`;
  }

  async function seed() {
    try {
      const r = await fetch(`/runs/${runId}/progress.json`);
      if (!r.ok) return;
      paint(await r.json());
    } catch (_) {}
  }

  function connect() {
    const es = new EventSource(`/runs/${runId}/progress.sse`);
    es.addEventListener("message", (e) => {
      let snap;
      try { snap = JSON.parse(e.data); } catch (_) { return; }
      paint(snap);
    });
    es.addEventListener("error", () => {
      es.close();
      setTimeout(connect, 5000);
    });
  }

  await seed();
  connect();
};
