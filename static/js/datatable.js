(function () {
  "use strict";

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

  window.dtTable = dtTable;
  window.dtSort = dtSort;
  window.dtPage = dtPage;
  window.initDatatableFilters = initDatatableFilters;
})();
