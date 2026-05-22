(function () {
  "use strict";

  function openCustomerPicker() {
    if (!window.bootstrap) return;
    var modal = document.getElementById("customerPickerModal");
    if (!modal) return;
    customerPickerShowSearch();
    var searchInput = document.getElementById("customer-picker-search");
    var custSel     = document.getElementById("id_customer");
    var currentPk   = custSel ? custSel.value : "";
    bootstrap.Modal.getOrCreateInstance(modal).show();
    modal.addEventListener("shown.bs.modal", function handler() {
      if (searchInput) {
        searchInput.value = "";
        searchInput.focus();
        var tbody = document.getElementById("customer-picker-tbody");
        if (tbody && currentPk) {
          function onCustSwap() {
            tbody.removeEventListener("htmx:afterSwap", onCustSwap);
            var match = tbody.querySelector('tr[data-pk="' + currentPk + '"]');
            if (match) {
              customerPickerHighlight(match);
              match.scrollIntoView({ block: "nearest", behavior: "smooth" });
            }
          }
          tbody.addEventListener("htmx:afterSwap", onCustSwap);
        }
        _refreshCustomerPickerList("");
      }
      modal.removeEventListener("shown.bs.modal", handler);
    });
  }

  function customerPickerHighlight(tr) {
    var tbody = document.getElementById("customer-picker-tbody");
    if (tbody) {
      tbody.querySelectorAll("tr").forEach(function (r) { r.removeAttribute("aria-selected"); });
    }
    tr.setAttribute("aria-selected", "true");
  }

  function _refreshCustomerPickerList(q) {
    var searchInput = document.getElementById("customer-picker-search");
    if (!searchInput || !window.htmx) return;
    var url = searchInput.getAttribute("hx-get");
    if (!url) return;
    if (q) url += (url.indexOf("?") === -1 ? "?" : "&") + "q=" + encodeURIComponent(q);
    htmx.ajax("GET", url, { target: "#customer-picker-tbody", swap: "innerHTML" });
  }

  function customerPickerSelect(pk, name, rnc, defaultNcfType) {
    var sel = document.getElementById("id_customer");
    if (sel) {
      sel.value = pk;
      // Trigger HTMX change for SaleOrder department reload
      htmx.trigger(sel, "change");
    }
    var display = document.getElementById("customer-display-text");
    if (display) {
      display.textContent = rnc ? (name + " (" + rnc + ")") : name;
      display.classList.remove("text-muted", "fst-italic");
    }
    var modal = document.getElementById("customerPickerModal");
    if (modal) bootstrap.Modal.getOrCreateInstance(modal).hide();
  }

  function customerPickerShowCreate() {
    var search  = document.getElementById("customer-picker-search-panel");
    var create  = document.getElementById("customer-picker-create-panel");
    if (search) search.classList.add("d-none");
    if (create) create.classList.remove("d-none");
    var nameEl   = document.getElementById("qc-name");
    var idTypeEl = document.getElementById("qc-id-type");
    var rncEl    = document.getElementById("qc-rnc");
    if (nameEl)   { nameEl.value   = ""; nameEl.classList.remove("is-invalid"); }
    if (idTypeEl) { idTypeEl.value = idTypeEl.options[0] ? idTypeEl.options[0].value : ""; idTypeEl.classList.remove("is-invalid"); }
    if (rncEl)    { rncEl.value    = ""; rncEl.classList.remove("is-invalid"); }
    ["qc-name-error", "qc-id-type-error", "qc-rnc-error", "qc-non-field-errors"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.textContent = "";
    });
    if (nameEl) nameEl.focus();
  }

  function customerPickerShowSearch() {
    var search = document.getElementById("customer-picker-search-panel");
    var create = document.getElementById("customer-picker-create-panel");
    if (search) search.classList.remove("d-none");
    if (create) create.classList.add("d-none");
    // Clear quick-create error state
    ["qc-name", "qc-rnc", "qc-id-type"].forEach(function(id) {
      var el = document.getElementById(id);
      if (el) el.classList.remove("is-invalid");
    });
    ["qc-name-error", "qc-rnc-error", "qc-id-type-error", "qc-non-field-errors"].forEach(function(id) {
      var el = document.getElementById(id);
      if (el) el.textContent = "";
    });
  }

  function customerPickerQuickCreate() {
    var name = (document.getElementById("qc-name") || {}).value || "";
    var idType = (document.getElementById("qc-id-type") || {}).value || "";
    var rnc = (document.getElementById("qc-rnc") || {}).value || "";
    // Safe: customer_picker_modal.html is always included inside the <form> tag,
    // so the CSRF token input is always a sibling of the modal.
    var csrf = (document.querySelector("[name=csrfmiddlewaretoken]") || {}).value || "";
    var btn = document.getElementById("qc-submit-btn");
    if (btn) { btn.disabled = true; }

    var body = "name=" + encodeURIComponent(name) +
               "&id_type=" + encodeURIComponent(idType) +
               "&rnc_cedula=" + encodeURIComponent(rnc);

    fetch(window.CUSTOMER_QUICK_CREATE_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-CSRFToken": csrf,
      },
      body: body,
    })
    .then(function(resp) {
      return resp.json().then(function(data) {
        return { status: resp.status, data: data };
      });
    })
    .then(function(result) {
      if (btn) { btn.disabled = false; }
      if (result.status === 200) {
        customerPickerShowSearch();
        _refreshCustomerPickerList(result.data.name || "");
        setTimeout(function () {
          customerPickerSelect(
            result.data.pk,
            result.data.name,
            result.data.rnc_cedula,
            result.data.default_ncf_type
          );
        }, 600);
      } else {
        var errors = result.data.errors || {};
        var fieldMap = { name: "qc-name", id_type: "qc-id-type", rnc_cedula: "qc-rnc" };
        Object.keys(fieldMap).forEach(function(field) {
          var inputEl = document.getElementById(fieldMap[field]);
          var errEl = document.getElementById(fieldMap[field] + "-error");
          if (errors[field] && errors[field].length) {
            if (inputEl) inputEl.classList.add("is-invalid");
            if (errEl) errEl.textContent = errors[field][0];
          }
        });
        var nonField = errors["__all__"] || errors["non_field_errors"] || [];
        var nfEl = document.getElementById("qc-non-field-errors");
        if (nfEl) nfEl.textContent = nonField.join(" ");
      }
    })
    .catch(function() {
      if (btn) { btn.disabled = false; }
    });
  }

  window.openCustomerPicker = openCustomerPicker;
  window.customerPickerSelect = customerPickerSelect;
  window.customerPickerHighlight = customerPickerHighlight;
  window.customerPickerShowCreate = customerPickerShowCreate;
  window.customerPickerShowSearch = customerPickerShowSearch;
  window.customerPickerQuickCreate = customerPickerQuickCreate;
})();
