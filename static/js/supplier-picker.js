(function () {
  "use strict";

  function openSupplierPicker() {
    if (!window.bootstrap) return;
    var modal = document.getElementById("supplierPickerModal");
    if (!modal) return;
    supplierPickerShowSearch();
    var searchInput = document.getElementById("supplier-picker-search");
    var supplierSel = document.getElementById("id_supplier");
    var currentPk = supplierSel ? supplierSel.value : "";
    bootstrap.Modal.getOrCreateInstance(modal).show();
    modal.addEventListener("shown.bs.modal", function handler() {
      if (searchInput) {
        searchInput.value = "";
        searchInput.focus();
        var tbody = document.getElementById("supplier-picker-tbody");
        if (tbody && currentPk) {
          function onSupplierSwap() {
            tbody.removeEventListener("htmx:afterSwap", onSupplierSwap);
            var match = tbody.querySelector('tr[data-pk="' + currentPk + '"]');
            if (match) {
              supplierPickerHighlight(match);
              match.scrollIntoView({ block: "nearest", behavior: "smooth" });
            }
          }
          tbody.addEventListener("htmx:afterSwap", onSupplierSwap);
        }
        _refreshSupplierPickerList("");
      }
      modal.removeEventListener("shown.bs.modal", handler);
    });
  }

  function supplierPickerHighlight(tr) {
    var tbody = document.getElementById("supplier-picker-tbody");
    if (tbody) {
      tbody.querySelectorAll("tr").forEach(function (r) { r.removeAttribute("aria-selected"); });
    }
    tr.setAttribute("aria-selected", "true");
  }

  function _refreshSupplierPickerList(q) {
    var searchInput = document.getElementById("supplier-picker-search");
    if (!searchInput || !window.htmx) return;
    var url = searchInput.getAttribute("hx-get");
    if (!url) return;
    if (q) url += (url.indexOf("?") === -1 ? "?" : "&") + "q=" + encodeURIComponent(q);
    htmx.ajax("GET", url, { target: "#supplier-picker-tbody", swap: "innerHTML" });
  }

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

  function supplierPickerShowCreate() {
    var search = document.getElementById("supplier-picker-search-panel");
    var create = document.getElementById("supplier-picker-create-panel");
    if (search) search.classList.add("d-none");
    if (create) create.classList.remove("d-none");
    var nameEl = document.getElementById("qs-name");
    var idTypeEl = document.getElementById("qs-id-type");
    var rncCedulaEl = document.getElementById("qs-rnc-cedula");
    if (nameEl) { nameEl.value = ""; nameEl.classList.remove("is-invalid"); }
    if (idTypeEl) { idTypeEl.value = "RNC"; idTypeEl.classList.remove("is-invalid"); }
    if (rncCedulaEl) { rncCedulaEl.value = ""; rncCedulaEl.classList.remove("is-invalid"); }
    ["qs-name-error", "qs-id-type-error", "qs-rnc-cedula-error", "qs-non-field-errors"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.textContent = "";
    });
    if (nameEl) nameEl.focus();
  }

  function supplierPickerShowSearch() {
    var search = document.getElementById("supplier-picker-search-panel");
    var create = document.getElementById("supplier-picker-create-panel");
    if (search) search.classList.remove("d-none");
    if (create) create.classList.add("d-none");
    ["qs-name", "qs-id-type", "qs-rnc-cedula"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.classList.remove("is-invalid");
    });
    ["qs-name-error", "qs-id-type-error", "qs-rnc-cedula-error", "qs-non-field-errors"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.textContent = "";
    });
  }

  function supplierPickerQuickCreate() {
    var name = (document.getElementById("qs-name") || {}).value || "";
    var idType = (document.getElementById("qs-id-type") || {}).value || "RNC";
    var rncCedula = (document.getElementById("qs-rnc-cedula") || {}).value || "";
    var csrf = (document.querySelector("[name=csrfmiddlewaretoken]") || {}).value || "";
    var btn = document.getElementById("qs-submit-btn");
    if (btn) btn.disabled = true;

    var body = "name=" + encodeURIComponent(name) +
               "&id_type=" + encodeURIComponent(idType) +
               "&rnc_cedula=" + encodeURIComponent(rncCedula);

    fetch(window.SUPPLIER_QUICK_CREATE_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-CSRFToken": csrf,
      },
      body: body,
    })
    .then(function (resp) {
      return resp.json().then(function (data) {
        return { status: resp.status, data: data };
      });
    })
    .then(function (result) {
      if (btn) btn.disabled = false;
      if (result.status === 200) {
        supplierPickerShowSearch();
        _refreshSupplierPickerList(result.data.name || "");
        setTimeout(function () {
          supplierPickerSelect(result.data.pk, result.data.name, result.data.rnc_cedula);
        }, 600);
      } else {
        var errors = result.data.errors || {};
        var fieldMap = { name: "qs-name", id_type: "qs-id-type", rnc_cedula: "qs-rnc-cedula" };
        Object.keys(fieldMap).forEach(function (field) {
          var inputEl = document.getElementById(fieldMap[field]);
          var errEl = document.getElementById(fieldMap[field] + "-error");
          if (errors[field] && errors[field].length) {
            if (inputEl) inputEl.classList.add("is-invalid");
            if (errEl) errEl.textContent = errors[field][0];
          }
        });
        var nonField = errors["__all__"] || errors["non_field_errors"] || [];
        var nfEl = document.getElementById("qs-non-field-errors");
        if (nfEl) nfEl.textContent = nonField.join(" ");
      }
    })
    .catch(function () {
      if (btn) btn.disabled = false;
    });
  }

  window.openSupplierPicker = openSupplierPicker;
  window.supplierPickerSelect = supplierPickerSelect;
  window.supplierPickerHighlight = supplierPickerHighlight;
  window.supplierPickerShowCreate = supplierPickerShowCreate;
  window.supplierPickerShowSearch = supplierPickerShowSearch;
  window.supplierPickerQuickCreate = supplierPickerQuickCreate;
})();
