/* Light-curve rendering via Chart.js (UMD, vendored).
 *
 * Contract: each <canvas class="lightcurve-canvas" data-lc='...JSON...'> is
 * initialized once on DOMContentLoaded, and again every time htmx swaps new
 * content in (htmx:afterSwap). Re-init destroys any prior chart on the same
 * canvas so detail-view swaps don't leak a chart instance.
 *
 * Flux is plotted in nJy (already normalized server-side). Y axis starts at
 * 0 so diff-flux detections sit above the baseline visibly.
 */
(function () {
  const BAND_COLORS = {
    u: "#56B4E9",
    g: "#009E73",
    r: "#D55E00",
    i: "#E69F00",
    z: "#CC79A7",
    y: "#0072B2",
    unknown: "#888888",
  };

  // Canvas element → Chart instance, so we can destroy before re-initializing.
  const charts = new WeakMap();

  function buildDatasets(bands) {
    return bands.map((b) => ({
      label: b.name,
      data: b.points.map((p) => ({ x: p.mjd, y: p.flux, e: p.e_flux })),
      backgroundColor: BAND_COLORS[b.name] || BAND_COLORS.unknown,
      borderColor: BAND_COLORS[b.name] || BAND_COLORS.unknown,
      showLine: false,
      pointRadius: 3,
      pointHoverRadius: 5,
    }));
  }

  function initCanvas(canvas) {
    const payload = canvas.dataset.lc;
    if (!payload) return;
    let data;
    try {
      data = JSON.parse(payload);
    } catch (e) {
      console.warn("lightcurve: bad JSON payload", e);
      return;
    }
    if (typeof Chart === "undefined") {
      console.warn("lightcurve: Chart.js not loaded yet");
      return;
    }

    const prior = charts.get(canvas);
    if (prior) prior.destroy();

    const chart = new Chart(canvas.getContext("2d"), {
      type: "scatter",
      data: { datasets: buildDatasets(data.bands || []) },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            type: "linear",
            title: { display: true, text: "MJD", color: "#8b949e" },
            grid: { color: "rgba(139,148,158,0.15)" },
            ticks: { color: "#8b949e" },
          },
          y: {
            title: { display: true, text: "Flux (nJy)", color: "#8b949e" },
            grid: { color: "rgba(139,148,158,0.15)" },
            ticks: { color: "#8b949e" },
          },
        },
        plugins: {
          legend: {
            position: "top",
            labels: { color: "#c9d1d9", boxWidth: 10 },
          },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const p = ctx.raw;
                const err = p.e != null ? ` ± ${p.e.toPrecision(3)}` : "";
                return `${ctx.dataset.label}: ${p.y.toPrecision(4)}${err} nJy @ MJD ${p.x.toFixed(3)}`;
              },
            },
          },
        },
      },
    });
    charts.set(canvas, chart);
  }

  function initAll(root) {
    (root || document).querySelectorAll("canvas.lightcurve-canvas").forEach(initCanvas);
  }

  document.addEventListener("DOMContentLoaded", () => initAll(document));
  document.addEventListener("htmx:afterSwap", (evt) => initAll(evt.detail.target));
})();
