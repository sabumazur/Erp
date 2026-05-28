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

  window.SabSysCore = { getConfig: getConfig, ready: ready, parseJsonScript: parseJsonScript, escapeHtml: escapeHtml, formatMoney: formatMoney, setText: setText };
  window.getConfig = getConfig;
  window.parseJsonScript = parseJsonScript;
  window.escapeHtml = escapeHtml;
  window.formatMoney = formatMoney;
  window.setText = setText;
})();
