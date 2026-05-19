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

  function initToasts() {
    if (!window.bootstrap) return;

    document.querySelectorAll(".toast-container .toast").forEach(function (el) {
      bootstrap.Toast.getOrCreateInstance(el).show();
    });

    document.body.addEventListener("showToast", function (evt) {
      var detail = evt.detail || {};
      var msg = detail.message || "";
      var type = detail.type || "success";
      var icons = {
        success: "bi-check-circle-fill",
        danger: "bi-exclamation-circle-fill",
        warning: "bi-exclamation-triangle-fill",
        info: "bi-info-circle-fill",
      };
      var icon = icons[type] || icons.info;
      var container = document.getElementById("htmx-toast-container");
      if (!container) return;

      var el = document.createElement("div");
      el.className = "toast align-items-center border-0 text-bg-" + type;
      el.setAttribute("role", "alert");
      el.setAttribute("data-bs-autohide", "true");
      el.setAttribute("data-bs-delay", "4500");
      el.innerHTML =
        '<div class="d-flex">' +
          '<div class="toast-body d-flex align-items-center gap-2">' +
            '<i class="bi ' + icon + '"></i>' + escapeHtml(msg) +
          '</div>' +
          '<button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>' +
        '</div>';
      container.appendChild(el);
      bootstrap.Toast.getOrCreateInstance(el).show();
      el.addEventListener("hidden.bs.toast", function () { el.remove(); });
    });

    document.body.addEventListener("showSwal", function (evt) {
      if (!window.Swal) return;
      var detail = evt.detail || {};
      Swal.fire({
        icon: detail.icon || "error",
        title: detail.title || "",
        text: detail.text || "",
        confirmButtonText: detail.confirmButtonText || "OK",
      });
    });
  }

  function initPasswordToggles() {
    document.querySelectorAll('input[type="password"]').forEach(function (input) {
      if (input.dataset.passwordToggleReady === "1") return;
      input.dataset.passwordToggleReady = "1";

      var wrapper = document.createElement("div");
      wrapper.style.position = "relative";
      input.parentElement.insertBefore(wrapper, input);
      wrapper.appendChild(input);
      input.style.paddingRight = "2.5rem";

      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn btn-link position-absolute top-50 end-0 translate-middle-y pe-2 text-muted";
      btn.style.zIndex = "10";
      btn.innerHTML = '<i class="bi bi-eye"></i>';
      btn.setAttribute("tabindex", "-1");
      btn.addEventListener("click", function () {
        var show = input.type === "password";
        input.type = show ? "text" : "password";
        btn.querySelector("i").className = show ? "bi bi-eye-slash" : "bi bi-eye";
      });
      wrapper.appendChild(btn);
    });
  }

  function swalConfirm(form, message, opts) {
    if (!window.Swal) {
      form.submit();
      return;
    }
    opts = opts || {};
    Swal.fire({
      text: message,
      icon: opts.icon || "question",
      showCancelButton: true,
      confirmButtonText: opts.ok || getConfig("swalConfirmOk", "Sí, continuar"),
      cancelButtonText: opts.cancel || getConfig("swalCancelText", "Cancelar"),
      confirmButtonColor: opts.color || "#0d6efd",
      cancelButtonColor: "#6c757d",
      reverseButtons: true,
    }).then(function (r) {
      if (r.isConfirmed) form.submit();
    });
  }

  function toggleSidebar() {
    var isDesktop = window.innerWidth >= 992;
    if (isDesktop) {
      document.body.classList.toggle("sidebar-collapsed");
      localStorage.setItem(
        "sidebarCollapsed",
        document.body.classList.contains("sidebar-collapsed") ? "1" : "0"
      );
    } else {
      document.body.classList.toggle("sidebar-open");
    }
  }

  function initSidebarState() {
    if (window.innerWidth >= 992 && localStorage.getItem("sidebarCollapsed") === "1") {
      document.body.classList.add("sidebar-collapsed");
    }
    window.addEventListener("resize", function () {
      if (window.innerWidth >= 992) {
        document.body.classList.remove("sidebar-open");
      }
    });
  }

  function passwordChecker() {
    return {
      password: "",
      confirm: "",
      get rules() {
        return {
          length: this.password.length >= 8,
          hasLetter: /[a-zA-Z]/.test(this.password),
          hasNumber: /\d/.test(this.password),
          hasSymbol: /[^a-zA-Z0-9]/.test(this.password),
          matches: this.password === this.confirm && this.confirm.length > 0,
        };
      },
      get strengthPct() {
        var rules = this.rules;
        var met = [rules.length, rules.hasLetter, rules.hasNumber, rules.hasSymbol].filter(Boolean).length;
        return Math.round((met / 4) * 100);
      },
      get strengthColor() {
        if (this.strengthPct <= 25) return "bg-danger";
        if (this.strengthPct <= 50) return "bg-warning";
        if (this.strengthPct <= 75) return "bg-info";
        return "bg-success";
      },
      init: function () {
        var self = this;
        var p1 = document.getElementById("id_password1") || document.getElementById("id_oldpassword");
        var p2 = document.getElementById("id_password2");
        if (p1) {
          p1.addEventListener("input", function (e) { self.password = e.target.value; });
          p1.addEventListener("change", function (e) { self.password = e.target.value; });
        }
        if (p2) {
          p2.addEventListener("input", function (e) { self.confirm = e.target.value; });
          p2.addEventListener("change", function (e) { self.confirm = e.target.value; });
        }
      },
    };
  }

  function avatarHandler(currentUrl, placeholderUrl) {
    return {
      previewSrc: currentUrl || placeholderUrl,
      hasAvatar: !!currentUrl,
      change: function (e) {
        var file = e.target.files[0];
        if (!file) return;
        this.previewSrc = URL.createObjectURL(file);
        this.hasAvatar = true;
        this.$refs.clearInput.checked = false;
      },
      clear: function () {
        this.previewSrc = placeholderUrl;
        this.hasAvatar = false;
        this.$refs.fileInput.value = "";
        this.$refs.clearInput.checked = true;
      },
    };
  }

  function itemForm(initialType) {
    return {
      itemType: initialType,
      get autoCode() {
        return this.itemType === "SALE" || this.itemType === "BOTH";
      },
      get codeHint() {
        return this.autoCode
          ? getConfig("itemAutoCodeHint", "Se generara automaticamente al guardar (ej. ART-0001).")
          : getConfig("itemManualCodeHint", "Codigo interno / SKU opcional.");
      },
      get codePlaceholder() {
        return this.autoCode
          ? getConfig("itemAutoCodePlaceholder", "Automatico (ART-XXXX)")
          : getConfig("itemManualCodePlaceholder", "Codigo manual (opcional)");
      },
      init: function () {
        var sel = this.$el.querySelector('[name="item_type"]');
        if (sel) this.itemType = sel.value;
      },
    };
  }

  function invoiceForm() {
    return {};
  }

  function dtTable(tableId, allCols, defaultVisible) {
    return {
      tableId: tableId,
      allCols: allCols,
      visible: [],
      init: function () {
        var self = this;
        var saved = localStorage.getItem("dt-visible-" + tableId);
        this.visible = saved ? JSON.parse(saved) : defaultVisible.slice();
        this.$nextTick(function () { self.applyColVisibility(); });

        document.addEventListener("htmx:afterSwap", function (e) {
          if (e.detail.target && e.detail.target.id === "dt-results") {
            self.applyColVisibility();
          }
        });

      },
      toggleCol: function (key) {
        if (this.visible.includes(key)) {
          this.visible = this.visible.filter(function (k) { return k !== key; });
        } else {
          this.visible.push(key);
        }
        localStorage.setItem("dt-visible-" + this.tableId, JSON.stringify(this.visible));
        this.applyColVisibility();
      },
      applyColVisibility: function () {
        this.allCols.forEach(function (col) {
          var show = this.visible.includes(col);
          document.querySelectorAll('[data-col="' + col + '"]').forEach(function (el) {
            el.style.display = show ? "" : "none";
          });
        }, this);
      },
    };
  }

  function dtSort(key, currentSort) {
    var form = document.getElementById("dt-form");
    var sortEl = document.getElementById("dt-sort-input");
    var pageEl = document.getElementById("dt-page-input");
    if (!form || !sortEl || !window.htmx) return;
    if (currentSort === key) sortEl.value = "-" + key;
    else if (currentSort === "-" + key) sortEl.value = key;
    else sortEl.value = key;
    if (pageEl) pageEl.value = "1";
    htmx.trigger(form, "submit");
  }

  function dtPage(n) {
    var form = document.getElementById("dt-form");
    var pageEl = document.getElementById("dt-page-input");
    if (!form || !pageEl || !window.htmx) return;
    form._dtKeepPage = true;
    pageEl.value = n;
    htmx.trigger(form, "submit");
  }

  function initDatatableFilters() {
    document.addEventListener("htmx:configRequest", function (e) {
      if (!e.detail.elt || e.detail.elt.id !== "dt-form") return;
      var form = e.detail.elt;
      if (!form._dtKeepPage) {
        e.detail.parameters["page"] = "1";
      }
      form._dtKeepPage = false;
    });

    document.addEventListener("htmx:afterRequest", function (e) {
      if (!window.bootstrap || !e.detail.elt || e.detail.elt.id !== "dt-form") return;
      var canvas = document.getElementById("dt-filter-offcanvas");
      if (!canvas) return;
      var oc = bootstrap.Offcanvas.getInstance(canvas);
      if (oc) oc.hide();
    });
  }

  function itemRow() {
    return {
      qty: 1,
      price: 0,
      rate: "RATE_18",
      rateMap: { EXEMPT: 0, RATE_0: 0, RATE_16: 0.16, RATE_18: 0.18 },
      init: function () {
        var row = this.$el;
        var qEl = row.querySelector('[name$="-quantity"]');
        var pEl = row.querySelector('[name$="-unit_price"]');
        var rEl = row.querySelector('[name$="-itbis_rate"]');
        if (qEl) this.qty = parseInt(qEl.value, 10) || 1;
        if (pEl) this.price = parseFloat(pEl.value) || 0;
        if (rEl) this.rate = rEl.value || "RATE_18";
        this.$nextTick(function () { recalcGrandTotal(); });
      },
      subtotal: function () { return this.qty * this.price; },
      itbisAmt: function () { return this.subtotal() * (this.rateMap[this.rate] || 0); },
      rowTotal: function () { return this.subtotal() + this.itbisAmt(); },
      fmt: function (n) { return n.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ","); },
      fmtSubtotal: function () { return this.fmt(this.subtotal()); },
      fmtItbis: function () { return this.fmt(this.itbisAmt()); },
      fmtTotal: function () { return this.fmt(this.rowTotal()); },
      recalc: function () { recalcGrandTotal(); },
    };
  }

  function deleteRow(btn) {
    var row = btn.closest("tr");
    var next = row && row.nextElementSibling;
    var descRow = next && next.classList.contains("item-row-desc") ? next : null;
    var delEl = row ? row.querySelector('[name$="-DELETE"]') : null;
    if (delEl) {
      delEl.checked = true;
      row.style.display = "none";
      if (descRow) descRow.style.display = "none";
    } else if (row) {
      if (descRow) descRow.remove();
      row.remove();
    }
    recalcGrandTotal();
  }

  function openItemPicker(rowEl) {
    if (!window.bootstrap) return;
    window.activeItemRow  = rowEl;
    window.activePickerTr = null;
    itemPickerShowSearch();
    var selBtn = document.getElementById("picker-select-btn");
    if (selBtn) selBtn.disabled = true;
    var searchEl = document.getElementById("picker-search");
    if (searchEl) searchEl.value = "";

    var itemEl    = rowEl ? rowEl.querySelector('[name$="-item"]') : null;
    var currentPk = itemEl ? itemEl.value : "";
    var tbody     = document.getElementById("picker-tbody");
    if (tbody && currentPk) {
      function onItemSwap() {
        tbody.removeEventListener("htmx:afterSwap", onItemSwap);
        var match = tbody.querySelector('tr[data-pk="' + currentPk + '"]');
        if (match) {
          itemPickerHighlight(match);
          match.scrollIntoView({ block: "nearest", behavior: "smooth" });
        }
      }
      tbody.addEventListener("htmx:afterSwap", onItemSwap);
    }

    var modal = document.getElementById("itemPickerModal");
    if (modal) bootstrap.Modal.getOrCreateInstance(modal).show();
    _refreshItemPickerList("");
  }

  function _refreshItemPickerList(q) {
    var searchEl = document.getElementById("picker-search");
    if (!searchEl || !window.htmx) return;
    var url = searchEl.getAttribute("hx-get");
    if (!url) return;
    if (q) url += (url.indexOf("?") === -1 ? "?" : "&") + "q=" + encodeURIComponent(q);
    htmx.ajax("GET", url, { target: "#picker-tbody", swap: "innerHTML" });
  }

  function itemPickerShowCreate() {
    var search = document.getElementById("item-picker-search-panel");
    var create = document.getElementById("item-picker-create-panel");
    if (search) search.classList.add("d-none");
    if (create) create.classList.remove("d-none");
    var nameEl  = document.getElementById("iqc-name");
    var unitEl  = document.getElementById("iqc-unit");
    var priceEl = document.getElementById("iqc-unit-price");
    var rateEl  = document.getElementById("iqc-itbis-rate");
    if (nameEl)  { nameEl.value  = ""; nameEl.classList.remove("is-invalid"); }
    if (unitEl)  { unitEl.value  = "UNIT"; unitEl.classList.remove("is-invalid"); }
    if (priceEl) { priceEl.value = ""; priceEl.classList.remove("is-invalid"); }
    if (rateEl)  { rateEl.value  = "RATE_18"; rateEl.classList.remove("is-invalid"); }
    ["iqc-name-error", "iqc-unit-error", "iqc-unit-price-error", "iqc-itbis-rate-error", "iqc-non-field-errors"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.textContent = "";
    });
    if (nameEl) nameEl.focus();
  }

  function itemPickerShowSearch() {
    var search = document.getElementById("item-picker-search-panel");
    var create = document.getElementById("item-picker-create-panel");
    if (search) search.classList.remove("d-none");
    if (create) create.classList.add("d-none");
    ["iqc-name", "iqc-unit", "iqc-unit-price", "iqc-itbis-rate"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.classList.remove("is-invalid");
    });
    ["iqc-name-error", "iqc-unit-error", "iqc-unit-price-error", "iqc-itbis-rate-error", "iqc-non-field-errors"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.textContent = "";
    });
  }

  function itemPickerQuickCreate() {
    var name      = (document.getElementById("iqc-name")       || {}).value || "";
    var unit      = (document.getElementById("iqc-unit")       || {}).value || "UNIT";
    var unitPrice = (document.getElementById("iqc-unit-price") || {}).value || "";
    var itbisRate = (document.getElementById("iqc-itbis-rate") || {}).value || "RATE_18";
    var csrf      = (document.querySelector("[name=csrfmiddlewaretoken]") || {}).value || "";
    var btn       = document.getElementById("iqc-submit-btn");
    if (btn) btn.disabled = true;

    fetch(window.ITEM_QUICK_CREATE_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-CSRFToken": csrf,
      },
      body: "name=" + encodeURIComponent(name) +
            "&unit=" + encodeURIComponent(unit) +
            "&unit_price=" + encodeURIComponent(unitPrice) +
            "&itbis_rate=" + encodeURIComponent(itbisRate),
    })
    .then(function (resp) {
      return resp.json().then(function (data) { return { status: resp.status, data: data }; });
    })
    .then(function (result) {
      if (btn) btn.disabled = false;
      if (result.status === 200) {
        var d = result.data;
        itemPickerShowSearch();
        _refreshItemPickerList(d.name || "");
        setTimeout(function () {
          if (window.activeItemRow) {
            var formRow = window.activeItemRow;
            var next    = formRow.nextElementSibling;
            var descEl  = formRow.querySelector('[name$="-description"]') ||
                          (next && next.querySelector('[name$="-description"]'));
            var priceEl = formRow.querySelector('[name$="-unit_price"]');
            var qtyEl   = formRow.querySelector('[name$="-quantity"]');
            var rateEl  = formRow.querySelector('[name$="-itbis_rate"]');
            var itemEl  = formRow.querySelector('[name$="-item"]');
            if (descEl)  descEl.value  = d.name;
            if (itemEl)  itemEl.value  = d.pk;
            if (priceEl) priceEl.value = d.unit_price;
            if (qtyEl)   qtyEl.value   = "1";
            if (rateEl)  rateEl.value  = d.itbis_rate;
            if (typeof Alpine !== "undefined") {
              try {
                Alpine.evaluate(formRow, "price = " + (parseFloat(d.unit_price) || 0) +
                  ", qty = 1, rate = '" + (d.itbis_rate || "RATE_18") + "'");
              } catch (err) {}
            }
            recalcGrandTotal();
          }
          var modal = document.getElementById("itemPickerModal");
          if (modal) bootstrap.Modal.getOrCreateInstance(modal).hide();
        }, 600);
      } else {
        var errors   = result.data.errors || {};
        var fieldMap = { name: "iqc-name", unit: "iqc-unit", unit_price: "iqc-unit-price", itbis_rate: "iqc-itbis-rate" };
        Object.keys(fieldMap).forEach(function (field) {
          var inputEl = document.getElementById(fieldMap[field]);
          var errEl   = document.getElementById(fieldMap[field] + "-error");
          if (errors[field] && errors[field].length) {
            if (inputEl) inputEl.classList.add("is-invalid");
            if (errEl)   errEl.textContent = errors[field][0];
          }
        });
        var nonField = errors["__all__"] || errors["non_field_errors"] || [];
        var nfEl = document.getElementById("iqc-non-field-errors");
        if (nfEl) nfEl.textContent = nonField.join(" ");
      }
    })
    .catch(function () {
      if (btn) btn.disabled = false;
    });
  }

  function itemPickerHighlight(tr) {
    document.querySelectorAll("#picker-tbody .item-picker-row").forEach(function (r) {
      r.removeAttribute("aria-selected");
    });
    tr.setAttribute("aria-selected", "true");
    window.activePickerTr = tr;
    var selBtn = document.getElementById("picker-select-btn");
    if (selBtn) selBtn.disabled = false;
  }

  function itemPickerConfirm() {
    var tr = window.activePickerTr;
    if (!tr || !window.activeItemRow) return;
    pickItemRow(window.activeItemRow, tr);
    var modal = document.getElementById("itemPickerModal");
    if (modal) bootstrap.Modal.getOrCreateInstance(modal).hide();
    window.activePickerTr = null;
  }

  function pickItemRow(formRow, catalogTr) {
    var pk    = catalogTr.dataset.pk;
    var name  = catalogTr.dataset.name;
    var price = catalogTr.dataset.unitPrice;
    var rate  = catalogTr.dataset.itbisRate;

    var next    = formRow.nextElementSibling;
    var descEl  = formRow.querySelector('[name$="-description"]') ||
                  (next && next.querySelector('[name$="-description"]'));
    var priceEl = formRow.querySelector('[name$="-unit_price"]');
    var qtyEl   = formRow.querySelector('[name$="-quantity"]');
    var rateEl  = formRow.querySelector('[name$="-itbis_rate"]');
    var itemEl  = formRow.querySelector('[name$="-item"]');

    if (descEl)  descEl.value  = name;
    if (itemEl)  itemEl.value  = pk;
    if (priceEl) priceEl.value = price;
    if (qtyEl)   qtyEl.value   = "1";
    if (rateEl)  rateEl.value  = rate;

    if (typeof Alpine !== "undefined") {
      try {
        Alpine.evaluate(formRow, "price = " + (parseFloat(price) || 0) +
          ", qty = 1, rate = '" + (rate || "RATE_18") + "'");
      } catch (err) {}
    }
    recalcGrandTotal();
  }

  function pickCatalogItem(btn) {
    var formRow = window.activeItemRow;
    if (!formRow) return;

    var name  = btn.dataset.desc;
    var price = btn.dataset.price;
    var rate  = btn.dataset.rate;
    var pk    = btn.dataset.pk;

    var next    = formRow.nextElementSibling;
    var descEl  = formRow.querySelector('[name$="-description"]') ||
                  (next && next.querySelector('[name$="-description"]'));
    var priceEl = formRow.querySelector('[name$="-unit_price"]');
    var qtyEl   = formRow.querySelector('[name$="-quantity"]');
    var rateEl  = formRow.querySelector('[name$="-itbis_rate"]');
    var itemEl  = formRow.querySelector('[name$="-item"]');

    if (descEl)  descEl.value  = name;
    if (itemEl)  itemEl.value  = pk;
    if (priceEl) priceEl.value = price;
    if (qtyEl)   qtyEl.value   = "1";
    if (rateEl)  rateEl.value  = rate;

    if (typeof Alpine !== "undefined") {
      try {
        Alpine.evaluate(formRow, "price = " + (parseFloat(price) || 0) +
          ", qty = 1, rate = '" + (rate || "RATE_18") + "'");
      } catch (err) {}
    }
    recalcGrandTotal();
  }

  // ── Customer picker ──────────────────────────────────────────────────────

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

  function formatMoney(n) {
    return parseFloat(n || 0).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }

  function recalcGrandTotal() {
    var rateMap = { EXEMPT: 0, RATE_0: 0, RATE_16: 0.16, RATE_18: 0.18 };
    var subtotal = 0;
    var itbis18 = 0;
    var itbis16 = 0;

    document.querySelectorAll("#item-tbody tr").forEach(function (row) {
      var qEl = row.querySelector('[name$="-quantity"]');
      var pEl = row.querySelector('[name$="-unit_price"]');
      var rEl = row.querySelector('[name$="-itbis_rate"]');
      var dEl = row.querySelector('[name$="-DELETE"]');
      if (!qEl || !pEl || !rEl) return;

      var deleted = dEl && dEl.checked;
      var qty = parseInt(qEl.value, 10) || 0;
      var price = parseFloat(pEl.value) || 0;
      var rate = rEl.value;
      var base = qty * price;
      var itbis = base * (rateMap[rate] || 0);

      var subSpan = row.querySelector(".row-subtotal");
      var itbSpan = row.querySelector(".row-itbis");
      var totSpan = row.querySelector(".row-total");
      if (subSpan) subSpan.textContent = deleted ? "0.00" : formatMoney(base);
      if (itbSpan) itbSpan.textContent = deleted ? "0.00" : formatMoney(itbis);
      if (totSpan) totSpan.textContent = deleted ? "0.00" : formatMoney(base + itbis);

      if (deleted) return;
      subtotal += base;
      if (rate === "RATE_18") itbis18 += itbis;
      else if (rate === "RATE_16") itbis16 += itbis;
    });

    setText("grand-subtotal", formatMoney(subtotal));
    setText("grand-itbis18", formatMoney(itbis18));
    setText("grand-itbis16", formatMoney(itbis16));
    setText("grand-total", formatMoney(subtotal + itbis18 + itbis16));
  }

  function setText(id, text) {
    var el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  function initInvoiceItemFormset() {
    if (!document.getElementById("item-tbody")) return;
    recalcGrandTotal();

    var tbody = document.getElementById("item-tbody");
    tbody.addEventListener("input", function (e) {
      var n = e.target.name || "";
      if (n.endsWith("-quantity")) {
        var val = parseFloat(e.target.value);
        var warn = e.target.closest("td") && e.target.closest("td").querySelector(".qty-warning");
        if (warn) warn.classList.toggle("d-none", !val || val <= 0 || Number.isInteger(val));
        recalcGrandTotal();
      } else if (n.endsWith("-unit_price")) {
        recalcGrandTotal();
      }
    });
    tbody.addEventListener("change", function (e) {
      var n = e.target.name || "";
      if (n.endsWith("-itbis_rate")) recalcGrandTotal();
    });

    var pickerModal = document.getElementById("itemPickerModal");
    if (pickerModal) {
      pickerModal.addEventListener("hidden.bs.modal", function () {
        window.activePickerTr = null;
        var selBtn = document.getElementById("picker-select-btn");
        if (selBtn) selBtn.disabled = true;
      });
    }
  }

  function initInvoiceItemHtmx() {
    document.body.addEventListener("htmx:afterSwap", function (e) {
      if (e.detail.target && e.detail.target.id === "item-tbody") {
        var descRow = e.detail.target.lastElementChild;
        var mainRow = descRow && descRow.previousElementSibling;
        if (mainRow && typeof Alpine !== "undefined") Alpine.initTree(mainRow);
      }
      recalcGrandTotal();
    });
  }

  function applyCustomerDefaults(pk) {
    var defaults = (window.CUSTOMER_DEFAULTS || {})[pk];
    if (!defaults) return;

    var condSel = document.querySelector('[name="payment_condition"]');
    if (condSel && defaults.payment_condition) condSel.value = defaults.payment_condition;

    var daysDue = defaults.days_due || 0;
    if (daysDue > 0) {
      var issueDateEl = document.querySelector('[name="issue_date"]');
      var dueDateEl = document.querySelector('[name="due_date"]');
      if (issueDateEl && dueDateEl) {
        var base = issueDateEl.value ? new Date(issueDateEl.value) : new Date();
        base.setDate(base.getDate() + daysDue);
        dueDateEl.value = base.getFullYear() + "-" +
          String(base.getMonth() + 1).padStart(2, "0") + "-" +
          String(base.getDate()).padStart(2, "0");
      }
    }
  }

  function initCustomerDefaults() {
    var custSel = document.querySelector('[name="customer"]');
    if (!custSel || !window.CUSTOMER_DEFAULTS) return;
    custSel.addEventListener("change", function () {
      applyCustomerDefaults(this.value);
      if (document.querySelector(".module-sale-order")) {
        var deptSel = document.getElementById("id_department");
        if (deptSel) deptSel.value = "";
      }
    });
  }

  function updatePaymentTotal() {
    var sum = 0;
    document.querySelectorAll('[name="alloc_amounts"]').forEach(function (el) {
      var v = parseFloat(String(el.value).replace(",", ".")) || 0;
      if (v > 0) sum += v;
    });
    setText("payment-total", sum.toFixed(2));
    var submit = document.getElementById("submit-btn");
    if (submit) submit.disabled = sum <= 0;
  }

  function initPaymentForm() {
    var form = document.getElementById("payment-form");
    if (!form) return;
    document.addEventListener("htmx:afterSettle", function (evt) {
      if (evt.target && evt.target.id === "allocation-tbody") updatePaymentTotal();
    });
    form.addEventListener("input", function (e) {
      if (e.target && e.target.name === "alloc_amounts") updatePaymentTotal();
    });
    updatePaymentTotal();
  }

  function initTemplateModal(modalId, bodyId, templateId, titleId, titleConfigKey, processAlpine) {
    var modal = document.getElementById(modalId);
    var body = document.getElementById(bodyId);
    var tpl = document.getElementById(templateId);
    if (!modal || !body || !tpl) return;

    function restore() {
      body.innerHTML = "";
      body.appendChild(tpl.content.cloneNode(true));
      var title = document.getElementById(titleId);
      if (title) title.textContent = getConfig(titleConfigKey, title.textContent);
      if (window.htmx) htmx.process(body);
      if (processAlpine && typeof Alpine !== "undefined") Alpine.initTree(body);
    }

    restore();
    modal.addEventListener("hidden.bs.modal", restore);
  }

  function initItemModal() {
    initTemplateModal("itemModal", "item-modal-body", "item-blank-tpl", "itemModalLabel", "itemCreateTitle", true);
    document.body.addEventListener("htmx:afterSwap", function (e) {
      if (e.detail.target && e.detail.target.id === "item-modal-body") {
        var title = document.getElementById("itemModalLabel");
        if (title) title.textContent = getConfig("itemEditTitle", title.textContent);
        if (typeof Alpine !== "undefined") Alpine.initTree(e.detail.target);
      }
    });
  }

  function initCustomerList() {
    initDeptPopovers();
    document.body.addEventListener("htmx:afterSwap", function (evt) {
      if (evt.detail && evt.detail.target && evt.detail.target.id === "dt-results") {
        initDeptPopovers(evt.detail.target);
      }
    });

    initTemplateModal("customerModal", "customer-modal-body", "customer-blank-tpl", "customerModalTitle", "customerCreateTitle", false);

    document.body.addEventListener("rncFound", function (evt) {
      if (!window.Swal) return;
      var d = evt.detail || {};
      Swal.fire({
        icon: "success",
        title: getConfig("rncFoundTitle", "RNC encontrado"),
        html: '<p class="mb-1"><strong>' + escapeHtml(d.name) + '</strong></p><small class="text-muted">RNC ' + escapeHtml(d.value) + "</small>",
        showCancelButton: true,
        confirmButtonText: getConfig("acceptText", "Aceptar"),
        cancelButtonText: getConfig("cancelText", "Cancelar"),
      }).then(function (result) {
        if (result.isConfirmed) {
          var f = (document.querySelector(".modal.show") || document).querySelector("[name=name]");
          if (f) f.value = d.name;
        }
      });
    });

    document.body.addEventListener("rncNotFound", function () {
      if (!window.Swal) return;
      Swal.fire({
        icon: "warning",
        title: getConfig("rncNotFoundTitle", "No encontrado"),
        text: getConfig("rncNotFoundText", "Este RNC/Cedula no esta registrado en el registro oficial."),
        confirmButtonText: getConfig("closeText", "Cerrar"),
      });
    });
  }

  function initDeptPopovers(root) {
    if (!window.bootstrap) return;
    (root || document).querySelectorAll(".dept-popover").forEach(function (el) {
      var existing = bootstrap.Popover.getInstance(el);
      if (existing) existing.dispose();
      var depts = [];
      try { depts = JSON.parse(el.dataset.departments || "[]"); } catch (err) {}
      var html = '<ul class="mb-0 ps-3 small">' +
        depts.map(function (d) { return "<li>" + escapeHtml(d) + "</li>"; }).join("") +
        "</ul>";
      new bootstrap.Popover(el, {
        title: getConfig("departmentsTitle", "Departamentos"),
        content: html,
        html: true,
        trigger: "hover focus",
        placement: "left",
        container: "body",
      });
    });
  }

  function initModuleModal() {
    initTemplateModal("moduleModal", "module-modal-body", "module-blank-tpl", "moduleModalLabel", "moduleCreateTitle", false);
    document.body.addEventListener("htmx:afterSwap", function (e) {
      if (e.detail.target && e.detail.target.id === "module-modal-body") {
        var title = document.getElementById("moduleModalLabel");
        if (title) title.textContent = getConfig("moduleEditTitle", title.textContent);
      }
    });
  }

  function initPaymentTermModal() {
    initTemplateModal("paymentTermModal", "payment-term-modal-body", "payment-term-blank-tpl", "paymentTermModalLabel", "paymentTermCreateTitle", false);
    document.body.addEventListener("htmx:afterSwap", function (e) {
      if (e.detail.target && e.detail.target.id === "payment-term-modal-body") {
        var title = document.getElementById("paymentTermModalLabel");
        if (title) title.textContent = getConfig("paymentTermEditTitle", title.textContent);
      }
    });
  }

  function initNcfModal() {
    initTemplateModal("ncfSequenceModal", "ncf-modal-body", "ncf-blank-tpl", "", "", false);
  }

  function confirmDeleteNCF(btn) {
    if (!window.Swal) {
      btn.closest("form").submit();
      return;
    }
    Swal.fire({
      icon: "warning",
      title: getConfig("ncfDeleteTitle", "Eliminar secuencia?"),
      text: getConfig("ncfDeleteText", "Esta accion no se puede deshacer."),
      showCancelButton: true,
      confirmButtonText: getConfig("ncfDeleteConfirm", "Si, eliminar"),
      cancelButtonText: getConfig("cancelText", "Cancelar"),
      confirmButtonColor: "#dc3545",
    }).then(function (result) {
      if (result.isConfirmed) btn.closest("form").submit();
    });
  }

  function initDeptModalClose() {
    document.body.addEventListener("closeDeptModal", function () {
      if (!window.bootstrap) return;
      var modal = document.getElementById("deptModal");
      if (modal) bootstrap.Modal.getOrCreateInstance(modal).hide();
    });
  }

  function initConsolidateForm() {
    var custSel = document.querySelector("#consolidate-form #id_customer");
    if (!custSel || !window.htmx) return;
    custSel.addEventListener("change", function () {
      var pk = this.value;
      var deptSel = document.getElementById("id_department");
      if (!deptSel) return;
      deptSel.value = "";
      if (pk) {
        htmx.ajax("GET", (window.DEPARTMENTS_FOR_CUSTOMER_URL || "") + "?customer=" + encodeURIComponent(pk), {
          target: "#id_department",
          swap: "innerHTML",
        });
      } else {
        deptSel.innerHTML = getConfig("allDepartmentsOption", '<option value="">-- Todos los departamentos --</option>');
      }
    });
  }

  function initDashboardCharts() {
    if (!window.Chart || !document.getElementById("revenueChart")) return;

    var months = parseJsonScript("chart-months", []);
    var invoiced = parseJsonScript("chart-invoiced", []);
    var collected = parseJsonScript("chart-collected", []);
    var stLabels = parseJsonScript("chart-status-labels", []);
    var stCounts = parseJsonScript("chart-status-counts", []);
    var stColors = parseJsonScript("chart-status-colors", []);
    var custDatasets = parseJsonScript("chart-customer-datasets", []);

    new Chart(document.getElementById("revenueChart"), {
      type: "bar",
      data: {
        labels: months,
        datasets: [
          { label: getConfig("chartInvoicedLabel", "Facturado"), data: invoiced, backgroundColor: "rgba(13,110,253,0.75)", borderRadius: 4 },
          { label: getConfig("chartCollectedLabel", "Cobrado"), data: collected, backgroundColor: "rgba(25,135,84,0.75)", borderRadius: 4 },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "top" } },
        scales: { y: { beginAtZero: true, ticks: { maxTicksLimit: 6 } } },
      },
    });

    if (stCounts.length) {
      new Chart(document.getElementById("statusChart"), {
        type: "doughnut",
        data: { labels: stLabels, datasets: [{ data: stCounts, backgroundColor: stColors, borderWidth: 2 }] },
        options: { responsive: true, plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } } } },
      });
    } else {
      replaceChartPanel("statusChart", getConfig("chartNoInvoicesText", "Sin facturas registradas."));
    }

    if (custDatasets.length) {
      new Chart(document.getElementById("customerChart"), {
        type: "bar",
        data: { labels: months, datasets: custDatasets },
        options: {
          responsive: true,
          plugins: { legend: { position: "top", labels: { boxWidth: 12 } } },
          scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, ticks: { maxTicksLimit: 6 } } },
        },
      });
    } else {
      replaceChartPanel("customerChart", getConfig("chartNoCustomerDataText", "Sin datos de clientes."));
    }
  }

  function replaceChartPanel(canvasId, text) {
    var canvas = document.getElementById(canvasId);
    var panel = canvas && canvas.closest(".db-panel-body");
    if (panel) panel.innerHTML = '<p class="text-muted small text-center py-3 mb-0">' + escapeHtml(text) + "</p>";
  }

  function initAutoPrint() {
    if (document.body && document.body.dataset.autoPrint === "true") {
      window.addEventListener("load", function () { window.print(); });
    }
  }

  window.swalConfirm = swalConfirm;
  window.toggleSidebar = toggleSidebar;
  window.passwordChecker = passwordChecker;
  window.avatarHandler = avatarHandler;
  window.itemForm = itemForm;
  window.invoiceForm = invoiceForm;
  window.dtTable = dtTable;
  window.dtSort = dtSort;
  window.dtPage = dtPage;
  window.itemRow = itemRow;
  window.deleteRow = deleteRow;
  window.openItemPicker = openItemPicker;
  window.itemPickerHighlight = itemPickerHighlight;
  window.itemPickerConfirm = itemPickerConfirm;
  window.itemPickerShowCreate = itemPickerShowCreate;
  window.itemPickerShowSearch = itemPickerShowSearch;
  window.itemPickerQuickCreate = itemPickerQuickCreate;
  window.openCustomerPicker = openCustomerPicker;
  window.customerPickerSelect = customerPickerSelect;
  window.customerPickerHighlight = customerPickerHighlight;
  window.customerPickerShowCreate = customerPickerShowCreate;
  window.customerPickerShowSearch = customerPickerShowSearch;
  window.customerPickerQuickCreate = customerPickerQuickCreate;
  window.recalcGrandTotal = recalcGrandTotal;
  window.confirmDeleteNCF = confirmDeleteNCF;
  window.pickCatalogItem = pickCatalogItem;

  ready(function () {
    initToasts();
    initPasswordToggles();
    initSidebarState();
    initDatatableFilters();
    initInvoiceItemFormset();
    initInvoiceItemHtmx();
    initCustomerDefaults();
    initPaymentForm();
    initItemModal();
    initModuleModal();
    initPaymentTermModal();
    initCustomerList();
    initNcfModal();
    initDeptModalClose();
    initConsolidateForm();
    initDashboardCharts();
    initAutoPrint();
  });
})();
