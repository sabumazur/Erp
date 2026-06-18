(function () {
  "use strict";

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

    // Update aria-expanded on sidebar toggle button
    var btn = document.getElementById('sidebar-toggle-btn');
    if (btn) {
      var isOpen = document.body.classList.contains('sidebar-open') ||
                   !document.body.classList.contains('sidebar-collapsed');
      btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
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

  function initAutoPrint() {
    if (document.body && document.body.dataset.autoPrint === "true") {
      window.addEventListener("load", function () { window.print(); });
    }
  }

  window.swalConfirm = swalConfirm;
  window.toggleSidebar = toggleSidebar;
  window.initToasts = initToasts;
  window.initPasswordToggles = initPasswordToggles;
  window.initSidebarState = initSidebarState;
  window.initAutoPrint = initAutoPrint;
})();
