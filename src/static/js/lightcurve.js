/* Light-curve rendering via Chart.js (UMD, vendored).
 *
 * Contract: each <canvas class="lightcurve-canvas" data-lc='...JSON...'> is
 * initialized once on DOMContentLoaded, and again every time htmx swaps new
 * content in (htmx:afterSwap). Re-init destroys any prior chart on the same
 * canvas so detail-view swaps don't leak a chart instance.
 *
 * Two independent toggles control the projection, both handled client-side:
 *   - Diff/Sci: pick difference flux vs science (absolute) flux per point.
 *     Points without sci flux drop out of sci mode.
 *   - Flux/Mag: keep nJy or convert with AB ZP 31.4 (same constant as
 *     normalize.py). Points with flux ≤ 0 drop out of mag mode; Y axis is
 *     reversed in mag mode so brighter sits higher.
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

  function projectPoint(p, axisMode, sourceMode) {
    const flux = sourceMode === "sci" ? p.sci_flux : p.flux;
    const eFlux = sourceMode === "sci" ? p.e_sci_flux : p.e_flux;
    if (flux == null) return null;
    if (axisMode === "mag") {
      if (flux <= 0) return null;
      const mag = AB_ZP_NJY - 2.5 * Math.log10(flux);
      const eMag = eFlux != null ? eFlux / flux / LN10_OVER_2P5 : null;
      return { x: p.mjd, y: mag, e: eMag, identifier: p.identifier, has_stamp: p.has_stamp };
    }
    return { x: p.mjd, y: flux, e: eFlux, identifier: p.identifier, has_stamp: p.has_stamp };
  }

  function buildDatasets(bands, fpBands, axisMode, sourceMode) {
    const project = (pts) => pts.map((p) => projectPoint(p, axisMode, sourceMode)).filter(Boolean);
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

  function applyModes(chart) {
    const raw = chart.$lcRaw;
    if (!raw) return;
    const axisMode = chart.$lcMode;
    const sourceMode = chart.$lcSource;
    chart.data.datasets = buildDatasets(raw.bands, raw.fpBands, axisMode, sourceMode);
    const y = chart.options.scales.y;
    const sciLabel = sourceMode === "sci" ? "science" : "diff";
    if (axisMode === "mag") {
      y.title.text = `Magnitude (AB, ${sciLabel})`;
      y.reverse = true;
    } else {
      y.title.text = `Flux (nJy, ${sciLabel})`;
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
    const initialAxisMode = "flux";
    const initialSourceMode = "diff";

    const chart = new Chart(canvas.getContext("2d"), {
      type: "scatter",
      data: { datasets: buildDatasets(bands, fpBands, initialAxisMode, initialSourceMode) },
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
            title: { display: true, text: "Flux (nJy, diff)", color: "#8b949e" },
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
    chart.$lcMode = initialAxisMode;
    chart.$lcSource = initialSourceMode;
    charts.set(canvas, chart);
  }

  function paintButtons(toggle, btnClass, activeValue, dataKey) {
    toggle.querySelectorAll(btnClass).forEach((b) => {
      const active = b.dataset[dataKey] === activeValue;
      b.setAttribute("aria-pressed", active ? "true" : "false");
      b.classList.toggle("tw-bg-bg-secondary", active);
      b.classList.toggle("tw-text-text-primary", active);
      b.classList.toggle("tw-bg-bg-card", !active);
      b.classList.toggle("tw-text-text-muted", !active);
    });
  }

  function bindToggle(toggle, spec) {
    if (toggle.$bound) return;
    toggle.$bound = true;
    toggle.addEventListener("click", (evt) => {
      const btn = evt.target.closest(spec.btnSelector);
      if (!btn) return;
      const value = btn.dataset[spec.dataKey];
      const canvas = document.getElementById(toggle.dataset.target);
      const chart = canvas && charts.get(canvas);
      if (!chart || chart[spec.chartProp] === value) return;
      chart[spec.chartProp] = value;
      applyModes(chart);
      paintButtons(toggle, spec.btnSelector, value, spec.dataKey);
    });
  }

  function initToggles(root) {
    const scope = root || document;
    scope.querySelectorAll(".lc-mode-toggle").forEach((t) =>
      bindToggle(t, { btnSelector: ".lc-mode-btn", dataKey: "lcMode", chartProp: "$lcMode" })
    );
    scope.querySelectorAll(".lc-source-toggle").forEach((t) =>
      bindToggle(t, { btnSelector: ".lc-source-btn", dataKey: "lcSource", chartProp: "$lcSource" })
    );
  }

  function initAll(root) {
    (root || document).querySelectorAll("canvas.lightcurve-canvas").forEach(initCanvas);
    initToggles(root);
  }

  document.addEventListener("DOMContentLoaded", () => initAll(document));
  document.addEventListener("htmx:afterSwap", (evt) => initAll(evt.detail.target));
})();
