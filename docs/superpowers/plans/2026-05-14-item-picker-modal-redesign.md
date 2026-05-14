# Item Picker Modal Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the shared item picker modal to match Microsoft Dynamics 365's "show from full list" lookup dialog — clean gray-header shell, sortable columns, client-side pagination (20/page), D365 blue `#0078d4` accent.

**Architecture:** All items remain client-side in `window.ITEM_CATALOG`. The `picker` JS object gains `sortKey`, `sortDir`, and `page` state. `pickerRender()` is extended to sort + paginate before rendering. Three new helpers (`pickerRenderPagination`, `pickerGoPage`, `pickerUpdateSortHeaders`) manage pagination UI and sort indicators. Single shared template — no per-document changes.

**Tech Stack:** Bootstrap 5, vanilla JS, Django templates, Bootstrap Icons

---

## File Map

| File | Change |
|------|--------|
| `templates/invoices/partials/item_picker_modal.html` | Full rewrite — D365 shell, add `#picker-pagination` div, drop icon badge + left accent border |
| `static/css/app.css` (lines 970–1083) | Replace picker CSS block with D365 styles |
| `static/js/app.js` line 360 | Extend `picker` object with `sortKey`, `sortDir`, `page` |
| `static/js/app.js` lines 362–406 | Rewrite `pickerRender()` — sort + paginate before render, use `picker-selected` class |
| `static/js/app.js` after line 414 | Add `pickerRenderPagination()`, `pickerGoPage()`, `pickerUpdateSortHeaders()` |
| `static/js/app.js` lines 523–538 | Update `initInvoiceItemFormset()` — reset page on search/open, add sort header handler |
| `static/js/app.js` globals block (~line 828) | Expose `pickerGoPage` on `window` |

---

## Task 1: CSS — Replace picker block with D365 styles

**Files:**
- Modify: `static/css/app.css` (lines 970–1083)

- [ ] **Step 1: Locate and replace the picker CSS block**

Find the block starting at `/* ── Item Picker Modal` and ending at `#picker-select-btn:disabled { opacity: 0.35; }`. Replace the entire block with:

