(function () {
  "use strict";

  var picker = window.createPicker({
    modalId:        "supplierPickerModal",
    searchInputId:  "supplier-picker-search",
    tbodyId:        "supplier-picker-tbody",
    searchPanelId:  "supplier-picker-search-panel",
    createPanelId:  "supplier-picker-create-panel",
    submitBtnId:    "qs-submit-btn",
    nonFieldErrorId: "qs-non-field-errors",
    createFields: [
      { id: "qs-name",        bodyKey: "name",       defaultValue: "" },
      { id: "qs-id-type",     bodyKey: "id_type",    defaultValue: "RNC" },
      { id: "qs-rnc-cedula",  bodyKey: "rnc_cedula", defaultValue: "" },
    ],
    errorFieldMap: { name: "qs-name", id_type: "qs-id-type", rnc_cedula: "qs-rnc-cedula" },
    quickCreateUrl: function () { return window.SUPPLIER_QUICK_CREATE_URL; },
    apply: function (pk, data) {
      var sel = document.getElementById("id_supplier");
      if (sel) {
        sel.value = pk;
        sel.dispatchEvent(new Event("change", { bubbles: true }));
      }
      var display = document.getElementById("supplier-display-text");
      if (display) {
        display.textContent = data.rnc_cedula ? (data.name + " (" + data.rnc_cedula + ")") : data.name;
        display.classList.remove("text-muted", "fst-italic");
      }
    },
  });

  function openSupplierPicker() {
    var sel = document.getElementById("id_supplier");
    picker.open(sel ? sel.value : "");
  }

  function supplierPickerSelect(pk, name, rncCedula) {
    picker.select(pk, { name: name, rnc_cedula: rncCedula });
  }

  window.openSupplierPicker        = openSupplierPicker;
  window.supplierPickerSelect      = supplierPickerSelect;
  window.supplierPickerHighlight   = picker.highlight;
  window.supplierPickerShowCreate  = picker.showCreate;
  window.supplierPickerShowSearch  = picker.showSearch;
  window.supplierPickerQuickCreate = picker.quickCreate;
})();
