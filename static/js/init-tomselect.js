(function () {
  "use strict";

  function makeRenderers() {
    return {
      option: function (data, escape) {
        var rate = data.rate ? '<span class="ts-rate">' + escape(data.rate) + "</span>" : "";
        return '<div class="ts-opt-row"><span class="ts-opt-label">' + escape(data.text) + "</span>" + rate + "</div>";
      },
      item: function (data, escape) {
        return "<div>" + escape(data.text) + "</div>";
      },
      no_results: function (data, escape) {
        return '<div class="no-results">Sin resultados para "' + escape(data.input) + '".</div>';
      },
    };
  }

  function initTom(root) {
    (root || document).querySelectorAll("select[data-tom]:not(.tomselected)").forEach(function (el) {
      var opts = Array.prototype.map.call(el.options, function (o) {
        return { value: o.value, text: o.text, rate: o.dataset.rate || "", disabled: o.disabled };
      });
      var plugins = ["dropdown_input"];
      if (el.multiple) plugins.push("remove_button");
      new TomSelect(el, {
        options: opts,
        items: Array.prototype.filter.call(el.options, function (o) { return o.selected; })
          .map(function (o) { return o.value; }),
        valueField: "value",
        labelField: "text",
        searchField: ["text"],
        maxOptions: null,
        allowEmptyOption: true,
        plugins: plugins,
        dropdownParent: el.closest(".modal, dialog, .app-table-wrap") ? "body" : null,
        placeholder: el.dataset.placeholder || "Seleccione…",
        render: makeRenderers(),
      });
    });
  }

  function destroyIn(node) {
    if (!node || !node.querySelectorAll) return;
    node.querySelectorAll("select.tomselected").forEach(function (el) {
      if (el.tomselect) el.tomselect.destroy();
    });
  }

  document.addEventListener("DOMContentLoaded", function () { initTom(document); });

  // Bootstrap 5 modal focus-trap steals focus from Tom Select dropdowns appended to <body>
  // (dropdownParent:"body"), causing the dropdown to close immediately on click.
  // Our listener is registered before Bootstrap's (added on each modal show), so it
  // fires first and stops Bootstrap from re-focusing the modal.
  document.addEventListener("focusin", function (e) {
    if (e.target && e.target.closest && e.target.closest(".ts-dropdown")) {
      e.stopImmediatePropagation();
    }
  });

  document.addEventListener("shown.bs.modal", function (e) { initTom(e.target); });
  document.addEventListener("hidden.bs.modal", function (e) { destroyIn(e.target); });

  if (window.htmx) {
    document.body.addEventListener("htmx:load", function (e) { initTom(e.target); });
    document.body.addEventListener("htmx:beforeCleanupElement", function (e) { destroyIn(e.target); });
  }

  window.SabSysTom = { init: initTom, destroyIn: destroyIn };
})();
