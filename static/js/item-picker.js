/* item-picker.js — config over picker-core.js createPicker(), plus the
   row-fill / confirm state that is unique to the item picker. */
(function () {
  "use strict";

  // Writes a catalog selection into the active formset row and syncs the
  // row's Alpine state. d: { pk, name, price, rate, code }
  function fillRow(formRow, d) {
    var next    = formRow.nextElementSibling;
    var descEl  = formRow.querySelector('[name$="-description"]') ||
                  (next && next.querySelector('[name$="-description"]'));
    var priceEl = formRow.querySelector('[name$="-unit_price"]');
    var qtyEl   = formRow.querySelector('[name$="-quantity"]');
    var rateEl  = formRow.querySelector('[name$="-itbis_rate"]');
    var itemEl  = formRow.querySelector('[name$="-item"]');

    if (descEl)  descEl.value  = d.name;
    if (itemEl)  itemEl.value  = d.pk;
    if (priceEl) priceEl.value = d.price;
    if (qtyEl)   qtyEl.value   = "1";
    if (rateEl)  rateEl.value  = d.rate;

    var codeEl = formRow.querySelector(".doc-line-code");
    if (codeEl) codeEl.textContent = d.code || "";

    if (typeof Alpine !== "undefined") {
      try {
        Alpine.evaluate(formRow, "price = " + (parseFloat(d.price) || 0) +
          ", qty = 1, rate = '" + (d.rate || "RATE_18") + "'");
      } catch (err) {}
    }
    window.recalcGrandTotal();
  }

  var picker = window.createPicker({
    modalId: "itemPickerModal",
    searchId: "picker-search",
    tbodyId: "picker-tbody",
    searchPanelId: "item-picker-search-panel",
    createPanelId: "item-picker-create-panel",
    submitBtnId: "iqc-submit-btn",
    nonFieldErrorsId: "iqc-non-field-errors",
    fields: [
      { param: "name", id: "iqc-name", reset: "", focus: true },
      { param: "unit", id: "iqc-unit", reset: "UNIT", fallback: "UNIT" },
      { param: "unit_price", id: "iqc-unit-price", reset: "" },
      { param: "itbis_rate", id: "iqc-itbis-rate", reset: "RATE_18", fallback: "RATE_18" },
    ],
    quickCreateUrl: function () { return window.ITEM_QUICK_CREATE_URL; },
    refreshOnShown: false,
    onOpen: function (rowEl) {
      window.activeItemRow  = rowEl;
      window.activePickerTr = null;
      var selBtn = document.getElementById("picker-select-btn");
      if (selBtn) selBtn.disabled = true;
    },
    getCurrentPk: function (rowEl) {
      var itemEl = rowEl ? rowEl.querySelector('[name$="-item"]') : null;
      return itemEl ? itemEl.value : "";
    },
    onHighlight: function (tr) {
      window.activePickerTr = tr;
      var selBtn = document.getElementById("picker-select-btn");
      if (selBtn) selBtn.disabled = false;
    },
    onQuickCreated: function (d) {
      if (window.activeItemRow) {
        fillRow(window.activeItemRow, {
          pk: d.pk, name: d.name, price: d.unit_price, rate: d.itbis_rate, code: d.code,
        });
      }
      var modal = document.getElementById("itemPickerModal");
      if (modal) bootstrap.Modal.getOrCreateInstance(modal).hide();
    },
  });

  function itemPickerConfirm() {
    var tr = window.activePickerTr;
    if (!tr || !window.activeItemRow) return;
    fillRow(window.activeItemRow, {
      pk: tr.dataset.pk,
      name: tr.dataset.name,
      price: tr.dataset.unitPrice,
      rate: tr.dataset.itbisRate,
      code: tr.dataset.code,
    });
    var modal = document.getElementById("itemPickerModal");
    if (modal) bootstrap.Modal.getOrCreateInstance(modal).hide();
    window.activePickerTr = null;
  }

  function pickCatalogItem(btn) {
    var formRow = window.activeItemRow;
    if (!formRow) return;
    fillRow(formRow, {
      pk: btn.dataset.pk,
      name: btn.dataset.desc,
      price: btn.dataset.price,
      rate: btn.dataset.rate,
      code: btn.dataset.code,
    });
  }

  window.openItemPicker = picker.open;
  window.itemPickerHighlight = picker.highlight;
  window.itemPickerConfirm = itemPickerConfirm;
  window.itemPickerShowCreate = picker.showCreate;
  window.itemPickerShowSearch = picker.showSearch;
  window.itemPickerQuickCreate = picker.quickCreate;
  window.pickCatalogItem = pickCatalogItem;
})();
