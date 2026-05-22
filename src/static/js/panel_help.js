// Panel-help tooltip positioner.
//
// The tooltip's CSS uses `position: fixed` (so it escapes the panel grid's
// `overflow: hidden` clipping); this script sets the viewport-relative
// top/left whenever the trigger gets pointer/keyboard focus. We delegate at
// the document level so the same listener handles tooltips that arrive via
// htmx swaps without rebinding on every fragment.
//
// Positioning rules:
//   • top = trigger.bottom (flush against the trigger so the cursor can
//     enter the tooltip without crossing a dead gap that would break
//     :hover and dismiss the card before the user could scroll it).
//   • side="left"  → align tooltip's left edge to trigger.left.
//   • side="right" → align tooltip's right edge to trigger.right.
//   • In both cases, clamp horizontally so the card stays inside the
//     viewport with a small inset.

(function () {
  const VIEWPORT_INSET = 8;       // px gap from viewport edges
  const VERTICAL_BUDGET = 0.80;   // matches tw-max-h-[80vh]

  function positionTooltip(root) {
    const trigger = root.firstElementChild;
    const tooltip = root.querySelector('[role="tooltip"]');
    if (!trigger || !tooltip) return;
    const rect = trigger.getBoundingClientRect();
    const side = root.dataset.tooltipSide || "left";

    // Read the tooltip's natural width via offsetWidth (which respects
    // tw-w-80 + tw-max-w-[calc(100vw-2rem)]). offsetWidth is 0 while the
    // tooltip is display:none; force a temporary measurement.
    const prevDisplay = tooltip.style.display;
    tooltip.style.visibility = "hidden";
    tooltip.style.display = "block";
    const ttWidth = tooltip.offsetWidth;
    tooltip.style.display = prevDisplay;
    tooltip.style.visibility = "";

    let left;
    if (side === "right") {
      left = rect.right - ttWidth;
    } else {
      left = rect.left;
    }
    // Clamp horizontally inside the viewport.
    const minLeft = VIEWPORT_INSET;
    const maxLeft = window.innerWidth - ttWidth - VIEWPORT_INSET;
    if (left < minLeft) left = minLeft;
    if (left > maxLeft) left = Math.max(minLeft, maxLeft);

    // Cap height so we don't push the tooltip below the viewport when the
    // trigger is near the bottom of the screen. tw-max-h-[80vh] is the
    // global ceiling; here we tighten it further when the trigger sits low.
    const availableBelow = window.innerHeight - rect.bottom - VIEWPORT_INSET;
    const cap = Math.min(window.innerHeight * VERTICAL_BUDGET, availableBelow);
    tooltip.style.maxHeight = Math.max(120, cap) + "px";

    tooltip.style.top = rect.bottom + "px";
    tooltip.style.left = left + "px";
  }

  function onTriggerEnter(evt) {
    const root = evt.target.closest(".panel-help");
    if (!root) return;
    // Only act on enters into the trigger or its descendants, not the
    // tooltip itself (which would loop the positioning unnecessarily).
    if (evt.target.closest('[role="tooltip"]')) return;
    positionTooltip(root);
  }

  // mouseover bubbles; mouseenter does not. We want a single delegated
  // listener, so use mouseover but filter via closest(".panel-help").
  document.addEventListener("mouseover", onTriggerEnter, true);
  document.addEventListener("focusin", onTriggerEnter, true);
})();
