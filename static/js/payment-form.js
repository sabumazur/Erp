(function () {
  "use strict";

  function updatePaymentTotal() {
    var sum = 0;
    document.querySelectorAll('[name="alloc_amounts"]').forEach(function (el) {
      var v = parseFloat(String(el.value).replace(",", ".")) || 0;
      if (v > 0) sum += v;
    });
    setText("payment-total", sum.toFixed(2));
    var submit = document.getElementById("submit-btn");
    if (submit) submit.disabled = sum <= 0;
  }

  function initPaymentForm() {
    var form = document.getElementById("payment-form");
    if (!form) return;
    document.addEventListener("htmx:afterSettle", function (evt) {
      if (evt.target && evt.target.id === "allocation-tbody") updatePaymentTotal();
    });
    form.addEventListener("input", function (e) {
      if (e.target && e.target.name === "alloc_amounts") updatePaymentTotal();
    });
    updatePaymentTotal();
  }

  window.initPaymentForm = initPaymentForm;
})();
