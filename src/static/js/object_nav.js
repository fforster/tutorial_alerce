/* Object-level navigation: prev/next arrow buttons + keyboard arrows walk
 * through the current result set, hopping to the previous/next page when
 * they run out of siblings.
 *
 * State lives on `window._resultsNav`, refreshed every time the results
 * table renders (the table template stamps `data-nav` on #objects_table;
 * we read it here). Cross-page hops re-fetch /htmx/list_objects with the
 * current filter state, parse the response to pick up its `data-nav`, and
 * then open the detail for the first/last OID of the new page.
 */
(function () {
  function readNavFromTable(root) {
    const scope = root || document;
    const table = scope.querySelector ? scope.querySelector("#objects_table") : null;
    if (!table) return null;
    const raw = table.dataset.nav;
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }

  function currentDetailOid() {
    // Prefer the live DOM (detail container carries data-oid); fall back to
    // the URL for the transitional moment right after a hx-swap.
    const el = document.getElementById("object-detail");
    if (el && el.dataset.oid) return el.dataset.oid;
    return new URLSearchParams(window.location.search).get("oid");
  }

  function currentFilters() {
    return (typeof window.send_form_Data === "function")
      ? window.send_form_Data()
      : {};
  }

  function detailUrl(oid) {
    const nav = window._resultsNav || {};
    const survey = nav.survey || currentFilters().survey;
    const classifier = nav.classifier || currentFilters().classifier;
    const parts = [
      `oid=${encodeURIComponent(oid)}`,
      `survey_id=${encodeURIComponent(survey || "")}`,
    ];
    if (classifier) parts.push(`classifier=${encodeURIComponent(classifier)}`);
    return `/htmx/detail?${parts.join("&")}`;
  }

  function openDetail(oid) {
    if (!oid) return;
    // htmx.ajax drives the same swap/push-url machinery as a normal hx-get,
    // so the browser address bar stays in sync with the opened object.
    window.htmx.ajax("GET", detailUrl(oid), "#results-slot");
  }

  async function fetchPageNav(page) {
    const filters = currentFilters();
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") params.append(k, String(v));
    });
    params.set("page", String(page));
    const url = `/htmx/list_objects?${params.toString()}`;
    const resp = await fetch(url, { headers: { "HX-Request": "true" } });
    if (!resp.ok) return null;
    const html = await resp.text();
    // Parse into a detached template so no side effects (inline scripts
    // don't run, no <img> loads) touch the live document.
    const tpl = document.createElement("template");
    tpl.innerHTML = html;
    return readNavFromTable(tpl.content);
  }

  function renderOidList(nav, currentOid) {
    const list = document.getElementById("object-nav-list");
    if (!list) return;
    list.innerHTML = "";
    if (!nav || !nav.oids || !nav.oids.length) return;
    const frag = document.createDocumentFragment();
    nav.oids.forEach((o) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.dataset.oid = o;
      const active = String(o) === String(currentOid);
      // Active chip gets accent border + filled background; inactive chips
      // are muted and pick up the accent on hover.
      // Font size is driven by the parent (scaled to fit in fitOidListFont);
      // per-chip classes only carry padding, border, and active-state colors.
      btn.className = active
        ? "tw-px-1 tw-py-0 tw-rounded tw-border tw-border-accent tw-bg-accent/20 tw-text-text-primary tw-leading-tight tw-flex-none"
        : "tw-px-1 tw-py-0 tw-rounded tw-border tw-border-border tw-text-text-muted tw-leading-tight hover:tw-text-text-primary hover:tw-border-accent tw-flex-none";
      btn.textContent = o;
      btn.title = o;
      frag.appendChild(btn);
    });
    list.appendChild(frag);
    fitOidListFont(list);
    observeOidListWidth();
  }

  // Shrink the container's font-size until all chips fit in one row (no
  // scroll). Baseline is 12px; floor is 6px so text stays legible. Uses
  // scrollWidth/clientWidth, so the measurement is real-DOM accurate.
  function fitOidListFont(list) {
    const MAX_PX = 12;
    const MIN_PX = 6;
    list.style.fontSize = MAX_PX + "px";
    // One reflow-inducing read is enough — if it fits at max, we're done.
    if (list.scrollWidth <= list.clientWidth + 1) return;
    const ratio = list.clientWidth / list.scrollWidth;
    const px = Math.max(MIN_PX, Math.floor(MAX_PX * ratio * 0.98));
    list.style.fontSize = px + "px";
  }

  // Re-fit when the container's own width changes — catches both window
  // resize and sidebar toggle (which doesn't trigger a window resize event).
  // Installed once per list element to survive htmx swaps.
  function observeOidListWidth() {
    const list = document.getElementById("object-nav-list");
    if (!list || list.$roObserved) return;
    list.$roObserved = true;
    if (typeof ResizeObserver === "undefined") return;
    let timer = null;
    new ResizeObserver(() => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        if (list.children.length) fitOidListFont(list);
      }, 50);
    }).observe(list);
  }

  function updateButtons() {
    const wrap = document.getElementById("object-nav");
    if (!wrap) return;
    const nav = window._resultsNav;
    const oid = currentDetailOid();
    const posEl = document.getElementById("object-nav-position");
    renderOidList(nav, oid);
    if (!nav || !nav.oids || !nav.oids.length || !oid) {
      wrap.classList.add("tw-hidden");
      wrap.classList.remove("tw-flex");
      if (posEl) posEl.textContent = "";
      return;
    }
    wrap.classList.remove("tw-hidden");
    wrap.classList.add("tw-flex");
    const pos = nav.oids.indexOf(String(oid));
    const prevBtn = document.getElementById("object-nav-prev");
    const nextBtn = document.getElementById("object-nav-next");
    // At the edge we still enable the button iff there's another page to
    // walk into; otherwise disable.
    if (prevBtn) prevBtn.disabled = !(pos > 0 || nav.has_prev);
    if (nextBtn) {
      nextBtn.disabled = !((pos >= 0 && pos < nav.oids.length - 1) || nav.has_next);
    }
    if (posEl) {
      // "3/20 · page 2" — "?/N" when the current OID isn't in the cached page
      // (e.g. deep-linked from a URL whose filters differ from the sidebar).
      const human = pos >= 0 ? (pos + 1) : "?";
      posEl.textContent = `${human}/${nav.oids.length} · page ${nav.current_page}`;
    }
  }

  async function navObject(direction) {
    const nav = window._resultsNav;
    if (!nav || !nav.oids || !nav.oids.length) return;
    const oid = currentDetailOid();
    if (!oid) return;
    const pos = nav.oids.indexOf(String(oid));
    let target = null;

    if (direction === "next") {
      if (pos >= 0 && pos < nav.oids.length - 1) {
        target = nav.oids[pos + 1];
      } else if (nav.has_next) {
        const newNav = await fetchPageNav(nav.next);
        if (newNav && newNav.oids && newNav.oids.length) {
          window._resultsNav = newNav;
          target = newNav.oids[0];
        }
      }
    } else if (direction === "prev") {
      if (pos > 0) {
        target = nav.oids[pos - 1];
      } else if (nav.has_prev) {
        const newNav = await fetchPageNav(nav.prev);
        if (newNav && newNav.oids && newNav.oids.length) {
          window._resultsNav = newNav;
          target = newNav.oids[newNav.oids.length - 1];
        }
      }
    }
    if (target) openDetail(target);
  }

  window.navObject = navObject;

  function refreshNavState(root) {
    const n = readNavFromTable(root);
    if (n) window._resultsNav = n;
    updateButtons();
  }

  // Keyboard nav: arrow keys walk between objects. Skip when the user is
  // typing in an input, textarea, or contenteditable element — otherwise
  // the filter form becomes unusable.
  function onKeydown(ev) {
    if (ev.key !== "ArrowLeft" && ev.key !== "ArrowRight") return;
    if (ev.altKey || ev.ctrlKey || ev.metaKey || ev.shiftKey) return;
    const t = ev.target;
    if (t) {
      const tag = (t.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select") return;
      if (t.isContentEditable) return;
    }
    // Only act when a detail is actually on screen.
    if (!document.getElementById("object-detail")) return;
    ev.preventDefault();
    navObject(ev.key === "ArrowRight" ? "next" : "prev");
  }

  // Delegate chip clicks on the list container (survives htmx swaps because
  // we listen on document, and the list is re-populated in place).
  function onListClick(ev) {
    const btn = ev.target.closest("#object-nav-list button[data-oid]");
    if (!btn) return;
    ev.preventDefault();
    openDetail(btn.dataset.oid);
  }

  document.addEventListener("DOMContentLoaded", () => {
    refreshNavState(document);
    document.addEventListener("keydown", onKeydown);
    document.addEventListener("click", onListClick);
  });
  document.addEventListener("htmx:afterSwap", (evt) => {
    refreshNavState(evt.detail.target);
  });
})();
