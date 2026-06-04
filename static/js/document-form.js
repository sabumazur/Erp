(function () {
  "use strict";

  function itemRow() {
    return {
      qty: 1,
      price: 0,
      rate: "RATE_18",
      rateMap: { EXEMPT: 0, RATE_0: 0, RATE_16: 0.16, RATE_18: 0.18 },
      init: function () {
        var row = this.$el;
        var qEl = row.querySelector('[name$="-quantity"]');
        var pEl = row.querySelector('[name$="-unit_price"]');
        var rEl = row.querySelector('[name$="-itbis_rate"]');
        if (qEl) this.qty = parseInt(qEl.value, 10) || 1;
        if (pEl) this.price = parseFloat(pEl.value) || 0;
        if (rEl) this.rate = rEl.value || "RATE_18";
        this.$nextTick(function () { recalcGrandTotal(); });
      },
      subtotal: function () { return this.qty * this.price; },
      itbisAmt: function () { return this.subtotal() * (this.rateMap[this.rate] || 0); },
      rowTotal: function () { return this.subtotal() + this.itbisAmt(); },
      fmt: function (n) { return n.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ","); },
      fmtSubtotal: function () { return this.fmt(this.subtotal()); },
      fmtItbis: function () { return this.fmt(this.itbisAmt()); },
      fmtTotal: function () { return this.fmt(this.rowTotal()); },
      recalc: function () { recalcGrandTotal(); },
    };
  }

  function deleteRow(btn) {
    var row = btn.closest("tr");
    var next = row && row.nextElementSibling;
    var descRow = next && next.classList.contains("item-row-desc") ? next : null;
    var delEl = row ? row.querySelector('[name$="-DELETE"]') : null;
    if (delEl) {
      delEl.checked = true;
      row.style.display = "none";
      if (descRow) descRow.style.display = "none";
    } else if (row) {
      if (descRow) descRow.remove();
      row.remove();
    }
    recalcGrandTotal();
  }

  function addDocumentLine() {
    var tmpl  = document.getElementById("empty-item-row");
    var tbody = document.getElementById("item-tbody");
    var mgmt  = document.querySelector('[name$="-TOTAL_FORMS"]');
    if (!tmpl || !tbody || !mgmt) return;

    var idx  = parseInt(mgmt.value, 10);
    var html = tmpl.innerHTML.replace(/__prefix__/g, String(idx));

    var temp = document.createElement("tbody");
    temp.innerHTML = html;
    var row = temp.firstElementChild;
    if (!row) return;

    tbody.appendChild(row);
    mgmt.value = String(idx + 1);

    if (typeof Alpine !== "undefined") {
      Alpine.initTree(row);
    }
    if (window.SabSysTom) {
      window.SabSysTom.init(row);
    }
    recalcGrandTotal();
  }

  function recalcGrandTotal() {
    var rateMap = { EXEMPT: 0, RATE_0: 0, RATE_16: 0.16, RATE_18: 0.18 };
    var subtotal = 0;
    var itbis18 = 0;
    var itbis16 = 0;

    document.querySelectorAll("#item-tbody tr").forEach(function (row) {
      var qEl = row.querySelector('[name$="-quantity"]');
      var pEl = row.querySelector('[name$="-unit_price"]');
      var rEl = row.querySelector('[name$="-itbis_rate"]');
      var dEl = row.querySelector('[name$="-DELETE"]');
      if (!qEl || !pEl || !rEl) return;

      var deleted = dEl && dEl.checked;
      var qty = parseInt(qEl.value, 10) || 0;
      var price = parseFloat(pEl.value) || 0;
      var rate = rEl.value;
      var base = qty * price;
      var itbis = base * (rateMap[rate] || 0);

      var subSpan = row.querySelector(".row-subtotal");
      var itbSpan = row.querySelector(".row-itbis");
      var totSpan = row.querySelector(".row-total");
      if (subSpan) subSpan.textContent = deleted ? "0.00" : formatMoney(base);
      if (itbSpan) itbSpan.textContent = deleted ? "0.00" : formatMoney(itbis);
      if (totSpan) totSpan.textContent = deleted ? "0.00" : formatMoney(base + itbis);

      if (deleted) return;
      subtotal += base;
      if (rate === "RATE_18") itbis18 += itbis;
      else if (rate === "RATE_16") itbis16 += itbis;
    });

    setText("grand-subtotal", formatMoney(subtotal));
    setText("grand-itbis18", formatMoney(itbis18));
    setText("grand-itbis16", formatMoney(itbis16));
    setText("grand-total", formatMoney(subtotal + itbis18 + itbis16));
  }

  function applyCustomerDefaults(pk) {
    var defaults = (window.CUSTOMER_DEFAULTS || {})[pk];
    if (!defaults) return;

    var condSel = document.querySelector('[name="payment_condition"]');
    if (condSel && defaults.payment_condition) {
      if (condSel.tomselect) {
        condSel.tomselect.setValue(defaults.payment_condition, true);
      } else {
        condSel.value = defaults.payment_condition;
      }
    }

    var daysDue = defaults.days_due || 0;
    if (daysDue > 0) {
      var issueDateEl = document.querySelector('[name="issue_date"]');
      var dueDateEl = document.querySelector('[name="due_date"]');
      if (issueDateEl && dueDateEl) {
        var base = issueDateEl.value ? new Date(issueDateEl.value) : new Date();
        base.setDate(base.getDate() + daysDue);
        dueDateEl.value = base.getFullYear() + "-" +
          String(base.getMonth() + 1).padStart(2, "0") + "-" +
          String(base.getDate()).padStart(2, "0");
      }
    }
  }

  function initInvoiceItemFormset() {
    if (!document.getElementById("item-tbody")) return;
    recalcGrandTotal();

    var tbody = document.getElementById("item-tbody");
    tbody.addEventListener("input", function (e) {
      var n = e.target.name || "";
      if (n.endsWith("-quantity")) {
        var val = parseFloat(e.target.value);
        var warn = e.target.closest("td") && e.target.closest("td").querySelector(".qty-warning");
        if (warn) warn.classList.toggle("d-none", !val || val <= 0 || Number.isInteger(val));
        recalcGrandTotal();
      } else if (n.endsWith("-unit_price")) {
        recalcGrandTotal();
      }
    });
    tbody.addEventListener("change", function (e) {
      var n = e.target.name || "";
      if (n.endsWith("-itbis_rate")) recalcGrandTotal();
    });

    var pickerModal = document.getElementById("itemPickerModal");
    if (pickerModal) {
      pickerModal.addEventListener("hidden.bs.modal", function () {
        window.activePickerTr = null;
        var selBtn = document.getElementById("picker-select-btn");
        if (selBtn) selBtn.disabled = true;
      });
    }
  }

  function initInvoiceItemHtmx() {
    document.body.addEventListener("htmx:afterSwap", function (e) {
      if (e.detail.target && e.detail.target.id === "item-tbody") {
        var newRow = e.detail.target.lastElementChild;
        if (newRow && typeof Alpine !== "undefined") Alpine.initTree(newRow);
      }
      recalcGrandTotal();
    });
  }

  function initIssueDateDeliverySync() {
    var issueDateEl = document.querySelector('[name="issue_date"]');
    var deliveryDateEl = document.querySelector('[name="delivery_date"]');
    if (!issueDateEl || !deliveryDateEl) return;
    issueDateEl.addEventListener("change", function () {
      deliveryDateEl.value = issueDateEl.value;
    });
  }

  function initCustomerDefaults() {
    var custSel = document.querySelector('[name="customer"]');
    if (!custSel || !window.CUSTOMER_DEFAULTS) return;
    custSel.addEventListener("change", function () {
      applyCustomerDefaults(this.value);
      if (document.querySelector(".module-sale-order")) {
        var deptSel = document.getElementById("id_department");
        if (deptSel) deptSel.value = "";
      }
    });
  }

  function initHeaderCardCollapse() {
    document.querySelectorAll(".doc-order-card").forEach(function (card) {
      var head = card.querySelector(".doc-order-card-head");
      var body = card.querySelector(".doc-order-card-body");
      if (!head || !body || head.dataset.collapseInit) return;
      head.dataset.collapseInit = "1";

      // Wrap the body to animate height via the grid-rows trick. The inner
      // (padding-less) div is the clip surface — body padding lives below it so
      // it collapses fully, leaving only the head visible.
      var wrap = document.createElement("div");
      wrap.className = "doc-card-collapse";
      var inner = document.createElement("div");
      inner.className = "doc-card-collapse-inner";
      body.parentNode.insertBefore(wrap, body);
      wrap.appendChild(inner);
      inner.appendChild(body);

      // Turn the head into an accessible toggle with a chevron affordance.
      head.classList.add("is-toggle");
      head.setAttribute("role", "button");
      head.setAttribute("tabindex", "0");
      var chev = document.createElement("i");
      chev.className = "bi bi-chevron-down doc-card-chevron";
      chev.setAttribute("aria-hidden", "true");
      head.appendChild(chev);

      // Persist per doc-type: strip UUID/numeric segments so create + edit share state.
      var key = "sabsys.docHead." +
        location.pathname.replace(/\/[0-9a-f-]{6,}/gi, "/:id").replace(/\/$/, "");

      function apply(collapsed, persist) {
        card.classList.toggle("is-collapsed", collapsed);
        head.setAttribute("aria-expanded", String(!collapsed));
        if (persist) {
          try { localStorage.setItem(key, collapsed ? "1" : "0"); } catch (e) {}
        }
      }

      var saved = null;
      try { saved = localStorage.getItem(key); } catch (e) {}
      apply(saved === "1", false); // default open

      function toggle() {
        apply(!card.classList.contains("is-collapsed"), true);
      }
      head.addEventListener("click", toggle);
      head.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
      });
    });
  }

  window.itemRow = itemRow;
  window.deleteRow = deleteRow;
  window.recalcGrandTotal = recalcGrandTotal;
  window.initInvoiceItemFormset = initInvoiceItemFormset;
  window.initInvoiceItemHtmx = initInvoiceItemHtmx;
  window.initCustomerDefaults = initCustomerDefaults;
  window.initIssueDateDeliverySync = initIssueDateDeliverySync;
  window.addDocumentLine = addDocumentLine;
  window.initHeaderCardCollapse = initHeaderCardCollapse;

  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-add-line]")) addDocumentLine();
  });
})();