```css
/* ── Item Picker Modal ──────────────────────────────────────── */

#itemPickerModal.fade .picker-dialog {
  transform: translateY(-14px) scale(0.98);
  transition: transform 0.22s cubic-bezier(0.2, 0, 0, 1) !important;
}
#itemPickerModal.show .picker-dialog {
  transform: none !important;
}

#itemPickerModal .picker-dialog {
  max-width: 560px;
  margin-top: 6vh;
}

#itemPickerModal .picker-content {
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
  box-shadow: 0 4px 16px rgba(0,0,0,0.10);
}

.picker-head {
  background: #f3f3f3;
  border-bottom: 1px solid #e0e0e0;
  padding: 12px 16px;
}

.picker-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: #1f1f1f;
}

.picker-search-area {
  border-bottom: 1px solid #e0e0e0;
  padding: 10px 16px;
}

.picker-search-area .input-group-text {
  background: transparent;
  border-right: 0;
  color: #605e5c;
}

.picker-search-input {
  border-left: 0;
  padding-left: 4px;
}

.picker-search-input:focus {
  border-color: #0078d4;
  box-shadow: 0 0 0 2px rgba(0,120,212,0.25);
}

.picker-search-area .input-group:focus-within .input-group-text {
  border-color: #0078d4;
}

.picker-list-wrap {
  max-height: 340px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #e2e8f0 transparent;
}
.picker-list-wrap::-webkit-scrollbar       { width: 4px; }
.picker-list-wrap::-webkit-scrollbar-thumb { background: #e2e8f0; border-radius: 2px; }

#itemPickerModal .picker-table thead th {
  font-size: 0.68rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #605e5c;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
}

#itemPickerModal .picker-table thead th:hover { color: #0078d4; }

#itemPickerModal .picker-table thead th .picker-sort-icon {
  font-size: 0.60rem;
  margin-left: 3px;
  opacity: 0.4;
}

#itemPickerModal .picker-table thead th.picker-sort-active .picker-sort-icon {
  opacity: 1;
  color: #0078d4;
}

.picker-ch-code  { width: 90px; }
.picker-ch-price { width: 90px; }

#itemPickerModal .picker-table tbody tr {
  border-left: 3px solid transparent;
  transition: background-color 0.1s, border-color 0.1s;
  cursor: pointer;
}

#itemPickerModal .picker-table tbody tr:hover {
  background-color: rgba(0,120,212,0.06);
}

#itemPickerModal .picker-table tbody tr.picker-selected {
  background-color: rgba(0,120,212,0.12);
  border-left-color: #0078d4;
}

#itemPickerModal .picker-table td:first-child {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.73rem;
  color: #605e5c;
}

#itemPickerModal .picker-table td:last-child {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.78rem;
  color: #0078d4;
}

#itemPickerModal .picker-table td[colspan] {
  text-align: center;
  padding: 48px 20px;
  color: #94a3b8 !important;
}

/* Pagination strip */
.picker-pagination {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 8px 16px;
  border-top: 1px solid #e0e0e0;
}

.picker-pagination .page-btn {
  min-width: 28px;
  height: 28px;
  padding: 0 6px;
  font-size: 0.78rem;
  border: 1px solid #e0e0e0;
  background: #fff;
  color: #323130;
  border-radius: 2px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background 0.1s, border-color 0.1s;
}

.picker-pagination .page-btn:hover:not(:disabled) {
  background: rgba(0,120,212,0.06);
  border-color: #0078d4;
  color: #0078d4;
}

.picker-pagination .page-btn.active {
  background: #0078d4;
  border-color: #0078d4;
  color: #fff;
}

.picker-pagination .page-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

/* Footer */
.picker-foot {
  background: #f3f3f3;
  border-top: 1px solid #e0e0e0;
  padding: 10px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.picker-count {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.70rem;
  color: #605e5c;
}

#picker-select-btn {
  background-color: #0078d4 !important;
  border-color: #0078d4 !important;
  color: #fff !important;
}

#picker-select-btn:hover:not(:disabled) {
  background-color: #106ebe !important;
  border-color: #106ebe !important;
}

#picker-select-btn:disabled { opacity: 0.4; }
```

- [ ] **Step 2: Verify CSS compiles (no syntax error)**

Open any invoice/quotation/sale order create/edit page in the browser. Check DevTools console for CSS errors. The picker section should show no red underlines in DevTools Sources.

---

## Task 2: HTML — Rewrite item picker modal template

**Files:**
- Modify: `templates/invoices/partials/item_picker_modal.html`

- [ ] **Step 1: Replace the entire template**

```html
{% load i18n %}
<div class="modal fade"
     id="itemPickerModal"
     tabindex="-1"
     aria-labelledby="itemPickerModalLabel"
     aria-hidden="true">

  <div class="modal-dialog picker-dialog">
    <div class="modal-content picker-content">

      <div class="picker-head d-flex align-items-center justify-content-between">
        <h6 class="picker-title mb-0" id="itemPickerModalLabel">
          {% trans "Catálogo de artículos" %}
        </h6>
        <button type="button" class="btn-close" data-bs-dismiss="modal"
                aria-label="{% trans 'Cerrar' %}"></button>
      </div>

      <div class="picker-search-area">
        <div class="input-group input-group-sm">
          <span class="input-group-text bg-transparent border-end-0">
            <i class="bi bi-search" style="font-size:0.85rem"></i>
          </span>
          <input type="text"
                 id="picker-search"
                 class="form-control border-start-0 ps-1 picker-search-input"
                 placeholder="{% trans 'Buscar por nombre o código…' %}"
                 autocomplete="off">
        </div>
      </div>

      <div class="picker-list-wrap">
        <table class="table table-sm picker-table mb-0">
          <thead class="table-light">
            <tr>
              <th class="picker-ch-code" data-sort="code">
                {% trans "Código" %}
                <i class="bi bi-arrow-down-up picker-sort-icon"></i>
              </th>
              <th data-sort="name">
                {% trans "Artículo" %}
                <i class="bi bi-arrow-down-up picker-sort-icon"></i>
              </th>
              <th class="text-end picker-ch-price" data-sort="unit_price">
                {% trans "Precio" %}
                <i class="bi bi-arrow-down-up picker-sort-icon"></i>
              </th>
            </tr>
          </thead>
          <tbody id="picker-tbody"></tbody>
        </table>
      </div>

      <div id="picker-pagination" class="picker-pagination d-none"></div>

      <div class="picker-foot">
        <span class="picker-count" id="picker-count"></span>
        <div class="d-flex gap-2">
          <button type="button" class="btn btn-sm btn-outline-secondary"
                  data-bs-dismiss="modal">
            {% trans "Cancelar" %}
          </button>
          <button type="button"
                  class="btn btn-sm"
                  id="picker-select-btn"
                  disabled>
            <i class="bi bi-check-lg me-1"></i>{% trans "Seleccionar" %}
          </button>
        </div>
      </div>

    </div>
  </div>
</div>
```

