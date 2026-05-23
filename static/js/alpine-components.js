(function () {
  "use strict";

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

  function signatureHandler(currentUrl) {
    return {
      previewSrc: currentUrl || "",
      hasSignature: !!currentUrl,
      fileName: "",
      change: function (e) {
        var file = e.target.files[0];
        if (!file) return;
        this.previewSrc = URL.createObjectURL(file);
        this.hasSignature = true;
        this.fileName = file.name;
        this.$refs.clearInput.checked = false;
      },
      clear: function () {
        this.previewSrc = "";
        this.hasSignature = false;
        this.fileName = "";
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

  window.passwordChecker = passwordChecker;
  window.avatarHandler = avatarHandler;
  window.signatureHandler = signatureHandler;
  window.itemForm = itemForm;
  window.invoiceForm = invoiceForm;
})();
