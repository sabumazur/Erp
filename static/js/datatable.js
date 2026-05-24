(function () {
  "use strict";

  function dtTable(tableId, allCols, defaultVisible) {
    return {
      // Column visibility state
      tableId: tableId,
      allCols: allCols,
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
        this.visible = saved ? JSON.parse(saved) : defaultVisible.slice();
        this.$nextTick(function () { self.applyColVisibility(); });

        document.addEventListener("htmx:afterSwap", function (e) {
          if (e.detail.target && e.detail.target.id === "dt-results") {
            self.applyColVisibility();
            self.clearSelection();
          }
        });
      },

      // ── Column visibility ────────────────────────────────────────────────
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
        if (this.selectedRow) {
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
        if (this.selectedRow) {
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
        event.preventDefault();

        if (key === "Enter") {
          if (this.selectedDetailUrl) {
            window.location.href = this.selectedDetailUrl;
          }
          return;
        }

        if (key === "Delete") {
          if (this.selectedPk !== null) {
            document.dispatchEvent(new CustomEvent("dt:delete-selected", {
              detail: { pk: this.selectedPk, status: this.selectedStatus }
            }));
          }
          return;
        }

        // Arrow navigation
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

  window.dtTable = dtTable;
  window.dtSort = dtSort;
  window.dtPage = dtPage;
  window.initDatatableFilters = initDatatableFilters;
})();
