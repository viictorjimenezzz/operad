// mutation-activity heatmap — per-op success rate over generations.
"use strict";

window.operadInit_mutations = async function(runId) {
  const panel = document.getElementById("panel-mutations");
  const table = document.getElementById("mutations-table");
  if (!panel || !table) return;

  let state = { gens: [], ops: [], success: [], attempts: [] };

  function paint() {
    if (!state.ops.length || !state.gens.length) {
      panel.hidden = true;
      return;
    }
    panel.hidden = false;
    const thead = table.querySelector("thead");
    const tbody = table.querySelector("tbody");
    thead.innerHTML = "";
    tbody.innerHTML = "";

    const headRow = document.createElement("tr");
    const cornerTh = document.createElement("th");
    cornerTh.textContent = "op";
    headRow.appendChild(cornerTh);
    for (const g of state.gens) {
      const th = document.createElement("th");
      th.textContent = "g" + g;
      headRow.appendChild(th);
    }
    thead.appendChild(headRow);

    for (let i = 0; i < state.ops.length; i++) {
      const tr = document.createElement("tr");
      const opCell = document.createElement("td");
      opCell.className = "op-name";
      opCell.textContent = state.ops[i];
      tr.appendChild(opCell);
      for (let j = 0; j < state.gens.length; j++) {
        const td = document.createElement("td");
        const a = state.attempts[i][j];
        const s = state.success[i][j];
        const rate = a > 0 ? s / a : null;
        if (rate === null) {
          td.textContent = "—";
        } else if (a > 0 && s === 0) {
          td.textContent = "0.00";
          td.classList.add("zero-success");
        } else {
          td.textContent = rate.toFixed(2);
          const alpha = Math.max(0.1, Math.min(1, rate));
          td.style.backgroundColor = `rgba(34, 197, 94, ${alpha})`;
        }
        td.title = `${s}/${a} attempts`;
        tr.appendChild(td);
      }
      tbody.appendChild(tr);
    }
  }

  async function seed() {
    try {
      const r = await fetch(`/runs/${runId}/mutations.json`);
      if (!r.ok) return;
      state = await r.json();
      paint();
    } catch (_) {}
  }

  function connect() {
    const es = new EventSource(`/runs/${runId}/mutations.sse`);
    es.addEventListener("message", (e) => {
      try { state = JSON.parse(e.data); } catch (_) { return; }
      paint();
    });
    es.addEventListener("error", () => {
      es.close();
      setTimeout(connect, 5000);
    });
  }

  await seed();
  connect();
};
