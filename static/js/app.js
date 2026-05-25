(function () {
  "use strict";

  // Boot — all init functions are defined in their own files loaded before this one.
  // If a page doesn't have a given element, each init function no-ops gracefully.
  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  ready(function () {
    // Shell
    initToasts();
    initPasswordToggles();
    initSidebarState();
    initAutoPrint();
    if (typeof initSessionTimeout === "function") initSessionTimeout();

    // Datatable
    initDatatableFilters();

    // Document forms
    initInvoiceItemFormset();
    initInvoiceItemHtmx();
    initCustomerDefaults();
    initIssueDateDeliverySync();

    // Payment
    initPaymentForm();

    // Modals
    initItemModal();
    initModuleModal();
    initPaymentTermModal();
    initCustomerList();
    initNcfModal();
    initDeptModalClose();
    initConsolidateForm();

    // Dashboard
    initDashboardCharts();
  });
})();
