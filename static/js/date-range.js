// Global date-range constraint: for any form containing both a
// [name="date_from"] and [name="date_to"] input, the "Hasta" date can never
// be earlier than the "Desde" date. Sets the native `min` attribute and a
// custom validity message so the browser blocks submit. Server-side guard
// lives in apps/core/daterange.py. Re-wires on HTMX swaps and modal show.
(function () {
  "use strict";

  var MSG = "La fecha «Hasta» no puede ser anterior a la fecha «Desde».";

  function wire(root) {
    root = root || document;
    root.querySelectorAll('[name="date_from"]').forEach(function (from) {
      var form = from.form;
      if (!form) return;
      var to = form.querySelector('[name="date_to"]');
      if (!to || to._dateRangeWired) return;
      to._dateRangeWired = true;

      function sync() {
        to.min = from.value || "";
        if (from.value && to.value && to.value < from.value) {
          to.setCustomValidity(MSG);
        } else {
          to.setCustomValidity("");
        }
      }

      from.addEventListener("change", sync);
      to.addEventListener("input", sync);
      to.addEventListener("change", sync);
      sync();
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    wire(document);
  });
  document.addEventListener("htmx:afterSwap", function (e) {
    wire(e.detail.elt);
  });
  document.addEventListener("show.bs.modal", function (e) {
    wire(e.target);
  });
})();
