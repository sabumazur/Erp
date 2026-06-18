(function () {
  "use strict";

  /*
   * createPicker(cfg) — shared factory for customer, supplier and item pickers.
   *
   * cfg = {
   *   modalId, searchInputId, tbodyId,
   *   searchPanelId, createPanelId, submitBtnId, nonFieldErrorId,
   *   createFields: [{ id, bodyKey, defaultValue }],
   *   errorFieldMap: { serverField: inputId },
   *   quickCreateUrl: function() → string,
   *   apply: function(pk, data)  — called when a row is selected or quick-created;
   *                                 updates form fields, does NOT close the modal.
   * }
   *
   * Returns { open, select, highlight, refresh, showSearch, showCreate, quickCreate }.
   */
  function createPicker(cfg) {

    function highlight(tr) {
      var tbody = document.getElementById(cfg.tbodyId);
      if (tbody) {
        tbody.querySelectorAll("tr").forEach(function (r) { r.removeAttribute("aria-selected"); });
      }
      tr.setAttribute("aria-selected", "true");
    }

    function refresh(q) {
      var searchInput = document.getElementById(cfg.searchInputId);
      if (!searchInput || !window.htmx) return;
      var url = searchInput.getAttribute("hx-get");
      if (!url) return;
      if (q) url += (url.indexOf("?") === -1 ? "?" : "&") + "q=" + encodeURIComponent(q);
      htmx.ajax("GET", url, { target: "#" + cfg.tbodyId, swap: "innerHTML" });
    }

    function showSearch() {
      var search = document.getElementById(cfg.searchPanelId);
      var create = document.getElementById(cfg.createPanelId);
      if (search) search.classList.remove("d-none");
      if (create) create.classList.add("d-none");
      cfg.createFields.forEach(function (f) {
        var el = document.getElementById(f.id);
        if (el) el.classList.remove("is-invalid");
        var err = document.getElementById(f.id + "-error");
        if (err) err.textContent = "";
      });
      var nfEl = document.getElementById(cfg.nonFieldErrorId);
      if (nfEl) nfEl.textContent = "";
    }

    function showCreate() {
      var search = document.getElementById(cfg.searchPanelId);
      var create = document.getElementById(cfg.createPanelId);
      if (search) search.classList.add("d-none");
      if (create) create.classList.remove("d-none");
      var firstField = null;
      cfg.createFields.forEach(function (f) {
        var el = document.getElementById(f.id);
        if (el) {
          el.value = f.defaultValue !== undefined ? f.defaultValue : "";
          el.classList.remove("is-invalid");
          if (!firstField) firstField = el;
        }
        var err = document.getElementById(f.id + "-error");
        if (err) err.textContent = "";
      });
      var nfEl = document.getElementById(cfg.nonFieldErrorId);
      if (nfEl) nfEl.textContent = "";
      if (firstField) firstField.focus();
    }

    function select(pk, data) {
      cfg.apply(pk, data);
      var modal = document.getElementById(cfg.modalId);
      if (modal && window.bootstrap) bootstrap.Modal.getOrCreateInstance(modal).hide();
    }

    function quickCreate() {
      var csrf = window.getCsrfToken();
      var btn = document.getElementById(cfg.submitBtnId);
      if (btn) btn.disabled = true;

      var bodyParts = cfg.createFields.map(function (f) {
        var val = (document.getElementById(f.id) || {}).value;
        if (val === undefined) val = f.defaultValue !== undefined ? f.defaultValue : "";
        return encodeURIComponent(f.bodyKey) + "=" + encodeURIComponent(val);
      });

      fetch(cfg.quickCreateUrl(), {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "X-CSRFToken": csrf,
        },
        body: bodyParts.join("&"),
      })
      .then(function (resp) {
        return resp.json().then(function (data) { return { status: resp.status, data: data }; });
      })
      .then(function (result) {
        if (btn) btn.disabled = false;
        if (result.status === 200) {
          showSearch();
          var data = result.data;
          var tbody = document.getElementById(cfg.tbodyId);
          if (tbody) {
            var handled = false;
            function onSwap() {
              if (handled) return;
              handled = true;
              tbody.removeEventListener("htmx:afterSwap", onSwap);
              select(data.pk, data);
            }
            tbody.addEventListener("htmx:afterSwap", onSwap);
            // Fallback: select anyway if the swap never fires (e.g. network error)
            setTimeout(function () {
              if (!handled) {
                handled = true;
                tbody.removeEventListener("htmx:afterSwap", onSwap);
                select(data.pk, data);
              }
            }, 3000);
          } else {
            select(data.pk, data);
          }
          refresh(data.name || "");
        } else {
          var errors = result.data.errors || {};
          Object.keys(cfg.errorFieldMap).forEach(function (field) {
            var inputId = cfg.errorFieldMap[field];
            var inputEl = document.getElementById(inputId);
            var errEl = document.getElementById(inputId + "-error");
            if (errors[field] && errors[field].length) {
              if (inputEl) inputEl.classList.add("is-invalid");
              if (errEl) errEl.textContent = errors[field][0];
            }
          });
          var nonField = errors["__all__"] || errors["non_field_errors"] || [];
          var nfEl = document.getElementById(cfg.nonFieldErrorId);
          if (nfEl) nfEl.textContent = nonField.join(" ");
        }
      })
      .catch(function () {
        if (btn) btn.disabled = false;
      });
    }

    function open(currentPk) {
      if (!window.bootstrap) return;
      var modal = document.getElementById(cfg.modalId);
      if (!modal) return;
      showSearch();
      var searchInput = document.getElementById(cfg.searchInputId);
      bootstrap.Modal.getOrCreateInstance(modal).show();
      modal.addEventListener("shown.bs.modal", function handler() {
        if (searchInput) {
          searchInput.value = "";
          searchInput.focus();
          var tbody = document.getElementById(cfg.tbodyId);
          if (tbody && currentPk) {
            function onSwap() {
              tbody.removeEventListener("htmx:afterSwap", onSwap);
              var match = tbody.querySelector('tr[data-pk="' + currentPk + '"]');
              if (match) {
                highlight(match);
                match.scrollIntoView({ block: "nearest", behavior: "smooth" });
              }
            }
            tbody.addEventListener("htmx:afterSwap", onSwap);
          }
          refresh("");
        }
        modal.removeEventListener("shown.bs.modal", handler);
      });
    }

    return { open: open, select: select, highlight: highlight, refresh: refresh, showSearch: showSearch, showCreate: showCreate, quickCreate: quickCreate };
  }

  window.createPicker = createPicker;
})();
