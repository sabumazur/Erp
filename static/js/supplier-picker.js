/* supplier-picker.js — config over picker-core.js createPicker(). */
(function () {
  "use strict";

  function supplierPickerSelect(pk, name, rncCedula) {
    var sel = document.getElementById("id_supplier");
    if (sel) {
      sel.value = pk;
      htmx.trigger(sel, "change");
    }
    var display = document.getElementById("supplier-display-text");
    if (display) {
      display.textContent = rncCedula ? (name + " (" + rncCedula + ")") : name;
      display.classList.remove("text-muted", "fst-italic");
    }
    var modal = document.getElementById("supplierPickerModal");
    if (modal) bootstrap.Modal.getOrCreateInstance(modal).hide();
  }

  var picker = window.createPicker({
    modalId: "supplierPickerModal",
    searchId: "supplier-picker-search",
    tbodyId: "supplier-picker-tbody",
    searchPanelId: "supplier-picker-search-panel",
    createPanelId: "supplier-picker-create-panel",
    submitBtnId: "qs-submit-btn",
    nonFieldErrorsId: "qs-non-field-errors",
    fields: [
      { param: "name", id: "qs-name", reset: "", focus: true },
      { param: "id_type", id: "qs-id-type", reset: "RNC", fallback: "RNC" },
      { param: "rnc_cedula", id: "qs-rnc-cedula", reset: "" },
    ],
    quickCreateUrl: function () { return window.SUPPLIER_QUICK_CREATE_URL; },
    refreshOnShown: true,
    getCurrentPk: function () {
      var sel = document.getElementById("id_supplier");
      return sel ? sel.value : "";
    },
    onQuickCreated: function (d) {
      supplierPickerSelect(d.pk, d.name, d.rnc_cedula);
    },
  });

  window.openSupplierPicker = picker.open;
  window.supplierPickerSelect = supplierPickerSelect;
  window.supplierPickerHighlight = picker.highlight;
  window.supplierPickerShowCreate = picker.showCreate;
  window.supplierPickerShowSearch = picker.showSearch;
  window.supplierPickerQuickCreate = picker.quickCreate;
})();
