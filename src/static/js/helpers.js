// Client-side helpers used by hx-vals='js:{...helper()}' attributes.
// Keep these thin — they exist only to collect DOM state into a query payload
// that htmx serializes onto its outgoing request.

function _val(id) {
  const el = document.getElementById(id);
  if (!el) return "";
  return (el.value ?? "").toString().trim();
}

// Collect current filter-form state.
function send_form_Data() {
  const form = document.getElementById("form-search");
  const survey = form?.dataset?.survey ?? "lsst";

  const classifier = _val("classifier");
  const className = _val("class_name");
  const probability = _val("prob_range");
  const oidsRaw = _val("objectIds");
  const minDet = _val("min_detections");
  const maxDet = _val("max_detections");

  const payload = { survey };
  if (classifier) payload.classifier = classifier;
  if (className) payload.class_name = className;
  if (probability && parseFloat(probability) > 0) payload.probability = probability;
  // `oids` (plural) is the free-text OID-list search. Distinct from the detail
  // view's `oid=` (single-object), which shares the URL namespace but means
  // something different — rename here so a search + detail URL can coexist.
  if (oidsRaw) payload.oids = oidsRaw;
  if (minDet) payload.n_det_min = minDet;
  if (maxDet) payload.n_det_max = maxDet;
  return payload;
}

function send_pagination_data(page) {
  return { page };
}

function send_order_data(order_by, order_mode) {
  return {
    order_by: order_by && order_by !== "None" ? order_by : undefined,
    order_mode: order_mode && order_mode !== "None" ? order_mode : "DESC",
  };
}

// Read the classes[] attached to the currently-selected classifier option.
function send_classes_data() {
  const sel = document.getElementById("classifier");
  if (!sel) return { classifier_classes: [] };
  const opt = sel.options[sel.selectedIndex];
  let classes = [];
  try {
    classes = JSON.parse(opt?.dataset?.classes ?? "[]");
  } catch {
    classes = [];
  }
  return { classifier_classes: classes };
}

window.send_form_Data = send_form_Data;
window.send_pagination_data = send_pagination_data;
window.send_order_data = send_order_data;
window.send_classes_data = send_classes_data;

// Results cache. Every time #results-slot lands on a listing (i.e. contains
// #objects_table), we snapshot the HTML + the URL that was pushed for it.
// The "Back to results" button restores from this cache instead of re-firing
// the upstream ALeRCE API query — which means no network call, no spinner,
// and no perceptible delay.
(function () {
  document.addEventListener("htmx:afterSwap", (evt) => {
    const t = evt.detail && evt.detail.target;
    if (!t || t.id !== "results-slot") return;
    // Auto-hide the search panel when drilling into a detail; auto-show it
    // when returning to a listing. The toggle button remains the manual
    // override — users can re-open the panel mid-detail if they want.
    if (t.querySelector("#object-detail") && window.setSearchPanelVisible) {
      window.setSearchPanelVisible(false);
    } else if (t.querySelector("#objects_table") && window.setSearchPanelVisible) {
      window.setSearchPanelVisible(true);
    }
    if (!t.querySelector("#objects_table")) return;
    window._lastResultsHtml = t.innerHTML;
    window._lastResultsUrl = window.location.pathname + window.location.search;
  });

  function restoreFromCache() {
    const slot = document.getElementById("results-slot");
    if (!slot || !window._lastResultsHtml) return false;
    slot.innerHTML = window._lastResultsHtml;
    // Re-scan for hx-* attributes on rows/pagination so they become active.
    if (window.htmx && window.htmx.process) window.htmx.process(slot);
    if (window._lastResultsUrl) {
      window.history.pushState({}, "", window._lastResultsUrl);
    }
    // Synthetic afterSwap so object_nav.js (and anyone else listening) re-reads
    // the table's data-nav and refreshes the chip row / arrow state.
    document.dispatchEvent(new CustomEvent("htmx:afterSwap", {
      detail: { target: slot },
    }));
    return true;
  }

  function backToResults() {
    if (restoreFromCache()) return;
    // No cache (e.g. the user deep-linked straight into a detail view); fall
    // back to the original re-fetch path.
    const filters = send_form_Data();
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v != null && v !== "") params.append(k, String(v));
    });
    const url = `/htmx/list_objects?${params.toString()}`;
    if (window.htmx) window.htmx.ajax("GET", url, "#results-slot");
  }

  window.backToResults = backToResults;
})();
