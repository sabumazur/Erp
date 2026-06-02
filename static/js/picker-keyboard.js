/* ============================================================================
   picker-keyboard.js — ↑/↓/Enter navigation for the customer, supplier and
   item pickers.  Non-invasive: relies only on the existing public hooks
   (*PickerHighlight / *PickerSelect / itemPickerConfirm) and the aria-selected
   attribute those functions already set, so no change to the other *-picker.js
   files is required.

   Load order: AFTER customer-picker.js / supplier-picker.js / item-picker.js
   (so the window.* functions exist), e.g. add to base.html:
       <script src="{% static 'js/picker-keyboard.js' %}"></script>

   Behaviour
   ---------
   • ↓ / ↑     move the highlight through the visible result rows (wraps at ends
                only by clamping — first stays first, last stays last).
   • Enter     customer / supplier → selects the highlighted row (or the first
                row if none is highlighted yet) and closes the modal.
                item → confirms the highlighted row via itemPickerConfirm().
   • Keys are ignored while the quick-create panel is showing, and Enter is
     always prevented from bubbling so it can never submit the surrounding form.
   ========================================================================== */
(function () {
  "use strict";

  var PICKERS = [
    {
      modal:     "customerPickerModal",
      tbody:     "customer-picker-tbody",
      highlight: function (tr) { window.customerPickerHighlight(tr); },
      confirm:   function (tr) { tr.click(); }            // runs the row's onclick → select
    },
    {
      modal:     "supplierPickerModal",
      tbody:     "supplier-picker-tbody",
      highlight: function (tr) { window.supplierPickerHighlight(tr); },
      confirm:   function (tr) { tr.click(); }
    },
    {
      modal:     "itemPickerModal",
      tbody:     "picker-tbody",
      highlight: function (tr) { window.itemPickerHighlight(tr); },
      confirm:   function ()   { window.itemPickerConfirm(); }   // uses window.activePickerTr
    }
  ];

  // Visible rows that represent a real record (skip the "no results" row).
  function rowsOf(tbodyId) {
    var tbody = document.getElementById(tbodyId);
    if (!tbody) return [];
    return Array.prototype.filter.call(
      tbody.querySelectorAll("tr"),
      function (tr) { return tr.hasAttribute("data-pk") && tr.offsetParent !== null; }
    );
  }

  function activeIndex(rows) {
    for (var i = 0; i < rows.length; i++) {
      if (rows[i].getAttribute("aria-selected") === "true") return i;
    }
    return -1;
  }

  function step(cfg, dir) {
    var rows = rowsOf(cfg.tbody);
    if (!rows.length) return;
    var idx = activeIndex(rows);
    if (idx === -1) {
      idx = dir > 0 ? 0 : rows.length - 1;
    } else {
      idx = Math.min(rows.length - 1, Math.max(0, idx + dir));
    }
    var tr = rows[idx];
    cfg.highlight(tr);
    tr.scrollIntoView({ block: "nearest" });
  }

  function searchPanelVisible(modal) {
    var panel = modal.querySelector('[id$="-search-panel"]');
    return !panel || !panel.classList.contains("d-none");
  }

  function onKeydown(cfg, modal, e) {
    if (!searchPanelVisible(modal)) return;        // ignore while quick-create is open

    if (e.key === "ArrowDown") {
      e.preventDefault();
      step(cfg, 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      step(cfg, -1);
    } else if (e.key === "Enter") {
      e.preventDefault();                          // never submit the surrounding form
      var rows = rowsOf(cfg.tbody);
      if (!rows.length) return;
      var idx = activeIndex(rows);
      if (idx === -1) {                            // nothing highlighted → take the first match
        idx = 0;
        cfg.highlight(rows[0]);
      }
      cfg.confirm(rows[idx]);
    }
  }

  function wire(cfg) {
    var modal = document.getElementById(cfg.modal);
    if (!modal) return;
    // Listen on the modal so it works whether focus is in the search box or a row.
    modal.addEventListener("keydown", function (e) { onKeydown(cfg, modal, e); });
  }

  function init() { PICKERS.forEach(wire); }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