- [ ] **Step 2: Verify modal renders**

Open an invoice create/edit page. Click the item picker button on any row. Confirm:
- Gray header band with title "Catálogo de artículos" and close X
- No left blue accent border on modal
- Search input visible
- Table columns: Código · Artículo · Precio with sort chevron icons
- "Cancelar" and "Seleccionar" buttons in footer (Seleccionar disabled)

---

## Task 3: JS — Extend picker object and add helper functions

**Files:**
- Modify: `static/js/app.js`

- [ ] **Step 1: Extend the `picker` object (line 360)**

Change:
```js
var picker = { selectedPk: null };
```
To:
```js
var picker = { selectedPk: null, sortKey: "name", sortDir: "asc", page: 1 };
```

- [ ] **Step 2: Add three helper functions after `pickerSelect` (after line ~414)**

Insert immediately after the closing `}` of `pickerSelect`:

```js
function pickerRenderPagination(totalPages) {
  var container = document.getElementById("picker-pagination");
  if (!container) return;
  if (totalPages <= 1) {
    container.classList.add("d-none");
    container.innerHTML = "";
    return;
  }
  container.classList.remove("d-none");
  var html = '<button class="page-btn" ' + (picker.page <= 1 ? "disabled" : "") +
    ' onclick="pickerGoPage(' + (picker.page - 1) + ')">&#8249;</button>';
  for (var i = 1; i <= totalPages; i++) {
    html += '<button class="page-btn' + (i === picker.page ? " active" : "") +
      '" onclick="pickerGoPage(' + i + ')">' + i + "</button>";
  }
  html += '<button class="page-btn" ' + (picker.page >= totalPages ? "disabled" : "") +
    ' onclick="pickerGoPage(' + (picker.page + 1) + ')">&#8250;</button>';
  container.innerHTML = html;
}

function pickerGoPage(n) {
  picker.page = n;
  var searchEl = document.getElementById("picker-search");
  pickerRender(searchEl ? searchEl.value : "");
}

function pickerUpdateSortHeaders() {
  var ths = document.querySelectorAll("#itemPickerModal .picker-table thead th[data-sort]");
  ths.forEach(function (th) {
    var key = th.getAttribute("data-sort");
    var icon = th.querySelector(".picker-sort-icon");
    th.classList.remove("picker-sort-active");
    if (icon) {
      icon.className = "bi bi-arrow-down-up picker-sort-icon";
    }
    if (key === picker.sortKey) {
      th.classList.add("picker-sort-active");
      if (icon) {
        icon.className = "bi bi-sort-" + (picker.sortDir === "asc" ? "up" : "down") +
          "-alt picker-sort-icon";
      }
    }
  });
}
```

- [ ] **Step 3: Expose `pickerGoPage` globally**

In the window globals block (the section with `window.dtSort`, `window.dtPage`, etc.), add:
```js
window.pickerGoPage = pickerGoPage;
```

---

## Task 4: JS — Rewrite `pickerRender()`

**Files:**
- Modify: `static/js/app.js` (lines 362–406)

- [ ] **Step 1: Replace the entire `pickerRender` function**

