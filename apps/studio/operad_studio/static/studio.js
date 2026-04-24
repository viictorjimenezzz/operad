"use strict";

// Persist ratings via AJAX; launch training with SSE-driven status stream.
(() => {
  const jobName = window.OPERAD_JOB_NAME;
  if (!jobName) return;

  document.querySelectorAll(".row-rate").forEach((form) => {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const data = new FormData(form);
      const action = form.getAttribute("action");
      try {
        const r = await fetch(action, { method: "POST", body: data });
        if (r.ok) {
          form.classList.add("saved");
          setTimeout(() => form.classList.remove("saved"), 1000);
        } else {
          console.error("rating save failed", await r.text());
        }
      } catch (err) { console.error(err); }
    });
  });

  const trainForm = document.getElementById("train-form");
  const statusEl = document.getElementById("train-status");
  if (trainForm && statusEl) {
    trainForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      statusEl.textContent = "";
      const r = await fetch(trainForm.action, {
        method: "POST",
        body: new FormData(trainForm),
      });
      if (r.status === 202) {
        connectStream();
      } else {
        statusEl.textContent = `training failed to start (${r.status})`;
      }
    });
  }

  function connectStream() {
    const es = new EventSource(`/jobs/${encodeURIComponent(jobName)}/train/stream`);
    es.addEventListener("message", (ev) => {
      try {
        const d = JSON.parse(ev.data);
        const line = document.createElement("div");
        line.textContent = `[${d.kind}] ${JSON.stringify(d).slice(0, 200)}`;
        statusEl.appendChild(line);
        statusEl.scrollTop = statusEl.scrollHeight;
        if (d.kind === "finished" || d.kind === "error") es.close();
      } catch (_) {}
    });
    es.addEventListener("error", () => {
      es.close();
    });
  }
})();
