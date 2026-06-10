(function () {
  "use strict";

  var picker = window.createPicker({
    modalId:        "customerPickerModal",
    searchInputId:  "customer-picker-search",
    tbodyId:        "customer-picker-tbody",
    searchPanelId:  "customer-picker-search-panel",
    createPanelId:  "customer-picker-create-panel",
    submitBtnId:    "qc-submit-btn",
    nonFieldErrorId: "qc-non-field-errors",
    createFields: [
      { id: "qc-name",    bodyKey: "name",       defaultValue: "" },
      { id: "qc-id-type", bodyKey: "id_type",    defaultValue: "" },
      { id: "qc-rnc",     bodyKey: "rnc_cedula", defaultValue: "" },
    ],
    errorFieldMap: { name: "qc-name", id_type: "qc-id-type", rnc_cedula: "qc-rnc" },
    quickCreateUrl: function () { return window.CUSTOMER_QUICK_CREATE_URL; },
    apply: function (pk, data) {
      var sel = document.getElementById("id_customer");
      if (sel) {
        sel.value = pk;
        sel.dispatchEvent(new Event("change", { bubbles: true }));
      }
      var display = document.getElementById("customer-display-text");
      if (display) {
        display.textContent = data.rnc_cedula ? (data.name + " (" + data.rnc_cedula + ")") : data.name;
        display.classList.remove("text-muted", "fst-italic");
      }
    },
  });

  function openCustomerPicker() {
    var sel = document.getElementById("id_customer");
    picker.open(sel ? sel.value : "");
  }

  function customerPickerSelect(pk, name, rnc) {
    picker.select(pk, { name: name, rnc_cedula: rnc });
  }

  window.openCustomerPicker        = openCustomerPicker;
  window.customerPickerSelect      = customerPickerSelect;
  window.customerPickerHighlight   = picker.highlight;
  window.customerPickerShowCreate  = picker.showCreate;
  window.customerPickerShowSearch  = picker.showSearch;
  window.customerPickerQuickCreate = picker.quickCreate;
})();
