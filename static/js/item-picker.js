(function () {
  "use strict";

  // Populate a document line-item form row from catalog values.
  // Used by pickItemRow, pickCatalogItem, and the quick-create apply callback.
  function applyToFormRow(formRow, name, pk, price, rate, code) {
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

    var codeEl = formRow.querySelector(".doc-line-code");
    if (codeEl) codeEl.textContent = code || "";

    if (typeof Alpine !== "undefined") {
      try {
        Alpine.evaluate(formRow, "price = " + (parseFloat(price) || 0) +
          ", qty = 1, rate = '" + (rate || "RATE_18") + "'");
      } catch (err) { console.error("[item-picker] Alpine eval failed:", err); }
    }
    window.recalcGrandTotal();
  }

  var picker = window.createPicker({
    modalId:        "itemPickerModal",
    searchInputId:  "picker-search",
    tbodyId:        "picker-tbody",
    searchPanelId:  "item-picker-search-panel",
    createPanelId:  "item-picker-create-panel",
    submitBtnId:    "iqc-submit-btn",
    nonFieldErrorId: "iqc-non-field-errors",
    createFields: [
      { id: "iqc-name",       bodyKey: "name",       defaultValue: "" },
      { id: "iqc-unit",       bodyKey: "unit",       defaultValue: "UNIT" },
      { id: "iqc-unit-price", bodyKey: "unit_price", defaultValue: "" },
      { id: "iqc-itbis-rate", bodyKey: "itbis_rate", defaultValue: "RATE_18" },
    ],
    errorFieldMap: { name: "iqc-name", unit: "iqc-unit", unit_price: "iqc-unit-price", itbis_rate: "iqc-itbis-rate" },
    quickCreateUrl: function () { return window.ITEM_QUICK_CREATE_URL; },
    apply: function (pk, data) {
      if (!window.activeItemRow) return;
      applyToFormRow(window.activeItemRow, data.name, pk, data.unit_price, data.itbis_rate, data.code);
    },
  });

  function openItemPicker(rowEl) {
    if (!window.bootstrap) return;
    window.activeItemRow  = rowEl;
    window.activePickerTr = null;
    picker.showSearch();
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
    picker.refresh("");
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
    applyToFormRow(
      formRow,
      catalogTr.dataset.name,
      catalogTr.dataset.pk,
      catalogTr.dataset.unitPrice,
      catalogTr.dataset.itbisRate,
      catalogTr.dataset.code
    );
  }

  function pickCatalogItem(btn) {
    if (!window.activeItemRow) return;
    applyToFormRow(
      window.activeItemRow,
      btn.dataset.desc,
      btn.dataset.pk,
      btn.dataset.price,
      btn.dataset.rate,
      btn.dataset.code
    );
  }

  window.openItemPicker        = openItemPicker;
  window.itemPickerHighlight   = itemPickerHighlight;
  window.itemPickerConfirm     = itemPickerConfirm;
  window.itemPickerShowCreate  = picker.showCreate;
  window.itemPickerShowSearch  = picker.showSearch;
  window.itemPickerQuickCreate = picker.quickCreate;
  window.pickCatalogItem       = pickCatalogItem;
})();
