// fitness-curve panel — best (solid), mean (dashed), spread band (fill).
"use strict";

window.operadInit_fitness = async function(runId) {
  const panel = document.getElementById("panel-fitness");
  const canvas = document.getElementById("fitness-chart");
  const fallback = document.getElementById("fitness-fallback");
  if (!panel || !canvas) return;

  let chart = null;
  const entries = [];

  async function seed() {
    try {
      const r = await fetch(`/runs/${runId}/fitness.json`);
      if (!r.ok) return;
      const rows = await r.json();
      for (const row of rows) entries.push(row);
      if (entries.length === 0) return;
      panel.hidden = false;
      renderOrFallback();
    } catch (err) { /* ignore */ }
  }

  function renderOrFallback() {
    if (typeof Chart === "undefined") {
      fallback.hidden = false;
      fallback.textContent = JSON.stringify(entries, null, 2);
      return;
    }
    if (!chart) chart = buildChart();
    const labels = entries.map((e) => e.gen_index);
    chart.data.labels = labels;
    chart.data.datasets[0].data = entries.map((e) => e.best);
    chart.data.datasets[1].data = entries.map((e) => e.mean);
    chart.data.datasets[2].data = entries.map((e) => e.worst);
    chart.update();
  }

  function buildChart() {
    return new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels: [],
        datasets: [
          { label: "best", data: [], borderColor: "#4ade80", backgroundColor: "transparent", tension: 0.2 },
          { label: "mean", data: [], borderColor: "#8a92a6", borderDash: [4, 4], backgroundColor: "transparent", tension: 0.2 },
          { label: "worst", data: [], borderColor: "#64748b", backgroundColor: "rgba(74, 140, 255, 0.1)", fill: "-1", tension: 0.2, pointRadius: 0 },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { labels: { color: "#e6e8ec" } } },
        scales: {
          x: { ticks: { color: "#8a92a6" }, grid: { color: "#1d212b" } },
          y: { ticks: { color: "#8a92a6" }, grid: { color: "#1d212b" } },
        },
      },
    });
  }

  function connect() {
    const es = new EventSource(`/runs/${runId}/fitness.sse`);
    es.addEventListener("message", (e) => {
      let entry;
      try { entry = JSON.parse(e.data); } catch (_) { return; }
      if (!entry || entry.skipped) return;
      entries.push(entry);
      panel.hidden = false;
      renderOrFallback();
    });
    es.addEventListener("error", () => {
      es.close();
      setTimeout(connect, 5000);
    });
  }

  await seed();
  connect();
};