Find `function pickerRender(query) {` through its closing `}` and replace with:

```js
function pickerRender(query) {
  var catalog = window.ITEM_CATALOG || [];
  var q = (query || "").toLowerCase().trim();
  var filtered = q ? catalog.filter(function (i) {
    return (i.name || "").toLowerCase().includes(q) ||
           (i.code || "").toLowerCase().includes(q);
  }) : catalog;

  // Sort
  var key = picker.sortKey;
  var dir = picker.sortDir;
  filtered = filtered.slice().sort(function (a, b) {
    var av, bv;
    if (key === "unit_price") {
      av = parseFloat(a[key]) || 0;
      bv = parseFloat(b[key]) || 0;
    } else {
      av = (a[key] || "").toString().toLowerCase();
      bv = (b[key] || "").toString().toLowerCase();
    }
    if (av < bv) return dir === "asc" ? -1 : 1;
    if (av > bv) return dir === "asc" ? 1 : -1;
    return 0;
  });

  // Paginate
  var pageSize = 20;
  var totalPages = Math.ceil(filtered.length / pageSize) || 1;
  if (picker.page > totalPages) picker.page = Math.max(1, totalPages);
  var start = (picker.page - 1) * pageSize;
  var pageItems = filtered.slice(start, start + pageSize);

  var tbody = document.getElementById("picker-tbody");
  var countEl = document.getElementById("picker-count");
  var selBtn = document.getElementById("picker-select-btn");
  if (!tbody) return;

  tbody.innerHTML = "";
  picker.selectedPk = null;
  if (selBtn) selBtn.disabled = true;

  if (filtered.length === 0) {
    var empty = document.createElement("tr");
    var emptyTd = document.createElement("td");
    emptyTd.colSpan = 3;
    emptyTd.className = "text-center text-muted py-4";
    emptyTd.innerHTML = '<i class="bi bi-inbox me-1"></i>' +
      getConfig("itemPickerEmpty", "No se encontraron artículos.");
    empty.appendChild(emptyTd);
    tbody.appendChild(empty);
  } else {
    pageItems.forEach(function (item) {
      var tr = document.createElement("tr");
      tr.innerHTML =
        '<td class="small font-monospace">' + escapeHtml(item.code || "-") + "</td>" +
        '<td><span class="fw-semibold">' + escapeHtml(item.name || "") + "</span></td>" +
        '<td class="text-end">' + formatMoney(item.unit_price) + "</td>";
      tr.addEventListener("click", function () {
        tbody.querySelectorAll("tr").forEach(function (r) {
          r.classList.remove("picker-selected");
        });
        tr.classList.add("picker-selected");
        picker.selectedPk = item.pk;
        if (selBtn) selBtn.disabled = false;
      });
      tr.addEventListener("dblclick", function () { pickerSelect(item.pk); });
      tbody.appendChild(tr);
    });
  }

  if (countEl) {
    if (filtered.length === 0) {
      countEl.textContent = "0 artículos";
    } else {
      var endIdx = Math.min(start + pageSize, filtered.length);
      countEl.textContent = (start + 1) + "–" + endIdx + " de " + filtered.length + " artículo(s)";
    }
  }

  pickerRenderPagination(totalPages);
  pickerUpdateSortHeaders();
}
```

- [ ] **Step 2: Verify pickerRender works**

Open invoice create page. Open item picker. Confirm:
- Items render in table (sorted by name ascending by default)
- Count shows "1–20 de X artículo(s)" if more than 20 items, otherwise "1–N de N artículo(s)"
- Pagination strip appears below table only if more than 20 items
- Clicking a row highlights it with blue left border + light blue bg
- Double-click selects and closes modal

---

## Task 5: JS — Update `initInvoiceItemFormset()`

**Files:**
- Modify: `static/js/app.js` (lines 523–538)

- [ ] **Step 1: Replace the picker setup block inside `initInvoiceItemFormset`**

Find this block (starting at `var pickerModal = document.getElementById...` through the end of `initInvoiceItemFormset`):

