// Bootstrap the four per-run panels. Each module self-registers via a
// globally-exposed init function when its own script is loaded.
(async () => {
  const runId = window.OPERAD_RUN_ID;
  if (!runId) return;

  const modules = [
    ['progress', '/static/js/progress.js'],
    ['fitness', '/static/js/fitness.js'],
    ['mutations', '/static/js/mutations.js'],
    ['drift', '/static/js/drift.js'],
  ];

  for (const [name, src] of modules) {
    await new Promise((resolve) => {
      const s = document.createElement('script');
      s.src = src;
      s.defer = false;
      s.onload = () => {
        const init = window[`operadInit_${name}`];
        if (typeof init === 'function') {
          try { init(runId); } catch (err) { console.error(`init ${name} failed`, err); }
        }
        resolve();
      };
      s.onerror = () => { console.warn(`panel ${name} script failed to load`); resolve(); };
      document.head.appendChild(s);
    });
  }
})();
