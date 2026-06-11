/*
   picker-core.js — shared factory for the customer / supplier / item pickers.

   Load order: BEFORE item-picker.js / customer-picker.js / supplier-picker.js,
   which are thin configs over window.createPicker(cfg).

   cfg surface:
     modalId / searchId / tbodyId        — DOM ids of the modal, search input
                                           and results <tbody>
     searchPanelId / createPanelId       — the two switchable panels
     submitBtnId / nonFieldErrorsId      — quick-create submit + error sink
     fields: [{param, id, reset, fallback, focus}]
                                           param   → POST field name
                                           id      → input element id
                                                     (error el is always `${id}-error`)
                                           reset   → value (or fn(el)) applied by showCreate
                                           fallback→ value used when the input is empty
                                           focus   → focus this input in showCreate
     quickCreateUrl()                    — resolved at call time from window.*
     refreshOnShown                      — true: clear/focus/refresh inside
                                           shown.bs.modal (customer/supplier);
                                           false: refresh immediately (item)
     getCurrentPk(...openArgs)           — pk to re-highlight after first swap
     onOpen(...openArgs)                 — per-picker open-time state (item)
     onHighlight(tr)                     — extra highlight behavior (item)
     onQuickCreated(data, api)           — runs 600ms after the post-create
                                           list refresh (select / fill row)

   Returned api: open, refresh, highlight, showCreate, showSearch, quickCreate.
*/
(function () {
  "use strict";

  function createPicker(cfg) {
    function byId(id) { return document.getElementById(id); }

    function errorIds() {
      return cfg.fields.map(function (f) { return f.id + "-error"; })
        .concat([cfg.nonFieldErrorsId]);
    }

    function clearErrors() {
      cfg.fields.forEach(function (f) {
        var el = byId(f.id);
        if (el) el.classList.remove("is-invalid");
      });
      errorIds().forEach(function (id) {
        var el = byId(id);
        if (el) el.textContent = "";
      });
    }

    function showSearch() {
      var search = byId(cfg.searchPanelId);
      var create = byId(cfg.createPanelId);
      if (search) search.classList.remove("d-none");
      if (create) create.classList.add("d-none");
      clearErrors();
    }

    function showCreate() {
      var search = byId(cfg.searchPanelId);
      var create = byId(cfg.createPanelId);
      if (search) search.classList.add("d-none");
      if (create) create.classList.remove("d-none");
      var focusEl = null;
      cfg.fields.forEach(function (f) {
        var el = byId(f.id);
        if (!el) return;
        el.value = typeof f.reset === "function" ? f.reset(el) : (f.reset || "");
        el.classList.remove("is-invalid");
        if (f.focus) focusEl = el;
      });
      errorIds().forEach(function (id) {
        var el = byId(id);
        if (el) el.textContent = "";
      });
      if (focusEl) focusEl.focus();
    }

    function refresh(q) {
      var searchInput = byId(cfg.searchId);
      if (!searchInput || !window.htmx) return;
      var url = searchInput.getAttribute("hx-get");
      if (!url) return;
      if (q) url += (url.indexOf("?") === -1 ? "?" : "&") + "q=" + encodeURIComponent(q);
      htmx.ajax("GET", url, { target: "#" + cfg.tbodyId, swap: "innerHTML" });
    }

    function highlight(tr) {
      var tbody = byId(cfg.tbodyId);
      if (tbody) {
        tbody.querySelectorAll("tr").forEach(function (r) { r.removeAttribute("aria-selected"); });
      }
      tr.setAttribute("aria-selected", "true");
      if (cfg.onHighlight) cfg.onHighlight(tr);
    }

    function armHighlight(currentPk) {
      var tbody = byId(cfg.tbodyId);
      if (!tbody || !currentPk) return;
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

    function open() {
      if (!window.bootstrap) return;
      var modal = byId(cfg.modalId);
      if (!modal) return;
      showSearch();
      if (cfg.onOpen) cfg.onOpen.apply(null, arguments);
      var searchInput = byId(cfg.searchId);
      var currentPk = cfg.getCurrentPk ? (cfg.getCurrentPk.apply(null, arguments) || "") : "";

      if (cfg.refreshOnShown) {
        bootstrap.Modal.getOrCreateInstance(modal).show();
        modal.addEventListener("shown.bs.modal", function handler() {
          if (searchInput) {
            searchInput.value = "";
            searchInput.focus();
            armHighlight(currentPk);
            refresh("");
          }
          modal.removeEventListener("shown.bs.modal", handler);
        });
      } else {
        if (searchInput) searchInput.value = "";
        armHighlight(currentPk);
        bootstrap.Modal.getOrCreateInstance(modal).show();
        refresh("");
      }
    }

    function quickCreate() {
      var csrf = (document.querySelector("[name=csrfmiddlewaretoken]") || {}).value || "";
      var btn = byId(cfg.submitBtnId);
      if (btn) btn.disabled = true;

      var body = cfg.fields.map(function (f) {
        var el = byId(f.id);
        var value = (el && el.value) || f.fallback || "";
        return f.param + "=" + encodeURIComponent(value);
      }).join("&");

      fetch(cfg.quickCreateUrl(), {
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
          showSearch();
          refresh(result.data.name || "");
          // Give the HTMX list swap time to land before selecting the new row.
          setTimeout(function () {
            if (cfg.onQuickCreated) cfg.onQuickCreated(result.data, api);
          }, 600);
        } else {
          var errors = result.data.errors || {};
          cfg.fields.forEach(function (f) {
            var inputEl = byId(f.id);
            var errEl = byId(f.id + "-error");
            if (errors[f.param] && errors[f.param].length) {
              if (inputEl) inputEl.classList.add("is-invalid");
              if (errEl) errEl.textContent = errors[f.param][0];
            }
          });
          var nonField = errors["__all__"] || errors["non_field_errors"] || [];
          var nfEl = byId(cfg.nonFieldErrorsId);
          if (nfEl) nfEl.textContent = nonField.join(" ");
        }
      })
      .catch(function () {
        if (btn) btn.disabled = false;
      });
    }

    var api = {
      open: open,
      refresh: refresh,
      highlight: highlight,
      showCreate: showCreate,
      showSearch: showSearch,
      quickCreate: quickCreate,
    };
    return api;
  }

  window.createPicker = createPicker;
})();