```js
    var pickerModal = document.getElementById("itemPickerModal");
    var pickerSearch = document.getElementById("picker-search");
    var pickerSelBtn = document.getElementById("picker-select-btn");
    if (pickerSearch) pickerSearch.addEventListener("input", function () { pickerRender(this.value); });
    if (pickerSelBtn) pickerSelBtn.addEventListener("click", function () { pickerSelect(picker.selectedPk); });
    if (pickerModal) {
      pickerModal.addEventListener("shown.bs.modal", function () {
        pickerRender("");
        if (pickerSearch) {
          pickerSearch.value = "";
          pickerSearch.focus();
        }
      });
      pickerModal.addEventListener("hidden.bs.modal", function () { picker.selectedPk = null; });
    }
  }
```

Replace with:

```js
    var pickerModal = document.getElementById("itemPickerModal");
    var pickerSearch = document.getElementById("picker-search");
    var pickerSelBtn = document.getElementById("picker-select-btn");

    if (pickerSearch) {
      pickerSearch.addEventListener("input", function () {
        picker.page = 1;
        pickerRender(this.value);
      });
    }

    if (pickerSelBtn) {
      pickerSelBtn.addEventListener("click", function () { pickerSelect(picker.selectedPk); });
    }

    var pickerThead = document.querySelector("#itemPickerModal .picker-table thead");
    if (pickerThead) {
      pickerThead.addEventListener("click", function (e) {
        var th = e.target.closest("th[data-sort]");
        if (!th) return;
        var key = th.getAttribute("data-sort");
        if (picker.sortKey === key) {
          picker.sortDir = picker.sortDir === "asc" ? "desc" : "asc";
        } else {
          picker.sortKey = key;
          picker.sortDir = "asc";
        }
        picker.page = 1;
        pickerRender(pickerSearch ? pickerSearch.value : "");
      });
    }

    if (pickerModal) {
      pickerModal.addEventListener("shown.bs.modal", function () {
        picker.page = 1;
        pickerRender("");
        if (pickerSearch) {
          pickerSearch.value = "";
          pickerSearch.focus();
        }
      });
      pickerModal.addEventListener("hidden.bs.modal", function () {
        picker.selectedPk = null;
      });
    }
  }
```

- [ ] **Step 2: Verify sort behavior**

Open item picker. Click "Código" header:
- Items re-sort by code ascending. Chevron on Código column becomes `bi-sort-up-alt` (active, blue).

Click "Código" again:
- Items re-sort by code descending. Chevron becomes `bi-sort-down-alt`.

Click "Precio" header:
- Items re-sort by price ascending. Precio column shows active sort icon. Código returns to inactive.

- [ ] **Step 3: Verify pagination navigation**

If catalog has >20 items: pagination strip shows `‹ 1 2 … ›`. Click page 2 → shows items 21–40, count updates. Click `‹` → returns to page 1. Search → resets to page 1.

- [ ] **Step 4: Verify cross-document consistency**

Open picker on a quotation edit page. Repeat verify steps — same behavior, same visual. Open on sale order edit page — same.

---

## Task 6: Final verification and commit

- [ ] **Step 1: Full end-to-end test on invoice edit**

1. Open any invoice in edit mode
2. Click item picker button on a line item
3. Modal opens with D365 gray header — no left accent border, clean white body
4. Type partial name → filtered, count updates, page resets to 1
5. Click column header → sort toggles, icon updates
6. If >20 items: navigate pages
7. Click a row → Seleccionar button enables
8. Click Seleccionar → modal closes, line item fields populate correctly
9. Repeat double-click flow: open, double-click row → closes and populates

- [ ] **Step 2: Commit**

```bash
git add templates/invoices/partials/item_picker_modal.html \
        static/css/app.css \
        static/js/app.js
git commit -m "feat: redesign item picker modal to D365 compact lookup style

- D365 gray header band, clean 1px border, no left accent
- Sortable column headers (code, name, price) with chevron indicators
- Client-side pagination (20/page) with prev/next controls
- Count display shows range and total (1–20 de 48 artículo(s))
- D365 blue #0078d4 accent for selection, focus, active sort"
```
