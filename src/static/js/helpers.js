// Client-side helpers used by hx-vals='js:{...helper()}' attributes.
// Keep these thin — they exist only to collect DOM state into a query payload.

// Collect current filter-form state.
function send_form_Data() {
  const f = document.getElementById("form-search");
  if (!f) return {};
  const survey = f.querySelector("#survey")?.dataset?.survey ?? "lsst";
  const classifier = f.querySelector("#classifier")?.dataset?.classifier ?? "";
  const className = f.querySelector("#class")?.dataset?.value ?? "";
  const probability = f.querySelector("#prob_range")?.value ?? "";
  const oidsRaw = f.querySelector("#objectIds")?.value ?? "";
  const minDet = f.querySelector("#min_detections")?.value ?? "";
  const maxDet = f.querySelector("#max_detections")?.value ?? "";
  return {
    survey,
    classifier: classifier || undefined,
    class_name: className || undefined,
    probability: probability || undefined,
    oid: oidsRaw || undefined,
    n_det_min: minDet || undefined,
    n_det_max: maxDet || undefined,
  };
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

// Used by the dependent-class select: encodes the classes list
// attached to the currently selected classifier.
function send_classes_data() {
  const classifierEl = document.getElementById("classifier");
  const raw = classifierEl?.dataset?.classes ?? "[]";
  let classes = [];
  try {
    classes = JSON.parse(raw);
  } catch {
    classes = [];
  }
  return { classifier_classes: classes };
}

window.send_form_Data = send_form_Data;
window.send_pagination_data = send_pagination_data;
window.send_order_data = send_order_data;
window.send_classes_data = send_classes_data;
