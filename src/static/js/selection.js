/* Cross-panel detection selection.
 *
 * A single `window._selectedIdentifier` (candid / measurement_id) is the
 * source of truth for which detection is "current". Clicks on the light
 * curve or the coordinate-residuals scatter call `setSelectedIdentifier`,
 * which:
 *   1. Updates the identifier.
 *   2. Asks the stamps panel to repaint to that detection.
 *   3. Redraws every participating chart so the selection-highlight plugin
 *      can outline the matching point with a white ring.
 *
 * The highlight plugin itself is registered once with Chart.js; every chart
 * picks it up automatically. The plugin reads the current selection from
 * window and finds any dataset point with a matching `identifier` — so
 * datasets need only include `identifier` per raw point for this to work.
 */
(function () {
  const HIGHLIGHT_CANVAS_CLASSES = ["lightcurve-canvas", "coord-residuals-canvas"];
  const RING_COLOR = "#ffffff";
  const RING_WIDTH = 2;
  const RING_RADIUS = 7;

  const selectionHighlight = {
    id: "selectionHighlight",
    afterDatasetsDraw(chart) {
      const sel = window._selectedIdentifier;
      if (!sel) return;
      const ctx = chart.ctx;
      chart.data.datasets.forEach((ds, dsi) => {
        const meta = chart.getDatasetMeta(dsi);
        ds.data.forEach((p, i) => {
          if (!p || p.identifier !== sel) return;
          const el = meta.data[i];
          if (!el) return;
          ctx.save();
          ctx.strokeStyle = RING_COLOR;
          ctx.lineWidth = RING_WIDTH;
          ctx.beginPath();
          ctx.arc(el.x, el.y, RING_RADIUS, 0, 2 * Math.PI);
          ctx.stroke();
          ctx.restore();
        });
      });
    },
  };

  if (typeof Chart !== "undefined") Chart.register(selectionHighlight);

  window._selectedIdentifier = window._selectedIdentifier || null;

  function redrawHighlightedCharts() {
    if (typeof Chart === "undefined") return;
    HIGHLIGHT_CANVAS_CLASSES.forEach((cls) => {
      document.querySelectorAll(`canvas.${cls}`).forEach((canvas) => {
        const chart = Chart.getChart(canvas);
        if (chart) chart.update("none");
      });
    });
  }

  window.setSelectedIdentifier = function (ident) {
    if (!ident) return;
    window._selectedIdentifier = String(ident);
    if (window.updateStampsForIdentifier) {
      window.updateStampsForIdentifier(window._selectedIdentifier);
    }
    redrawHighlightedCharts();
  };

  // New panels swapped in via htmx should reflect the current selection
  // without the user having to click again.
  document.addEventListener("htmx:afterSwap", () => redrawHighlightedCharts());

  // Generic reset-zoom binder: any button with class `chart-zoom-reset-btn`
  // and a `data-target` pointing to a canvas id resets that canvas's zoom.
  // Shared across light curve + scatter (and any future Chart.js panel)
  // without duplicating wiring.
  function bindResetButtons(root) {
    const scope = root || document;
    scope.querySelectorAll(".chart-zoom-reset-btn").forEach((btn) => {
      if (btn.$bound) return;
      btn.$bound = true;
      btn.addEventListener("click", () => {
        const canvas = document.getElementById(btn.dataset.target);
        if (!canvas || typeof Chart === "undefined") return;
        const chart = Chart.getChart(canvas);
        if (chart && chart.resetZoom) chart.resetZoom();
      });
    });
  }

  document.addEventListener("DOMContentLoaded", () => bindResetButtons(document));
  document.addEventListener("htmx:afterSwap", (evt) => bindResetButtons(evt.detail.target));
})();
