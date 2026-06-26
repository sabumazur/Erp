(function () {
  function initOptionalFields() {
    var addRow = document.getElementById("opt-add-row");
    if (!addRow || addRow.dataset.optInit) return;
    addRow.dataset.optInit = "1";

    document.querySelectorAll(".doc-optfield-wrap").forEach(function (wrap) {
      var field = wrap.querySelector("textarea, input:not([type=hidden])");
      var chip  = addRow.querySelector('[data-target="' + wrap.id + '"]');

      var remove = wrap.querySelector(".doc-optfield-remove");
      if (!remove) {
        remove = document.createElement("button");
        remove.type = "button";
        remove.className = "doc-optfield-remove";
        remove.innerHTML = '<i class="bi bi-x-lg"></i> ' + (window.OPT_REMOVE_LABEL || "Quitar");
        wrap.insertBefore(remove, wrap.firstChild);
      }

      function show(focus) {
        wrap.classList.add("is-open");
        if (chip) chip.style.display = "none";
        if (focus && field) field.focus();
        syncAddRow();
      }
      function hide() {
        wrap.classList.remove("is-open");
        if (field) field.value = "";
        if (chip) chip.style.display = "";
        syncAddRow();
      }

      if (chip) chip.addEventListener("click", function () { show(true); });
      remove.addEventListener("click", hide);

      if (field && field.value.trim() !== "") { show(false); } else { hide(); }
    });
    syncAddRow();
  }

  function syncAddRow() {
    var addRow = document.getElementById("opt-add-row");
    if (!addRow) return;
    var anyChipVisible = !!addRow.querySelector('.doc-optfield-chip:not([style*="display: none"])');
    addRow.style.display = anyChipVisible ? "" : "none";
  }

  document.addEventListener("DOMContentLoaded", initOptionalFields);
})();
