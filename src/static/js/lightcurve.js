/* Light-curve rendering via Chart.js (UMD, vendored).
 *
 * Contract: each <canvas class="lightcurve-canvas" data-lc='...JSON...'> is
 * initialized once on DOMContentLoaded, and again every time htmx swaps new
 * content in (htmx:afterSwap). Re-init destroys any prior chart on the same
 * canvas so detail-view swaps don't leak a chart instance.
 *
 * Flux is plotted in nJy (already normalized server-side). In "mag" mode we
 * convert on the client with AB ZP 31.4 (same constant as normalize.py) and
 * reverse the Y axis so brighter sits higher. Points with flux ≤ 0 can't be
 * converted; they're dropped only in mag mode.
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

  const AB_ZP_NJY = 31.4;
  const LN10_OVER_2P5 = Math.log(10) / 2.5;

  // Canvas element → Chart instance, so we can destroy before re-initializing.
  const charts = new WeakMap();

  function projectPoint(p, mode) {
    if (mode === "mag") {
      if (p.flux == null || p.flux <= 0) return null;
      const mag = AB_ZP_NJY - 2.5 * Math.log10(p.flux);
      const eMag = p.e_flux != null ? p.e_flux / p.flux / LN10_OVER_2P5 : null;
      return { x: p.mjd, y: mag, e: eMag, identifier: p.identifier, has_stamp: p.has_stamp };
    }
    return { x: p.mjd, y: p.flux, e: p.e_flux, identifier: p.identifier, has_stamp: p.has_stamp };
  }

  function buildDatasets(bands, fpBands, mode) {
    const project = (pts) => pts.map((p) => projectPoint(p, mode)).filter(Boolean);
    const det = bands.map((b) => ({
      label: b.name,
      data: project(b.points),
      backgroundColor: BAND_COLORS[b.name] || BAND_COLORS.unknown,
      borderColor: BAND_COLORS[b.name] || BAND_COLORS.unknown,
      showLine: false,
      pointRadius: 3,
      pointHoverRadius: 5,
    }));
    // FP uses the same band colors but rendered as hollow triangles so they
    // read as distinct from detections without crowding the legend/tooltip.
    // FP rows don't carry a stamp identifier, so clicks on them are no-ops.
    const fp = (fpBands || []).map((b) => ({
      label: `${b.name} (FP)`,
      data: project(b.points),
      backgroundColor: "transparent",
      borderColor: BAND_COLORS[b.name] || BAND_COLORS.unknown,
      borderWidth: 1,
      pointStyle: "triangle",
      showLine: false,
      pointRadius: 3,
      pointHoverRadius: 5,
    }));
    return [...det, ...fp];
  }

  function applyMode(chart, mode) {
    const raw = chart.$lcRaw;
    if (!raw) return;
    chart.$lcMode = mode;
    chart.data.datasets = buildDatasets(raw.bands, raw.fpBands, mode);
    const y = chart.options.scales.y;
    if (mode === "mag") {
      y.title.text = "Magnitude (AB)";
      y.reverse = true;
    } else {
      y.title.text = "Flux (nJy)";
      y.reverse = false;
    }
    chart.update();
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

    const bands = data.bands || [];
    const fpBands = data.forced_phot_bands || [];
    const initialMode = "flux";

    const chart = new Chart(canvas.getContext("2d"), {
      type: "scatter",
      data: { datasets: buildDatasets(bands, fpBands, initialMode) },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        onClick: (_evt, elements) => {
          if (!elements.length) return;
          const { datasetIndex, index } = elements[0];
          const p = chart.data.datasets[datasetIndex].data[index];
          if (p?.has_stamp && p.identifier && window.updateStampsForIdentifier) {
            window.updateStampsForIdentifier(p.identifier);
          }
        },
        onHover: (evt, elements) => {
          const target = evt.native?.target;
          if (!target) return;
          const clickable = elements.some((el) => {
            const p = chart.data.datasets[el.datasetIndex].data[el.index];
            return p?.has_stamp && p.identifier;
          });
          target.style.cursor = clickable ? "pointer" : "default";
        },
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
                const unit = chart.$lcMode === "mag" ? "mag" : "nJy";
                return `${ctx.dataset.label}: ${p.y.toPrecision(4)}${err} ${unit} @ MJD ${p.x.toFixed(3)}`;
              },
            },
          },
        },
      },
    });
    chart.$lcRaw = { bands, fpBands };
    chart.$lcMode = initialMode;
    charts.set(canvas, chart);
  }

  function initToggles(root) {
    (root || document).querySelectorAll(".lc-mode-toggle").forEach((toggle) => {
      if (toggle.$bound) return;
      toggle.$bound = true;
      toggle.addEventListener("click", (evt) => {
        const btn = evt.target.closest(".lc-mode-btn");
        if (!btn) return;
        const mode = btn.dataset.lcMode;
        const canvas = document.getElementById(toggle.dataset.target);
        const chart = canvas && charts.get(canvas);
        if (!chart || chart.$lcMode === mode) return;
        applyMode(chart, mode);
        toggle.querySelectorAll(".lc-mode-btn").forEach((b) => {
          const active = b.dataset.lcMode === mode;
          b.setAttribute("aria-pressed", active ? "true" : "false");
          b.classList.toggle("tw-bg-bg-secondary", active);
          b.classList.toggle("tw-text-text-primary", active);
          b.classList.toggle("tw-bg-bg-card", !active);
          b.classList.toggle("tw-text-text-muted", !active);
        });
      });
    });
  }

  function initAll(root) {
    (root || document).querySelectorAll("canvas.lightcurve-canvas").forEach(initCanvas);
    initToggles(root);
  }

  document.addEventListener("DOMContentLoaded", () => initAll(document));
  document.addEventListener("htmx:afterSwap", (evt) => initAll(evt.detail.target));
})();
