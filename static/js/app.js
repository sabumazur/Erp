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

    // Datatable (loaded per-page on list views)
    if (typeof initDatatableFilters === "function") initDatatableFilters();

    // Document forms (loaded per-page on form views)
    if (typeof initInvoiceItemFormset === "function") initInvoiceItemFormset();
    if (typeof initInvoiceItemHtmx === "function") initInvoiceItemHtmx();
    if (typeof initCustomerDefaults === "function") initCustomerDefaults();
    if (typeof initIssueDateDeliverySync === "function") initIssueDateDeliverySync();
    if (typeof initHeaderCardCollapse === "function") initHeaderCardCollapse();

    // Payment (loaded per-page on payment forms)
    if (typeof initPaymentForm === "function") initPaymentForm();

    // Modals
    initEditableModals();
    initCustomerList();
    initNcfModal();
    initDeptModalClose();
    initConsolidateForm();

    // Dashboard (loaded per-page on dashboard)
    if (typeof initDashboardCharts === "function") initDashboardCharts();
  });
})();
