(function () {
  "use strict";

  var STORAGE_KEY = "sabsys.session.deadline";
  var KEEPALIVE_THROTTLE_MS = 60000;

  function initSessionTimeout() {
    var el = document.getElementById("session-timeout-config");
    if (!el) return;

    var config;
    try {
      config = JSON.parse(el.textContent);
    } catch (err) {
      return;
    }

    var expiresAt = new Date(config.expiresAt).getTime();
    var serverOffsetMs = Date.now() - new Date(config.serverNow).getTime();
    var lastKeepalive = 0;
    var warningOpen = false;
    var absoluteWarningAcknowledged = false;
    var logoutSubmitted = false;

    function csrfToken() {
      var field = document.querySelector("[name=csrfmiddlewaretoken]");
      return field ? field.value : "";
    }

    function serverNowMs() {
      return Date.now() - serverOffsetMs;
    }

    function publishDeadline() {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        expiresAt: new Date(expiresAt).toISOString(),
        expiryReason: config.expiryReason,
        serverNow: new Date(serverNowMs()).toISOString(),
        updatedAt: Date.now(),
      }));
    }

    function publishLogout() {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ loggedOut: true, updatedAt: Date.now() }));
    }

    function submitLogout(announce) {
      if (logoutSubmitted) return;
      logoutSubmitted = true;
      if (announce !== false) publishLogout();
      var form = document.getElementById("session-logout-form");
      if (form) {
        form.requestSubmit();
      } else {
        window.location.assign(config.loginUrl);
      }
    }

    function applyDeadline(data) {
      var nextExpiresAt = new Date(data.expires_at || data.expiresAt).getTime();
      var nextReason = data.expiry_reason || data.expiryReason || config.expiryReason;
      var nextServerNow = data.server_now || data.serverNow;
      if (nextServerNow) {
        serverOffsetMs = Date.now() - new Date(nextServerNow).getTime();
      }
      if (nextReason !== "absolute" || nextExpiresAt !== expiresAt) {
        absoluteWarningAcknowledged = false;
      }
      expiresAt = nextExpiresAt;
      config.expiryReason = nextReason;
      publishDeadline();
      if (warningOpen && window.Swal && Swal.isVisible()) {
        Swal.close();
      }
      warningOpen = false;
    }

    function keepalive() {
      if (Date.now() - lastKeepalive < KEEPALIVE_THROTTLE_MS) return;
      lastKeepalive = Date.now();
      fetch(config.keepaliveUrl, {
        method: "POST",
        keepalive: true,
        credentials: "same-origin",
        headers: {
          "X-CSRFToken": csrfToken(),
          "X-Requested-With": "XMLHttpRequest",
        },
      }).then(function (response) {
        if (response.status === 401) {
          publishLogout();
          window.location.assign(config.loginUrl);
          return null;
        }
        return response.ok ? response.json() : null;
      }).then(function (data) {
        if (data) applyDeadline(data);
      });
    }

    function showWarning() {
      if (warningOpen || !window.Swal) return;
      warningOpen = true;
      var absolute = config.expiryReason === "absolute";
      if (absolute && absoluteWarningAcknowledged) {
        warningOpen = false;
        return;
      }
      Swal.fire({
        icon: "warning",
        title: "Tu sesión está por expirar",
        text: absolute
          ? "Alcanzaste el límite máximo de sesión. Guarda tu trabajo; deberás iniciar sesión nuevamente."
          : "No hay autoguardado. Guarda tu trabajo o continúa la sesión antes de que expire.",
        showCancelButton: !absolute,
        confirmButtonText: absolute ? "Seguir trabajando" : "Continuar sesión",
        cancelButtonText: "Cerrar sesión",
        allowOutsideClick: false,
      }).then(function (result) {
        warningOpen = false;
        if (!absolute && result.isConfirmed) {
          lastKeepalive = 0;
          keepalive();
        } else if (absolute && result.isConfirmed) {
          absoluteWarningAcknowledged = true;
        } else if (!result.isConfirmed) {
          submitLogout();
        }
      });
    }

    ["keydown", "pointerdown", "input", "change"].forEach(function (eventName) {
      document.addEventListener(eventName, keepalive, { passive: true });
    });

    var logoutForm = document.getElementById("session-logout-form");
    if (logoutForm) {
      logoutForm.addEventListener("submit", publishLogout);
    }

    document.body.addEventListener("htmx:afterRequest", function (event) {
      var xhr = event.detail && event.detail.xhr;
      if (!xhr) return;
      var headerDeadline = xhr.getResponseHeader("X-Session-Expires-At");
      if (!headerDeadline) return;
      applyDeadline({
        expiresAt: headerDeadline,
        expiryReason: xhr.getResponseHeader("X-Session-Expiry-Reason"),
        serverNow: xhr.getResponseHeader("X-Session-Server-Now"),
      });
    });

    window.addEventListener("storage", function (event) {
      if (event.key !== STORAGE_KEY || !event.newValue) return;
      var data = JSON.parse(event.newValue);
      if (data.loggedOut) {
        submitLogout(false);
      } else if (data.expiresAt) {
        if (data.serverNow) {
          serverOffsetMs = Date.now() - new Date(data.serverNow).getTime();
        }
        expiresAt = new Date(data.expiresAt).getTime();
        config.expiryReason = data.expiryReason || config.expiryReason;
      }
    });

    publishDeadline();
    window.setInterval(function () {
      var now = serverNowMs();
      if (now >= expiresAt) {
        submitLogout();
      } else if (now >= expiresAt - (config.warningSeconds * 1000)) {
        showWarning();
      }
    }, 1000);
  }

  window.initSessionTimeout = initSessionTimeout;
})();
