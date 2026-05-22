(function () {
  "use strict";

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
      var html = depts.map(function (d) {
        return '<div class="dept-chip"><span class="dept-chip-dot"></span>' + escapeHtml(d) + "</div>";
      }).join("");
      new bootstrap.Popover(el, {
        title: '<i class="bi bi-diagram-3 me-1"></i>' + escapeHtml(getConfig("departmentsTitle", "Departamentos")),
        content: html || '<span class="text-muted small">—</span>',
        html: true,
        trigger: "hover focus",
        placement: "left",
        container: "body",
        customClass: "dept-popover-bs",
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

  window.confirmDeleteNCF = confirmDeleteNCF;
  window.initItemModal = initItemModal;
  window.initCustomerList = initCustomerList;
  window.initModuleModal = initModuleModal;
  window.initPaymentTermModal = initPaymentTermModal;
  window.initNcfModal = initNcfModal;
  window.initDeptModalClose = initDeptModalClose;
  window.initConsolidateForm = initConsolidateForm;
})();
