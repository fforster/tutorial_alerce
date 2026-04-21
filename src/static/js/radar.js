/* Radar plot of classifier probabilities via Chart.js.
 *
 * One canvas carries the *entire* probability payload (all classifier groups)
 * as JSON; the classifier picker switches which group is rendered without
 * another server round trip. Re-init on htmx swap destroys any prior chart
 * so the detail-view re-open path doesn't leak a Chart instance.
 */
(function () {
  const NORMAL_COLOR = "#58a6ff";
  const MAX_COLOR = "#f85149";
  const FILL_COLOR = "rgba(88, 166, 255, 0.2)";

  const charts = new WeakMap();

  function findGroup(ctx, key) {
    return (ctx.groups || []).find((g) => g.key === key) || (ctx.groups || [])[0] || null;
  }

  function buildData(group) {
    const labels = group.classes.map((c) => c.class_name);
    const values = group.classes.map((c) => (c.probability == null ? 0 : c.probability));
    const colors = group.classes.map((c) => (c.is_max ? MAX_COLOR : NORMAL_COLOR));
    return {
      labels,
      datasets: [
        {
          label: group.key,
          data: values,
          backgroundColor: FILL_COLOR,
          borderColor: NORMAL_COLOR,
          borderWidth: 1.5,
          pointBackgroundColor: colors,
          pointBorderColor: colors,
          pointRadius: 3,
          pointHoverRadius: 5,
        },
      ],
    };
  }

  function applyGroup(chart, group) {
    chart.data = buildData(group);
    chart.update();
  }

  function initCanvas(canvas) {
    const payload = canvas.dataset.probs;
    if (!payload) return;
    let ctx;
    try {
      ctx = JSON.parse(payload);
    } catch (e) {
      console.warn("radar: bad JSON payload", e);
      return;
    }
    if (typeof Chart === "undefined") {
      console.warn("radar: Chart.js not loaded yet");
      return;
    }

    const prior = charts.get(canvas);
    if (prior) prior.destroy();

    const group = findGroup(ctx, ctx.default_key);
    if (!group) return;

    const chart = new Chart(canvas.getContext("2d"), {
      type: "radar",
      data: buildData(group),
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          r: {
            beginAtZero: true,
            max: 1,
            ticks: {
              stepSize: 0.2,
              color: "#8b949e",
              backdropColor: "transparent",
            },
            grid: { color: "rgba(139,148,158,0.25)" },
            angleLines: { color: "rgba(139,148,158,0.25)" },
            pointLabels: { color: "#c9d1d9", font: { size: 11 } },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (item) => `${item.label}: ${Number(item.raw).toFixed(3)}`,
            },
          },
        },
      },
    });
    chart.$radarCtx = ctx;
    charts.set(canvas, chart);
  }

  function bindPicker(select) {
    if (select.$bound) return;
    select.$bound = true;
    select.addEventListener("change", () => {
      const canvas = document.getElementById(select.dataset.target);
      const chart = canvas && charts.get(canvas);
      if (!chart) return;
      const group = findGroup(chart.$radarCtx, select.value);
      if (group) applyGroup(chart, group);
    });
  }

  function initAll(root) {
    const scope = root || document;
    scope.querySelectorAll("canvas.radar-canvas").forEach(initCanvas);
    scope.querySelectorAll(".radar-classifier-select").forEach(bindPicker);
  }

  document.addEventListener("DOMContentLoaded", () => initAll(document));
  document.addEventListener("htmx:afterSwap", (evt) => initAll(evt.detail.target));
})();
