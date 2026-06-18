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

  var EDITABLE_MODALS = [
    { modal: "itemModal",        body: "item-modal-body",         template: "item-blank-tpl",         titleId: "itemModalLabel",        createKey: "itemCreateTitle",        editKey: "itemEditTitle",        alpine: true  },
    { modal: "moduleModal",      body: "module-modal-body",       template: "module-blank-tpl",       titleId: "moduleModalLabel",      createKey: "moduleCreateTitle",      editKey: "moduleEditTitle",      alpine: false },
    { modal: "paymentTermModal", body: "payment-term-modal-body", template: "payment-term-blank-tpl", titleId: "paymentTermModalLabel", createKey: "paymentTermCreateTitle", editKey: "paymentTermEditTitle", alpine: false },
  ];

  function initEditableModals() {
    EDITABLE_MODALS.forEach(function (m) {
      initTemplateModal(m.modal, m.body, m.template, m.titleId, m.createKey, m.alpine);
      document.body.addEventListener("htmx:afterSwap", function (e) {
        if (e.detail.target && e.detail.target.id === m.body) {
          var title = document.getElementById(m.titleId);
          if (title && m.editKey) title.textContent = getConfig(m.editKey, title.textContent);
          if (m.alpine && typeof Alpine !== "undefined") Alpine.initTree(e.detail.target);
        }
      });
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

    function normalizeTaxId(value) {
      return String(value || "").replace(/\D/g, "");
    }

    function activeTaxIdForm() {
      var modal = document.querySelector("#customerModal.show");
      if (modal) {
        return modal.querySelector("form");
      }
      var supplierModal = document.querySelector("#supplierModal.show");
      if (supplierModal) {
        return supplierModal.querySelector("form");
      }
      var taxId = document.querySelector("form [name=rnc_cedula]");
      return taxId ? taxId.closest("form") : null;
    }

    function taxIdField(form) {
      return form.querySelector("[name=rnc_cedula]");
    }

    // Flag set synchronously before Swal.fire() — guards against duplicate events
    // that fire before SweetAlert2 has added .swal2-popup to the DOM (so
    // Swal.isVisible() would still return false during the opening animation).
    var _rncSwalPending = false;

    document.body.addEventListener("rncFound", function (evt) {
      if (!window.Swal || _rncSwalPending) return;
      _rncSwalPending = true;
      var d = evt.detail || {};
      Swal.fire({
        icon: "success",
        title: getConfig("rncFoundTitle", "RNC encontrado"),
        html: '<p class="mb-1"><strong>' + escapeHtml(d.name) + '</strong></p><small class="text-muted">RNC ' + escapeHtml(d.value) + "</small>",
        showCancelButton: true,
        confirmButtonText: getConfig("acceptText", "Aceptar"),
        cancelButtonText: getConfig("cancelText", "Cancelar"),
        allowOutsideClick: false,
        allowEscapeKey: false,
      }).then(function (result) {
        _rncSwalPending = false;
        if (result.isConfirmed) {
          var form = activeTaxIdForm();
          if (!form) return;
          var rnc = taxIdField(form);
          var name = form.querySelector("[name=name]");
          if (!rnc || !name) return;
          if (d.normalized_value && normalizeTaxId(rnc.value) !== d.normalized_value) return;
          name.value = d.name;
        }
      });
    });

    document.body.addEventListener("rncNotFound", function () {
      if (!window.Swal || _rncSwalPending) return;
      _rncSwalPending = true;
      Swal.fire({
        icon: "warning",
        title: getConfig("rncNotFoundTitle", "No encontrado"),
        text: getConfig("rncNotFoundText", "Este RNC/Cedula no esta registrado en el registro oficial."),
        confirmButtonText: getConfig("closeText", "Cerrar"),
      }).then(function () {
        _rncSwalPending = false;
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

    function refreshDeptWidget(deptSel) {
      if (window.SabSysTom && deptSel.parentNode) {
        window.SabSysTom.init(deptSel.parentNode);
      }
    }

    function onCustomerChange(pk) {
      var deptSel = document.getElementById("id_department");
      if (!deptSel) return;
      if (deptSel.tomselect) deptSel.tomselect.destroy();
      if (pk) {
        htmx.ajax("GET", (window.DEPARTMENTS_FOR_CUSTOMER_URL || "") + "?customer=" + encodeURIComponent(pk), {
          target: "#id_department",
          swap: "innerHTML",
        }).then(function () { refreshDeptWidget(deptSel); });
      } else {
        deptSel.innerHTML = getConfig("allDepartmentsOption", '<option value="">-- Todos los departamentos --</option>');
        refreshDeptWidget(deptSel);
      }
    }

    // Prefer TomSelect's own event API — it fires reliably when the user picks
    // a value via TomSelect's UI, where a native DOM "change" event may not fire.
    if (custSel.tomselect) {
      custSel.tomselect.on("change", function (value) { onCustomerChange(value); });
    } else {
      custSel.addEventListener("change", function () { onCustomerChange(this.value); });
    }
  }

  window.confirmDeleteNCF = confirmDeleteNCF;
  window.initEditableModals = initEditableModals;
  window.initCustomerList = initCustomerList;
  window.initNcfModal = initNcfModal;
  window.initDeptModalClose = initDeptModalClose;
  window.initConsolidateForm = initConsolidateForm;
})();
