(function () {
  "use strict";

  function dtTable(tableId, allCols, defaultVisible) {
    return {
      // Column visibility state
      tableId: tableId,
      allCols: allCols,
      defaultVisible: defaultVisible,
      visible: [],

      // Single-row selection state
      selectedRow: null,
      selectedPk: null,
      selectedStatus: null,
      selectedDetailUrl: null,

      // Computed helper: true when a row is selected
      get canAct() { return this.selectedPk !== null; },

      init: function () {
        var self = this;
        var saved = localStorage.getItem("dt-visible-" + tableId);
        try {
          this.visible = saved ? JSON.parse(saved) : defaultVisible.slice();
          this.visible = this.normalizeVisible(this.visible);
        } catch (e) {
          this.visible = this.normalizeVisible(defaultVisible);
          localStorage.removeItem("dt-visible-" + tableId);
        }
        this.$nextTick(function () { self.applyColVisibility(); });

        // Single source of truth: any change to `visible` (checkbox x-model,
        // select-all, deselect) reactively persists + re-applies column display.
        this.$watch("visible", function (val) {
          // Empty-guard: never hide every column — fall back to one.
          if ((!val || val.length === 0) && self.allCols.length > 0) {
            self.visible = self.normalizeVisible([]);
            return; // re-assignment re-fires this watcher with the fallback
          }
          self.persistVisibility();
          self.applyColVisibility();
        });

        this._swapHandler = function (e) {
          if (e.detail.target && e.detail.target.id === "dt-results") {
            self.$nextTick(function () { self.applyColVisibility(); });
            self.clearSelection();
          }
        };
        document.addEventListener("htmx:afterSwap", this._swapHandler);
      },

      destroy: function () {
        document.removeEventListener("htmx:afterSwap", this._swapHandler);
      },

      // ── Column visibility ────────────────────────────────────────────────
      normalizeVisible: function (cols) {
        var source = Array.isArray(cols) ? cols : [];
        var seen = {};
        var normalized = [];
        source.forEach(function (key) {
          if (this.allCols.includes(key) && !seen[key]) {
            seen[key] = true;
            normalized.push(key);
          }
        }, this);
        if (normalized.length === 0 && this.allCols.length > 0) {
          var fallback = this.defaultVisible.find(function (key) {
            return this.allCols.includes(key);
          }, this) || this.allCols[0];
          normalized.push(fallback);
        }
        return normalized;
      },
      persistVisibility: function () {
        localStorage.setItem("dt-visible-" + this.tableId, JSON.stringify(this.visible));
      },
      setVisible: function (cols) {
        // Reassign only — the $watch on `visible` persists + applies.
        this.visible = this.normalizeVisible(cols);
      },
      selectAllCols: function () {
        this.setVisible(this.allCols.slice());
      },
      unselectCols: function () {
        this.setVisible([]);
      },
      applyColVisibility: function () {
        var $el = this.$el;
        if (!$el) return;
        this.allCols.forEach(function (col) {
          var show = this.visible.includes(col);
          $el.querySelectorAll('[data-col="' + col + '"]').forEach(function (el) {
            el.style.display = show ? "" : "none";
          });
        }, this);
      },

      // ── Single-row selection ─────────────────────────────────────────────
      selectRow: function (tr) {
        if (tr === this.selectedRow) {
          // Toggle off — clicking the already-selected row deselects it
          tr.classList.remove("dt-row-selected");
          this.selectedRow = null;
          this.selectedPk = null;
          this.selectedStatus = null;
          this.selectedDetailUrl = null;
          return;
        }
        // Deselect previous row if any
        if (this.selectedRow && document.contains(this.selectedRow)) {
          this.selectedRow.classList.remove("dt-row-selected");
        }
        // Select new row
        this.selectedRow = tr;
        this.selectedPk = tr.dataset.pk || null;
        this.selectedStatus = tr.dataset.status || null;
        this.selectedDetailUrl = tr.dataset.detailUrl || null;
        tr.classList.add("dt-row-selected");
      },

      clearSelection: function () {
        if (this.selectedRow && document.contains(this.selectedRow)) {
          this.selectedRow.classList.remove("dt-row-selected");
        }
        this.selectedRow = null;
        this.selectedPk = null;
        this.selectedStatus = null;
        this.selectedDetailUrl = null;
      },

      // ── Keyboard navigation ──────────────────────────────────────────────
      handleKey: function (event) {
        var key = event.key;
        if (key !== "ArrowUp" && key !== "ArrowDown" && key !== "Enter" && key !== "Delete") {
          return;
        }

        if (key === "Enter") {
          if (this.selectedDetailUrl) {
            event.preventDefault();
            window.location.href = this.selectedDetailUrl;
          }
          return;
        }

        if (key === "Delete") {
          if (this.selectedPk !== null) {
            event.preventDefault();
            document.dispatchEvent(new CustomEvent("dt:delete-selected", {
              detail: { pk: this.selectedPk, status: this.selectedStatus }
            }));
          }
          return;
        }

        // Arrow navigation
        event.preventDefault();
        var tbody = this.$el.querySelector("table tbody");
        if (!tbody) return;
        var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
        if (rows.length === 0) return;

        if (!this.selectedRow) {
          // No current selection — ArrowDown picks first, ArrowUp picks last
          this.selectRow(key === "ArrowDown" ? rows[0] : rows[rows.length - 1]);
          return;
        }

        var idx = rows.indexOf(this.selectedRow);
        if (idx === -1) {
          this.selectRow(key === "ArrowDown" ? rows[0] : rows[rows.length - 1]);
          return;
        }
        if (key === "ArrowDown") {
          if (idx < rows.length - 1) this.selectRow(rows[idx + 1]);
        } else {
          // ArrowUp
          if (idx > 0) this.selectRow(rows[idx - 1]);
        }
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

  function dtPageSize(n) {
    var form = document.getElementById("dt-form");
    var sizeEl = document.getElementById("dt-page-size-input");
    var pageEl = document.getElementById("dt-page-input");
    if (!form || !sizeEl || !window.htmx) return;
    sizeEl.value = n;
    if (pageEl) pageEl.value = "1";
    htmx.trigger(form, "submit");
  }

  function closeFilterDropdown(form) {
    if (!window.bootstrap || !form) return;
    var toggle = form.querySelector(".dt-filter-toggle[aria-expanded='true']");
    if (!toggle) return;
    var dropdown = bootstrap.Dropdown.getInstance(toggle) || new bootstrap.Dropdown(toggle);
    dropdown.hide();
  }

  function dtClearFilters(form) {
    if (!form || !window.htmx) return;

    var search = form.querySelector('[name="q"]');
    if (search) search.value = "";

    var menu = form.querySelector(".dt-filter-menu");
    if (menu) {
      menu.querySelectorAll("input, select, textarea").forEach(function (field) {
        if (!field.name || field.type === "hidden" || field.disabled) return;

        if (field.tomselect) {
          field.tomselect.clear(true);
          field.tomselect.refreshItems();
          return;
        }

        if (field.type === "checkbox" || field.type === "radio") {
          field.checked = false;
        } else {
          field.value = "";
        }
      });
    }

    var pageEl = form.querySelector("#dt-page-input");
    if (pageEl) pageEl.value = "1";
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
      if (!e.detail.elt || e.detail.elt.id !== "dt-form") return;
      closeFilterDropdown(e.detail.elt);
    });
  }

  window.dtTable = dtTable;
  window.dtSort = dtSort;
  window.dtPage = dtPage;
  window.dtPageSize = dtPageSize;
  window.dtClearFilters = dtClearFilters;
  window.initDatatableFilters = initDatatableFilters;
})();
