/* customer-picker.js — config over picker-core.js createPicker(). */
(function () {
  "use strict";

  function customerPickerSelect(pk, name, rnc, defaultNcfType) {
    var sel = document.getElementById("id_customer");
    if (sel) {
      sel.value = pk;
      sel.dispatchEvent(new Event("change", { bubbles: true }));
    }
    var display = document.getElementById("customer-display-text");
    if (display) {
      display.textContent = rnc ? (name + " (" + rnc + ")") : name;
      display.classList.remove("text-muted", "fst-italic");
    }
    var modal = document.getElementById("customerPickerModal");
    if (modal) bootstrap.Modal.getOrCreateInstance(modal).hide();
  }

  var picker = window.createPicker({
    modalId: "customerPickerModal",
    searchId: "customer-picker-search",
    tbodyId: "customer-picker-tbody",
    searchPanelId: "customer-picker-search-panel",
    createPanelId: "customer-picker-create-panel",
    submitBtnId: "qc-submit-btn",
    nonFieldErrorsId: "qc-non-field-errors",
    fields: [
      { param: "name", id: "qc-name", reset: "", focus: true },
      {
        param: "id_type",
        id: "qc-id-type",
        reset: function (el) { return el.options[0] ? el.options[0].value : ""; },
      },
      { param: "rnc_cedula", id: "qc-rnc", reset: "" },
    ],
    quickCreateUrl: function () { return window.CUSTOMER_QUICK_CREATE_URL; },
    refreshOnShown: true,
    getCurrentPk: function () {
      var sel = document.getElementById("id_customer");
      return sel ? sel.value : "";
    },
    onQuickCreated: function (d) {
      customerPickerSelect(d.pk, d.name, d.rnc_cedula, d.default_ncf_type);
    },
  });

  window.openCustomerPicker = picker.open;
  window.customerPickerSelect = customerPickerSelect;
  window.customerPickerHighlight = picker.highlight;
  window.customerPickerShowCreate = picker.showCreate;
  window.customerPickerShowSearch = picker.showSearch;
  window.customerPickerQuickCreate = picker.quickCreate;
})();
