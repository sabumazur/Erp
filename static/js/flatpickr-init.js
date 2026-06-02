(function () {
  "use strict";

  function initFlatpickr(root) {
    root = root || document;

    root.querySelectorAll(".js-flatpickr-date").forEach(function (el) {
      if (el._flatpickr) return;
      flatpickr(el, {
        dateFormat: "Y-m-d",
        altInput: true,
        altFormat: "m/d/Y",
        allowInput: true,
      });
    });

    root.querySelectorAll(".js-flatpickr-datetime").forEach(function (el) {
      if (el._flatpickr) return;
      flatpickr(el, {
        enableTime: true,
        dateFormat: "Y-m-d H:i",
        altInput: true,
        altFormat: "m/d/Y h:i K",
        allowInput: true,
      });
    });

    root.querySelectorAll(".js-flatpickr-time").forEach(function (el) {
      if (el._flatpickr) return;
      flatpickr(el, {
        enableTime: true,
        noCalendar: true,
        dateFormat: "H:i",
        altInput: true,
        altFormat: "h:i K",
        allowInput: true,
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initFlatpickr(document);
  });

  document.addEventListener("htmx:afterSwap", function (e) {
    initFlatpickr(e.detail.elt);
  });

  document.addEventListener("show.bs.modal", function (e) {
    initFlatpickr(e.target);
  });
})();
