(function () {
  "use strict";

  function openItemPicker(rowEl) {
    if (!window.bootstrap) return;
    window.activeItemRow  = rowEl;
    window.activePickerTr = null;
    itemPickerShowSearch();
    var selBtn = document.getElementById("picker-select-btn");
    if (selBtn) selBtn.disabled = true;
    var searchEl = document.getElementById("picker-search");
    if (searchEl) searchEl.value = "";

    var itemEl    = rowEl ? rowEl.querySelector('[name$="-item"]') : null;
    var currentPk = itemEl ? itemEl.value : "";
    var tbody     = document.getElementById("picker-tbody");
    if (tbody && currentPk) {
      function onItemSwap() {
        tbody.removeEventListener("htmx:afterSwap", onItemSwap);
        var match = tbody.querySelector('tr[data-pk="' + currentPk + '"]');
        if (match) {
          itemPickerHighlight(match);
          match.scrollIntoView({ block: "nearest", behavior: "smooth" });
        }
      }
      tbody.addEventListener("htmx:afterSwap", onItemSwap);
    }

    var modal = document.getElementById("itemPickerModal");
    if (modal) bootstrap.Modal.getOrCreateInstance(modal).show();
    _refreshItemPickerList("");
  }

  function _refreshItemPickerList(q) {
    var searchEl = document.getElementById("picker-search");
    if (!searchEl || !window.htmx) return;
    var url = searchEl.getAttribute("hx-get");
    if (!url) return;
    if (q) url += (url.indexOf("?") === -1 ? "?" : "&") + "q=" + encodeURIComponent(q);
    htmx.ajax("GET", url, { target: "#picker-tbody", swap: "innerHTML" });
  }

  function itemPickerShowCreate() {
    var search = document.getElementById("item-picker-search-panel");
    var create = document.getElementById("item-picker-create-panel");
    if (search) search.classList.add("d-none");
    if (create) create.classList.remove("d-none");
    var nameEl  = document.getElementById("iqc-name");
    var unitEl  = document.getElementById("iqc-unit");
    var priceEl = document.getElementById("iqc-unit-price");
    var rateEl  = document.getElementById("iqc-itbis-rate");
    if (nameEl)  { nameEl.value  = ""; nameEl.classList.remove("is-invalid"); }
    if (unitEl)  { unitEl.value  = "UNIT"; unitEl.classList.remove("is-invalid"); }
    if (priceEl) { priceEl.value = ""; priceEl.classList.remove("is-invalid"); }
    if (rateEl)  { rateEl.value  = "RATE_18"; rateEl.classList.remove("is-invalid"); }
    ["iqc-name-error", "iqc-unit-error", "iqc-unit-price-error", "iqc-itbis-rate-error", "iqc-non-field-errors"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.textContent = "";
    });
    if (nameEl) nameEl.focus();
  }

  function itemPickerShowSearch() {
    var search = document.getElementById("item-picker-search-panel");
    var create = document.getElementById("item-picker-create-panel");
    if (search) search.classList.remove("d-none");
    if (create) create.classList.add("d-none");
    ["iqc-name", "iqc-unit", "iqc-unit-price", "iqc-itbis-rate"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.classList.remove("is-invalid");
    });
    ["iqc-name-error", "iqc-unit-error", "iqc-unit-price-error", "iqc-itbis-rate-error", "iqc-non-field-errors"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.textContent = "";
    });
  }

  function itemPickerQuickCreate() {
    var name      = (document.getElementById("iqc-name")       || {}).value || "";
    var unit      = (document.getElementById("iqc-unit")       || {}).value || "UNIT";
    var unitPrice = (document.getElementById("iqc-unit-price") || {}).value || "";
    var itbisRate = (document.getElementById("iqc-itbis-rate") || {}).value || "RATE_18";
    var csrf      = (document.querySelector("[name=csrfmiddlewaretoken]") || {}).value || "";
    var btn       = document.getElementById("iqc-submit-btn");
    if (btn) btn.disabled = true;

    fetch(window.ITEM_QUICK_CREATE_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-CSRFToken": csrf,
      },
      body: "name=" + encodeURIComponent(name) +
            "&unit=" + encodeURIComponent(unit) +
            "&unit_price=" + encodeURIComponent(unitPrice) +
            "&itbis_rate=" + encodeURIComponent(itbisRate),
    })
    .then(function (resp) {
      return resp.json().then(function (data) { return { status: resp.status, data: data }; });
    })
    .then(function (result) {
      if (btn) btn.disabled = false;
      if (result.status === 200) {
        var d = result.data;
        itemPickerShowSearch();
        _refreshItemPickerList(d.name || "");
        setTimeout(function () {
          if (window.activeItemRow) {
            var formRow = window.activeItemRow;
            var next    = formRow.nextElementSibling;
            var descEl  = formRow.querySelector('[name$="-description"]') ||
                          (next && next.querySelector('[name$="-description"]'));
            var priceEl = formRow.querySelector('[name$="-unit_price"]');
            var qtyEl   = formRow.querySelector('[name$="-quantity"]');
            var rateEl  = formRow.querySelector('[name$="-itbis_rate"]');
            var itemEl  = formRow.querySelector('[name$="-item"]');
            if (descEl)  descEl.value  = d.name;
            if (itemEl)  itemEl.value  = d.pk;
            if (priceEl) priceEl.value = d.unit_price;
            if (qtyEl)   qtyEl.value   = "1";
            if (rateEl)  rateEl.value  = d.itbis_rate;
            if (typeof Alpine !== "undefined") {
              try {
                Alpine.evaluate(formRow, "price = " + (parseFloat(d.unit_price) || 0) +
                  ", qty = 1, rate = '" + (d.itbis_rate || "RATE_18") + "'");
              } catch (err) {}
            }
            window.recalcGrandTotal();
          }
          var modal = document.getElementById("itemPickerModal");
          if (modal) bootstrap.Modal.getOrCreateInstance(modal).hide();
        }, 600);
      } else {
        var errors   = result.data.errors || {};
        var fieldMap = { name: "iqc-name", unit: "iqc-unit", unit_price: "iqc-unit-price", itbis_rate: "iqc-itbis-rate" };
        Object.keys(fieldMap).forEach(function (field) {
          var inputEl = document.getElementById(fieldMap[field]);
          var errEl   = document.getElementById(fieldMap[field] + "-error");
          if (errors[field] && errors[field].length) {
            if (inputEl) inputEl.classList.add("is-invalid");
            if (errEl)   errEl.textContent = errors[field][0];
          }
        });
        var nonField = errors["__all__"] || errors["non_field_errors"] || [];
        var nfEl = document.getElementById("iqc-non-field-errors");
        if (nfEl) nfEl.textContent = nonField.join(" ");
      }
    })
    .catch(function () {
      if (btn) btn.disabled = false;
    });
  }

  function itemPickerHighlight(tr) {
    document.querySelectorAll("#picker-tbody .item-picker-row").forEach(function (r) {
      r.removeAttribute("aria-selected");
    });
    tr.setAttribute("aria-selected", "true");
    window.activePickerTr = tr;
    var selBtn = document.getElementById("picker-select-btn");
    if (selBtn) selBtn.disabled = false;
  }

  function itemPickerConfirm() {
    var tr = window.activePickerTr;
    if (!tr || !window.activeItemRow) return;
    pickItemRow(window.activeItemRow, tr);
    var modal = document.getElementById("itemPickerModal");
    if (modal) bootstrap.Modal.getOrCreateInstance(modal).hide();
    window.activePickerTr = null;
  }

  function pickItemRow(formRow, catalogTr) {
    var pk    = catalogTr.dataset.pk;
    var name  = catalogTr.dataset.name;
    var price = catalogTr.dataset.unitPrice;
    var rate  = catalogTr.dataset.itbisRate;

    var next    = formRow.nextElementSibling;
    var descEl  = formRow.querySelector('[name$="-description"]') ||
                  (next && next.querySelector('[name$="-description"]'));
    var priceEl = formRow.querySelector('[name$="-unit_price"]');
    var qtyEl   = formRow.querySelector('[name$="-quantity"]');
    var rateEl  = formRow.querySelector('[name$="-itbis_rate"]');
    var itemEl  = formRow.querySelector('[name$="-item"]');

    if (descEl)  descEl.value  = name;
    if (itemEl)  itemEl.value  = pk;
    if (priceEl) priceEl.value = price;
    if (qtyEl)   qtyEl.value   = "1";
    if (rateEl)  rateEl.value  = rate;

    if (typeof Alpine !== "undefined") {
      try {
        Alpine.evaluate(formRow, "price = " + (parseFloat(price) || 0) +
          ", qty = 1, rate = '" + (rate || "RATE_18") + "'");
      } catch (err) {}
    }
    var codeEl = formRow.querySelector('.doc-line-code');
    if (codeEl) codeEl.textContent = catalogTr.dataset.code || "";
    window.recalcGrandTotal();
  }

  function pickCatalogItem(btn) {
    var formRow = window.activeItemRow;
    if (!formRow) return;

    var name  = btn.dataset.desc;
    var price = btn.dataset.price;
    var rate  = btn.dataset.rate;
    var pk    = btn.dataset.pk;

    var next    = formRow.nextElementSibling;
    var descEl  = formRow.querySelector('[name$="-description"]') ||
                  (next && next.querySelector('[name$="-description"]'));
    var priceEl = formRow.querySelector('[name$="-unit_price"]');
    var qtyEl   = formRow.querySelector('[name$="-quantity"]');
    var rateEl  = formRow.querySelector('[name$="-itbis_rate"]');
    var itemEl  = formRow.querySelector('[name$="-item"]');

    if (descEl)  descEl.value  = name;
    if (itemEl)  itemEl.value  = pk;
    if (priceEl) priceEl.value = price;
    if (qtyEl)   qtyEl.value   = "1";
    if (rateEl)  rateEl.value  = rate;

    if (typeof Alpine !== "undefined") {
      try {
        Alpine.evaluate(formRow, "price = " + (parseFloat(price) || 0) +
          ", qty = 1, rate = '" + (rate || "RATE_18") + "'");
      } catch (err) {}
    }
    window.recalcGrandTotal();
  }

  window.openItemPicker = openItemPicker;
  window.itemPickerHighlight = itemPickerHighlight;
  window.itemPickerConfirm = itemPickerConfirm;
  window.itemPickerShowCreate = itemPickerShowCreate;
  window.itemPickerShowSearch = itemPickerShowSearch;
  window.itemPickerQuickCreate = itemPickerQuickCreate;
  window.pickCatalogItem = pickCatalogItem;
})();
