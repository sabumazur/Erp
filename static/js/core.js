(function () {
  "use strict";

  var config = window.SabSysConfig || {};

  function getConfig(key, fallback) {
    config = window.SabSysConfig || {};
    return Object.prototype.hasOwnProperty.call(config, key) ? config[key] : fallback;
  }

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  function parseJsonScript(id, fallback) {
    var el = document.getElementById(id);
    if (!el) return fallback;
    try {
      return JSON.parse(el.textContent);
    } catch (err) {
      return fallback;
    }
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatMoney(n) {
    return parseFloat(n || 0).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }

  function setText(id, text) {
    var el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  function getCsrfToken() {
    var el = document.querySelector("[name=csrfmiddlewaretoken]");
    return el ? el.value : "";
  }

  // dt-kebab dropdowns: fixed strategy escapes overflow:hidden containers;
  // auto placement picks best direction when table has few rows.
  (function patchDtKebabDropdowns() {
    if (typeof bootstrap === "undefined" || !bootstrap.Dropdown) return;
    var orig = bootstrap.Dropdown.prototype._getPopperConfig;
    bootstrap.Dropdown.prototype._getPopperConfig = function () {
      var cfg = orig.call(this);
      if (this._element && this._element.closest(".dt-kebab")) {
        cfg.strategy = "fixed";
        cfg.placement = "auto";
      }
      return cfg;
    };
  })();

  // Auto-grow textareas marked with .autosize-ta
  ready(function () {
    function initAutosize(el) {
      function resize() { el.style.height = "auto"; el.style.height = el.scrollHeight + "px"; }
      el.addEventListener("input", resize);
      resize();
    }
    document.querySelectorAll(".autosize-ta").forEach(initAutosize);
    document.addEventListener("htmx:afterSettle", function () {
      document.querySelectorAll(".autosize-ta").forEach(initAutosize);
    });
  });

  // Declarative Bootstrap modal open/close driven by data attributes on HTMX triggers.
  //
  // Pattern A — open modal after HTMX load:
  //   data-modal-open="#id"            target modal selector
  //   data-modal-title-id="labelId"    (optional) element whose textContent to set
  //   data-modal-title="text"          (optional) text to write into that element
  //
  // Pattern B — hide modal on successful form POST:
  //   data-modal-close="#id"           target modal selector
  //   data-modal-close-event="name"    (optional) custom event to fire on document.body after hide
  document.addEventListener("htmx:afterRequest", function (evt) {
    var elt = evt.detail.elt;
    if (!elt || !evt.detail.successful) return;

    var openTarget = elt.dataset.modalOpen;
    if (openTarget) {
      var titleId = elt.dataset.modalTitleId;
      var titleText = elt.dataset.modalTitle;
      if (titleId && titleText) {
        var titleEl = document.getElementById(titleId);
        if (titleEl) titleEl.textContent = titleText;
      }
      bootstrap.Modal.getOrCreateInstance(document.querySelector(openTarget)).show();
    }

    var closeTarget = elt.dataset.modalClose;
    if (closeTarget) {
      var inst = bootstrap.Modal.getInstance(document.querySelector(closeTarget));
      if (inst) inst.hide();
      var closeEvt = elt.dataset.modalCloseEvent;
      if (closeEvt) htmx.trigger(document.body, closeEvt, {});
    }
  });

  window.SabSysCore = { getConfig: getConfig, ready: ready, parseJsonScript: parseJsonScript, escapeHtml: escapeHtml, formatMoney: formatMoney, setText: setText, getCsrfToken: getCsrfToken };
  window.getConfig = getConfig;
  window.parseJsonScript = parseJsonScript;
  window.escapeHtml = escapeHtml;
  window.formatMoney = formatMoney;
  window.setText = setText;
  window.getCsrfToken = getCsrfToken;

  // ── Loading-state buttons ─────────────────────────────────────────────────
  // Buttons with data-loading-text are disabled on form submit and their
  // label replaced with a spinner + the loading text.  The page redirect that
  // follows a successful POST resets the button naturally.
  function initLoadingButtons() {
    document.querySelectorAll('[data-loading-text]').forEach(function (btn) {
      if (btn._loadingBound) return;
      btn._loadingBound = true;
      var form = btn.closest('form') || document.getElementById(btn.getAttribute('form'));
      if (!form) return;
      form.addEventListener('submit', function () {
        btn.disabled = true;
        btn.innerHTML =
          '<span class="spinner-border spinner-border-sm me-1" ' +
          'role="status" aria-hidden="true"></span>' +
          btn.getAttribute('data-loading-text');
      });
    });
  }
  window.initLoadingButtons = initLoadingButtons;
})();
