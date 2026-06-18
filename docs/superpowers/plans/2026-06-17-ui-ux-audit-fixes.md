# UI/UX Audit Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 29 findings from `docs/ui-ux-audit-2026-06.md` to raise the impeccable audit score from 10/20 to ≥16/20.

**Architecture:** Pure front-end changes — CSS, Django templates, one JS refactor, one Python view change. No migrations. No model changes. All changes are additive-or-replacement on existing files. Organized in 8 phases from safest (CSS tokens) to most structural (auth panel, invoice action bar). Each phase is independently shippable.

**Tech Stack:** Django 5.2 templates, Bootstrap 5.3, HTMX, Alpine.js, vanilla CSS (no preprocessors), IBM Plex Mono / Manrope / Cormorant Garamond

**Audit report:** `docs/ui-ux-audit-2026-06.md`

---

## File Map

### Phase A — CSS token/contrast fixes
- Modify: `static/css/components.css` (lines 101, 312, 609, 617–639, 1037, 1057)
- Modify: `static/css/documents.css` (lines 121, 269, 306, 365, 369, 391, 481, 559, 672)
- Modify: `static/css/shell.css` (lines 72–79)
- Modify: `static/css/app.css` (line ~28 — #main-content)
- Modify: `static/css/dashboard.css` (lines 10, 118, 328)

### Phase B — Broken sticky bars + deprecated includes
- Modify: `templates/sales/customer_form.html:152`
- Modify: `templates/sales/payment_term_form.html:33`
- Modify: `templates/purchases/supplier_form.html:145`
- Modify: `templates/items/item_form.html:39`
- Modify: 20+ templates (full list in `templates/components/app_styles.html` deprecation comment)
- Delete: `templates/components/app_styles.html`

### Phase C — Anti-pattern: side-stripe borders
- Modify: `static/css/components.css` (db-kpi variants, db-empty-state, kv-note)
- Modify: `static/css/dashboard.css` (db-panel-overdue, db-cash-net, db-cash-risk border)
- Modify: `static/css/documents.css` (doc-paper, dt-row-selected)

### Phase D — Animation performance
- Modify: `static/css/documents.css` (doc-notes-panel, doc-ribbon-body)

### Phase E — JS selective loading
- Modify: `templates/base.html` (remove 8 scripts)
- Modify: `templates/sales/invoice_form.html`, `quotation_form.html`, `sale_order_form.html`, `credit_note_form.html`, `payment_form.html`
- Modify: `templates/purchases/purchase_order_form.html`, `supplier_invoice_form.html`, `supplier_payment_create.html`
- Modify: `templates/accounts/dashboard.html`
- Modify: `templates/components/datatable/wrapper.html` (or each list template that uses the datatable)

### Phase F — Accessibility: touch targets + ARIA
- Modify: `static/css/documents.css` (ribbon button padding)
- Modify: `static/css/shell.css` (subnav height)
- Modify: `templates/partials/_navbar.html` (aria-expanded on toggle)
- Modify: `templates/partials/_sidebar.html` (backdrop div → button)
- Modify: `static/js/shell.js` (toggle aria-expanded on sidebar open/close)

### Phase G — Template content fixes
- Modify: `templates/sales/invoice_detail.html` (ITBIS badge, inline styles, action bar)
- Modify: `templates/sales/invoice_form.html` (remove inline width:360px)
- Modify: `templates/sales/customer_form.html` (smart buttons → db-kpi, inline styles)
- Modify: `templates/partials/_sidebar.html` (remove Próximamente section)

### Phase H — Structural improvements
- Modify: `static/css/documents.css` (eyebrow hierarchy, app-card-head)
- Modify: `static/css/dashboard.css` (app-card-head)
- Modify: `apps/accounts/views.py` (DashboardView — pass breadcrumbs)
- Modify: `templates/base_anon.html` (add left branding panel)

---

## Phase A — Foundation: CSS Token & Contrast Fixes

*No template changes. No behavior changes. Pure CSS. Zero risk of breaking functionality.*

---

### Task 1: Deduplicate `--warn` token and `num-warn` rule

**Files:**
- Modify: `static/css/components.css:101` (remove duplicate `--warn`)
- Modify: `static/css/components.css:312` (remove duplicate `num-warn`)

**Context:** `--warn` is defined at line 101 as `#d97706` and again at line 1037 as `#b45309`. The second always wins (CSS cascade). `.num-warn` is defined twice at lines 312 and 1057. Remove the first instances.

- [ ] **Step 1: Remove first `--warn` definition**

In `static/css/components.css`, find the `:root` block around line 89–107:
```css
:root {
  --brand-ink: #1e2130;
  --brand-ink-2: #2a3050;
  --brand-accent: #3f6fd6;
  --brand-soft: #eef3fc;
  --pos: #16a34a;
  --neg: #b42318;
  --warn: #d97706;   /* ← DELETE THIS LINE */
  --muted: #6b7280;
  --muted-2: #9ca3af;
  --hairline: #e5e7eb;
  --hairline-soft: #eef0f6;
}
```

Delete the `--warn: #d97706;` line only.

- [ ] **Step 2: Remove first `num-warn` rule**

Around line 309–313 in `static/css/components.css`:
```css
.num-warn {
  color: var(--warn) !important;
}
```

Delete this entire rule block (3 lines). The identical rule at line ~1057 (inside the KV-card section) stays.

- [ ] **Step 3: Verify — run the dev server and spot-check**

```bash
python manage.py runserver
```

Open any page that shows aging/overdue amounts (Dashboard → Cartera por antigüedad, or any AR aging report). The `num-warn` text color should still be amber. If it disappeared, you removed the wrong block.

- [ ] **Step 4: Commit**

```bash
git add static/css/components.css
git commit -m "fix(css): deduplicate --warn token and num-warn rule"
```

---

### Task 2: Fix `#94a3b8` contrast failures on white backgrounds

**Files:**
- Modify: `static/css/documents.css` (7 occurrences)
- Modify: `static/css/dashboard.css` (line ~24)
- Modify: `static/css/app.css` (`.settings-secondary-link i`)

**Context:** `#94a3b8` on white = 2.8:1 contrast (WCAG AA requires 4.5:1 for text). Must become `#6b7280` (4.6:1) for any text that users actively read.

- [ ] **Step 1: Replace in `static/css/documents.css`**

Find and replace ALL instances of `color: #94a3b8` in `documents.css`. There are 7 occurrences. Run a targeted replace:

```css
/* Lines to change (doc-type-eyebrow, doc-stamp-draft, doc-meta-label,
   doc-status-card-header, doc-notes-label, doc-items-table th, module-eyebrow): */

/* BEFORE (example): */
.doc-type-eyebrow { color: #94a3b8; }
.doc-stamp-draft { color: #94a3b8; }
.doc-meta-label { color: #94a3b8; }
.doc-status-card-header { color: #94a3b8; }
.doc-notes-label { color: #94a3b8; }
.doc-items-table .table th { color: #94a3b8; }
.module-eyebrow { color: var(--module-accent); }  /* this one is fine, skip */

/* AFTER — change ALL #94a3b8 to #6b7280: */
.doc-type-eyebrow { color: #6b7280; }
.doc-stamp-draft { color: #6b7280; }
.doc-meta-label { color: #6b7280; }
.doc-status-card-header { color: #6b7280; }
.doc-notes-label { color: #6b7280; }
.doc-items-table .table th { color: #6b7280; }
```

Use your editor's "Replace All in file" for `documents.css`:
- Find: `color: #94a3b8`
- Replace: `color: #6b7280`
- (This replaces all 7 matching lines at once)

- [ ] **Step 2: Replace in `static/css/dashboard.css`**

Around line 24 in `dashboard.css`:
```css
/* BEFORE: */
.db-section-label {
  color: #9ca3af;    /* ← change this */
}

/* AFTER: */
.db-section-label {
  color: #6b7280;
}
```

Also around line 118:
```css
/* BEFORE: */
.db-panel-sub {
  ...
  color: #9ca3af;   /* ← change this */
}

/* AFTER: */
.db-panel-sub {
  color: #6b7280;
}
```

- [ ] **Step 3: Fix auth card subtitle in `templates/base_anon.html`**

The auth card sub text uses `color: #94a3b8` inline in the `<style>` block:

```css
/* BEFORE (in base_anon.html <style> block): */
.auth-card-sub {
  font-size: 0.8rem;
  color: #94a3b8;       /* ← change */
  margin: 0 0 24px;
}
.auth-page-footer {
  ...
  color: #94a3b8;       /* ← change */
}

/* AFTER: */
.auth-card-sub {
  font-size: 0.8rem;
  color: #6b7280;
  margin: 0 0 24px;
}
.auth-page-footer {
  ...
  color: #6b7280;
}
```

- [ ] **Step 4: Verify**

Open the invoice detail page. The document meta labels (Fecha de emisión, Vencimiento, etc.) should still be muted/secondary but readable. Open the login page — the subtitle text and footer should be readable without squinting.

- [ ] **Step 5: Commit**

```bash
git add static/css/documents.css static/css/dashboard.css templates/base_anon.html
git commit -m "fix(a11y): raise muted text contrast from #94a3b8 to #6b7280 (WCAG AA)"
```

---

### Task 3: Fix sidebar section label contrast on dark background

**Files:**
- Modify: `static/css/shell.css:76`

**Context:** `.sidebar-section-label { color: #5c6480 }` on `background: #1e2130` = ~2.9:1 (fails AA). Needs `#8892b0` (~4.5:1 on `#1e2130`).

- [ ] **Step 1: Edit `static/css/shell.css`**

Find the `.sidebar-section-label` rule (around line 72–79):
```css
/* BEFORE: */
.sidebar-section-label {
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #5c6480;           /* ← change this */
  padding: 18px 20px 6px;
  white-space: nowrap;
}

/* AFTER: */
.sidebar-section-label {
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #8892b0;           /* was #5c6480 — now ~4.5:1 on #1e2130 */
  padding: 18px 20px 6px;
  white-space: nowrap;
}
```

- [ ] **Step 2: Verify**

Open the app while logged in. The sidebar section labels ("FACTURACIÓN", "COMPRAS", "ORGANIZACIÓN") should be noticeably more readable on the dark background.

- [ ] **Step 3: Commit**

```bash
git add static/css/shell.css
git commit -m "fix(a11y): raise sidebar section label contrast to 4.5:1 on dark bg"
```

---

### Task 4: Raise typography floor — eliminate 9px micro-labels

**Files:**
- Modify: `static/css/components.css` (`.app-filter-label`, `.app-metric-label`)
- Modify: `static/css/documents.css` (`.doc-type-eyebrow`, `.doc-meta-label`, `.doc-notes-label`, `.doc-status-card-header`, `.module-eyebrow`)

**Context:** Several labels are set to `9px` or `0.6rem` (≈9.6px). Minimum readable floor is `0.6875rem` (11px) for all text that carries information.

- [ ] **Step 1: Fix in `static/css/components.css`**

```css
/* BEFORE: */
.app-filter-label {
  font-size: 9px;
}

.app-metric-label {
  font-size: 9px;
}

/* AFTER: */
.app-filter-label {
  font-size: 0.6875rem;   /* 11px — was 9px */
}

.app-metric-label {
  font-size: 0.6875rem;   /* 11px — was 9px */
}
```

- [ ] **Step 2: Fix in `static/css/documents.css`**

```css
/* BEFORE (multiple locations): */
.doc-type-eyebrow    { font-size: 0.6rem; }
.doc-status-card-header { font-size: 0.6rem; }
.doc-notes-label     { font-size: 0.6rem; }
.module-eyebrow      { font-size: 0.6rem; }

/* AFTER: */
.doc-type-eyebrow    { font-size: 0.6875rem; }
.doc-status-card-header { font-size: 0.6875rem; }
.doc-notes-label     { font-size: 0.6875rem; }
.module-eyebrow      { font-size: 0.6875rem; }
```

For `.doc-meta-label { font-size: 0.62rem }` → change to `0.6875rem`.

Do NOT change `.db-kpi-label` (0.64rem/800 weight — small but readable at that weight level, and it's KPI-only), `.app-card-head` (0.7rem — already acceptable), or `.kv-card-title` (0.82rem — fine).

- [ ] **Step 3: Verify**

Open an invoice detail page and a purchase order detail page. All field labels should remain compact but not require squinting. The eyebrow labels above document sections should be the size of a small label, not microscopic.

- [ ] **Step 4: Commit**

```bash
git add static/css/components.css static/css/documents.css
git commit -m "fix(a11y): raise typography floor to 11px minimum for all informational labels"
```

---

### Task 5: Add Safari momentum scrolling to main content area

**Files:**
- Modify: `static/css/app.css` (the `#main-content` rule)

**Context:** `html, body { overflow: hidden }` is required for the fixed sidebar shell. But this means `#main-content` handles all scrolling. Safari iOS requires `-webkit-overflow-scrolling: touch` on non-body scrollers for momentum (inertial) scrolling.

- [ ] **Step 1: Edit `static/css/app.css`**

Find the `#main-content` rule in `shell.css` (not `app.css` — it's actually in `shell.css` around line 328):
```css
/* BEFORE (static/css/shell.css, ~line 328): */
#main-content {
  flex: 1;
  overflow-y: auto;
  padding: 28px 28px;
}

/* AFTER: */
#main-content {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;   /* Safari iOS momentum scroll */
  padding: 28px 28px;
}
```

- [ ] **Step 2: Verify**

If you have an iOS device or Safari on macOS, open the app and scroll a long page (invoice list, report). Scrolling should feel smooth with natural deceleration. On other browsers this property is ignored.

- [ ] **Step 3: Commit**

```bash
git add static/css/shell.css
git commit -m "fix(perf): add -webkit-overflow-scrolling:touch for Safari iOS momentum scroll"
```

---

## Phase B — Broken Functionality: Sticky Bars + Deprecated Includes

---

### Task 6: Fix sticky save bar class mismatch (4 templates)

**Files:**
- Modify: `templates/sales/customer_form.html:152`
- Modify: `templates/sales/payment_term_form.html:33`
- Modify: `templates/purchases/supplier_form.html:145`
- Modify: `templates/items/item_form.html:39`

**Context:** CSS in `components.css:951` defines `.app-form-bar` with `position: sticky; bottom: 0`. Four templates use `.form-sticky-bar` (a class that has no CSS). The save button is NOT sticky on these pages. This is a broken UX feature — users must scroll to the bottom of long forms to save.

- [ ] **Step 1: Fix `templates/sales/customer_form.html`**

Find around line 152 (the save bar at the end of the form):
```html
<!-- BEFORE: -->
  <div class="form-sticky-bar">
    <button type="submit" class="btn btn-sm btn-brand">
      <i class="bi bi-floppy me-1"></i>{% trans "Guardar" %}
    </button>
    <a href="{% url 'sales:customer_list' %}" class="btn btn-outline-secondary btn-sm">
      {% trans "Cancelar" %}
    </a>
  </div>

<!-- AFTER: -->
  <div class="app-form-bar">
    <button type="submit" class="btn btn-sm btn-brand">
      <i class="bi bi-floppy me-1"></i>{% trans "Guardar" %}
    </button>
    <a href="{% url 'sales:customer_list' %}" class="btn btn-outline-secondary btn-sm">
      {% trans "Cancelar" %}
    </a>
  </div>
```

- [ ] **Step 2: Fix `templates/sales/payment_term_form.html`**

Find around line 33:
```html
<!-- BEFORE: -->
      <div class="form-sticky-bar">

<!-- AFTER: -->
      <div class="app-form-bar">
```

- [ ] **Step 3: Fix `templates/purchases/supplier_form.html`**

Find around line 145:
```html
<!-- BEFORE: -->
  <div class="form-sticky-bar">

<!-- AFTER: -->
  <div class="app-form-bar">
```

- [ ] **Step 4: Fix `templates/items/item_form.html`**

Find around line 39:
```html
<!-- BEFORE: -->
      <div class="form-sticky-bar">

<!-- AFTER: -->
      <div class="app-form-bar">
```

- [ ] **Step 5: Verify**

Open each of these 4 pages in the browser. The save/cancel button bar should now stick to the bottom of the viewport when the form is taller than the viewport. Scroll past the bottom of the form fields — the bar should remain visible.

Pages to test:
1. `/sales/customers/new/` — Nuevo cliente
2. `/sales/payment-terms/` → edit any term
3. `/purchases/suppliers/new/` — Nuevo proveedor
4. `/items/new/` — Nuevo artículo

- [ ] **Step 6: Commit**

```bash
git add templates/sales/customer_form.html templates/sales/payment_term_form.html \
        templates/purchases/supplier_form.html templates/items/item_form.html
git commit -m "fix(ux): fix sticky save bar class (form-sticky-bar → app-form-bar) on 4 forms"
```

---

### Task 7: Remove deprecated `app_styles.html` includes

**Files:**
- Modify: Every template listed in the deprecation comment in `templates/components/app_styles.html`

**Context:** `templates/components/app_styles.html` is intentionally empty with a deprecation comment listing all templates that still include it. Every include adds an HTTP request for a no-op file.

- [ ] **Step 1: Get the complete list of files to edit**

```bash
grep -rl 'app_styles.html' templates/
```

This will output the complete list of template files. Expected output (approximately):
```
templates/accounts/dashboard.html
templates/accounts/create_org.html
templates/accounts/members.html
templates/accounts/org_settings.html
templates/accounts/team_form.html
templates/accounts/teams.html
templates/accounts/profile.html
templates/core/module_detail.html
templates/core/module_form.html
templates/core/module_list.html
templates/items/item_detail.html
templates/items/item_form.html
templates/items/item_list.html
... (purchases/* and sales/*)
```

- [ ] **Step 2: Remove the include from every file**

For each file in the list, remove the line:
```django
{% include "components/app_styles.html" %}
```

This line appears verbatim in each file. Use your editor's "Replace in Files" feature:
- Search in: `templates/`
- Find: `{% include "components/app_styles.html" %}`
- Replace: *(empty string)*
- Replace All

Or run from the project root:
```bash
# Preview what would change first:
grep -rn 'include "components/app_styles.html"' templates/

# Then remove (Unix/Git Bash):
grep -rl 'include "components/app_styles.html"' templates/ | \
  xargs sed -i 's/{% include "components\/app_styles.html" %}//g'
```

- [ ] **Step 3: Verify no regressions**

```bash
python manage.py runserver
```

Open 5-6 different pages (dashboard, invoice list, customer list, item list, purchase order list). All should render identically to before — the included file was empty, so no visual changes expected.

- [ ] **Step 4: Commit**

```bash
git add templates/
git commit -m "refactor(templates): remove deprecated app_styles.html includes from all templates"
```

---

### Task 8: Delete `app_styles.html`

**Files:**
- Delete: `templates/components/app_styles.html`

- [ ] **Step 1: Delete the file**

```bash
git rm templates/components/app_styles.html
```

- [ ] **Step 2: Verify no 500 errors**

```bash
python manage.py runserver
```

Open 3-4 pages. If any template still includes `app_styles.html`, Django will throw a TemplateDoesNotExist error. If you see a 500, run `grep -rn 'app_styles' templates/` to find the remaining include.

- [ ] **Step 3: Commit**

```bash
git commit -m "refactor(templates): delete deprecated app_styles.html (was empty no-op)"
```

---

## Phase C — Anti-Patterns: Replace Side-Stripe Borders

*The most impactful visual change. Every `border-left: N px` accent on a card/callout/panel becomes a top-border or background tint. The `border-left: 1px solid var(--hairline-soft)` dividers in `.db-cash-side` are exempt — those are structural separators, not accents.*

---

### Task 9: Replace KPI card side-stripes → top-border + subtle tint

**Files:**
- Modify: `static/css/components.css` (`.db-kpi` and its variant rules)

**Context:** `.db-kpi { border-left: 3px solid #9ca3af }` with colored overrides per variant. The left stripe provides module color but signals nothing because every card has one. Replace with a colored top border + subtle matching gradient on the background.

- [ ] **Step 1: Replace the `.db-kpi` base border**

Find the `.db-kpi` rule (around line 316 in `components.css`):
```css
/* BEFORE: */
.db-kpi {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 100%;
  min-height: 74px;
  padding: 12px 14px;
  border: 1px solid #e5e7eb;
  border-left: 3px solid #9ca3af;   /* ← REMOVE this line */
  border-radius: 8px;
  background: #fff;
  ...
}

/* AFTER: */
.db-kpi {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 100%;
  min-height: 74px;
  padding: 12px 14px;
  border: 1px solid #e5e7eb;
  border-top: 3px solid #9ca3af;    /* changed: border-left → border-top */
  border-radius: 8px;
  background: #fff;
  ...
}
```

- [ ] **Step 2: Update the variant rules**

Find the `.db-kpi.is-ar`, `.db-kpi.is-ap`, etc. rules and update them:

```css
/* BEFORE: */
.db-kpi.is-ar { border-left-color: #3f6fd6; }
.db-kpi.is-ap { border-left-color: #d97706; }
.db-kpi.is-neg { border-left-color: #b42318; }
.db-kpi.is-pos { border-left-color: #16a34a; }
.db-kpi.is-net { border-left-color: #1e2130; }

/* AFTER: */
.db-kpi.is-ar  { border-top-color: #3f6fd6; }
.db-kpi.is-ap  { border-top-color: #d97706; }
.db-kpi.is-neg { border-top-color: #b42318; }
.db-kpi.is-pos { border-top-color: #16a34a; }
.db-kpi.is-net { border-top-color: #1e2130; }
```

Leave all `.db-kpi-icon` background/color rules unchanged — those are the icon tint and stay.

- [ ] **Step 3: Verify**

Open the dashboard and any list page (invoice list, customer list). KPI cards should now have a colored bar across the top instead of the left. Icons and values should be unchanged.

- [ ] **Step 4: Commit**

```bash
git add static/css/components.css
git commit -m "fix(design): replace db-kpi side-stripe border-left with border-top accent"
```

---

### Task 10: Replace side-stripes on dashboard panels, empty state, cash band

**Files:**
- Modify: `static/css/dashboard.css`
- Modify: `static/css/components.css` (`.db-empty-state`)

- [ ] **Step 1: Fix `.db-panel-overdue` in `dashboard.css`**

```css
/* BEFORE: */
.db-panel-overdue {
  border-left: 3px solid #dc2626;
}
.db-panel-overdue .db-panel-title {
  color: #dc2626;
}

/* AFTER: */
.db-panel-overdue {
  border-top: 3px solid #dc2626;
}
.db-panel-overdue .db-panel-title {
  color: #dc2626;
}
```

- [ ] **Step 2: Fix `.db-cash-net` in `dashboard.css`**

```css
/* BEFORE: */
.db-cash-net {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 300px;
  padding: 18px 22px;
  border-left: 4px solid var(--brand-ink);   /* ← change */
}

/* AFTER: */
.db-cash-net {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 300px;
  padding: 18px 22px;
  /* No border — the overall .db-cash card border is sufficient */
}
```

Also fix the mobile override referencing `border-left` for `.db-cash-net`:
```css
/* BEFORE (around line 412): */
@media (max-width: 991.98px) {
  .db-cash { flex-direction: column; }
  .db-cash-net,
  .db-cash-risk { min-width: 0; }
  .db-cash-net { border-left: 4px solid var(--brand-ink); border-bottom: 1px solid var(--hairline-soft); }
  .db-cash-risk { border-left: 0; border-top: 1px solid #f6d4d1; }
}

/* AFTER: */
@media (max-width: 991.98px) {
  .db-cash { flex-direction: column; }
  .db-cash-net,
  .db-cash-risk { min-width: 0; }
  .db-cash-net { border-bottom: 1px solid var(--hairline-soft); }  /* removed border-left */
  .db-cash-risk { border-top: 1px solid #f6d4d1; }                 /* removed border-left:0 */
}
```

- [ ] **Step 3: Fix `.db-empty-state` in `components.css`**

```css
/* BEFORE: */
.db-empty-state {
  min-height: 58px;
  padding: 14px 16px;
  border: 1px solid #dfe5ee;
  border-left: 3px solid #1e2130;   /* ← remove */
  border-radius: 8px;
  background: #f8fafc;
  color: #334155;
  font-size: .86rem;
}

/* AFTER: */
.db-empty-state {
  min-height: 58px;
  padding: 14px 16px;
  border: 1px solid #dfe5ee;
  border-radius: 8px;
  background: #f8fafc;
  color: #334155;
  font-size: .86rem;
}
```

- [ ] **Step 4: Verify**

Open the dashboard. The overdue panel should have a red top bar instead of left bar. The cash position net cell should have no special border. Empty states in tables should have a regular border instead of a left stripe.

- [ ] **Step 5: Commit**

```bash
git add static/css/dashboard.css static/css/components.css
git commit -m "fix(design): replace side-stripe border-left on dashboard panels and empty states"
```

---

### Task 11: Replace side-stripe on `.kv-note` callout

**Files:**
- Modify: `static/css/components.css` (`.kv-note`)

- [ ] **Step 1: Edit `.kv-note` rule**

```css
/* BEFORE (around line 1182–1190): */
.kv-note {
  margin: 6px 0 14px;
  padding: 10px 13px;
  background: #f8fafc;
  border: 1px solid var(--hairline-soft);
  border-left: 3px solid var(--brand-accent);   /* ← change */
  border-radius: 8px;
  font-size: .82rem;
  color: #475569;
}

/* AFTER — tinted background, no special left border: */
.kv-note {
  margin: 6px 0 14px;
  padding: 10px 13px;
  background: #eef3fc;                           /* brand-soft tint */
  border: 1px solid rgba(63, 111, 214, 0.20);   /* brand-accent at 20% */
  border-radius: 8px;
  font-size: .82rem;
  color: #475569;
}
```

- [ ] **Step 2: Verify**

Open an invoice detail that has notes (e.g., one with `notes` or `terms` filled in). The note callout should now show as a blue-tinted box with blue border, no left stripe.

- [ ] **Step 3: Commit**

```bash
git add static/css/components.css
git commit -m "fix(design): replace kv-note border-left stripe with tinted background"
```

---

### Task 12: Fix `doc-paper` and `dt-row-selected` border-left

**Files:**
- Modify: `static/css/documents.css`

- [ ] **Step 1: Fix `.module-page-title` border-left**

Around line 13 in `documents.css`:
```css
/* BEFORE: */
.module-page-title {
  border-left: 4px solid var(--module-accent);
  padding-left: 12px;
  line-height: 1.1;
}

/* AFTER: */
.module-page-title {
  /* No left border — use module accent on the heading text instead */
  line-height: 1.1;
}
.module-page-title h1 {
  color: #0f172a;    /* keep unchanged */
}
```

The `.module-eyebrow` color remains `var(--module-accent)` — that's accent on text (fine).

- [ ] **Step 2: Fix `.dt-row-selected` border-left**

Around line 591–596 in `documents.css`:
```css
/* BEFORE: */
tr.dt-row-selected > td:first-child {
  border-left: 3px solid var(--module-accent, #0078d4);
  padding-left: 9px; /* compensate 3px border: original is 12px, 12-3=9 */
}

/* AFTER — use background highlight only, no border: */
tr.dt-row-selected > td:first-child {
  /* border-left removed — the blue background (already applied via tr.dt-row-selected>td)
     is sufficient to communicate selection */
  padding-left: 12px;   /* restore normal padding */
}
```

- [ ] **Step 3: Verify**

Open any document list page that uses `.module-page-title` (currently the datatable list pages for sales). Select a row — it should highlight blue. The selected row's first cell should NOT have a colored left bar. Open a page with `.module-page-title` and verify it no longer has a left stripe.

- [ ] **Step 4: Commit**

```bash
git add static/css/documents.css
git commit -m "fix(design): remove remaining side-stripe border-left on module title and row selection"
```

---

## Phase D — Animation Performance

---

### Task 13: Replace `max-height` animation with `grid-template-rows`

**Files:**
- Modify: `static/css/documents.css` (`.doc-notes-panel` and `.doc-ribbon-body`)

**Context:** `max-height` transitions trigger layout recalculation on every frame. The correct technique (already used in `.doc-card-collapse`) is `grid-template-rows: 0fr → 1fr`. The JS that sets `.open` class on the accordion stays unchanged.

- [ ] **Step 1: Update `.doc-notes-panel` and `.doc-notes-acc`**

Find the rules around line 1099–1104 in `documents.css`:
```css
/* BEFORE: */
.doc-notes-panel { max-height: 0; overflow: hidden; transition: max-height .26s ease; }
.doc-notes-acc.open .doc-notes-panel { max-height: 320px; }
.doc-notes-panel-inner { padding: 0 15px 15px; }

/* AFTER: */
.doc-notes-panel {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows .26s cubic-bezier(.4, 0, .2, 1);
}
.doc-notes-acc.open .doc-notes-panel {
  grid-template-rows: 1fr;
}
.doc-notes-panel-inner {
  min-height: 0;      /* required for 0fr collapse to work */
  overflow: hidden;
  padding: 0 15px 15px;
}
```

Also add reduced motion override (add after the `.doc-notes-acc.open` rule):
```css
@media (prefers-reduced-motion: reduce) {
  .doc-notes-panel { transition: none; }
}
```

- [ ] **Step 2: Update `.doc-ribbon-body` and `.doc-notes-ribbon`**

Find the rules around line 1170–1175 in `documents.css`:
```css
/* BEFORE: */
.doc-ribbon-body { max-height: 0; overflow: hidden; transition: max-height .26s ease; }
.doc-notes-ribbon.open .doc-ribbon-body { max-height: 320px; }
.doc-ribbon-body-inner { padding: 11px 14px 14px; }

/* AFTER: */
.doc-ribbon-body {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows .26s cubic-bezier(.4, 0, .2, 1);
}
.doc-notes-ribbon.open .doc-ribbon-body {
  grid-template-rows: 1fr;
}
.doc-ribbon-body-inner {
  min-height: 0;
  overflow: hidden;
  padding: 11px 14px 14px;
}
```

- [ ] **Step 3: Verify**

Open an invoice/quotation/sale-order create form. Click the "Nota" accordion — it should expand and collapse smoothly. Open browser DevTools → Performance panel → Record a toggle animation. Confirm no layout events fire (no "Recalculate Style" + "Layout" pairs triggered per frame).

- [ ] **Step 4: Commit**

```bash
git add static/css/documents.css
git commit -m "perf(css): replace max-height animation with grid-template-rows in notes accordion"
```

---

## Phase E — Performance: Selective JS Loading

*Removes ~8 script tags from the global base.html and moves them to only the templates that need them. No functional changes.*

---

### Task 14: Move picker/form/dashboard JS to per-page loading

**Files:**
- Modify: `templates/base.html` (remove 8 script tags)
- Modify: `templates/sales/invoice_form.html`, `quotation_form.html`, `sale_order_form.html`, `credit_note_form.html`
- Modify: `templates/purchases/purchase_order_form.html`, `supplier_invoice_form.html`
- Modify: `templates/sales/payment_form.html`
- Modify: `templates/purchases/supplier_payment_create.html` (or equivalent)
- Modify: `templates/accounts/dashboard.html`
- Modify: `templates/components/datatable/wrapper.html`

- [ ] **Step 1: Edit `templates/base.html` — remove conditional scripts**

Find the script block (around line 51–76). Remove these lines from `base.html`:
```html
<!-- REMOVE these 8 lines from base.html: -->
<script src="{% static 'vendor/tom-select/tom-select.complete.min.js' %}"></script>
<script src="{% static 'js/init-tomselect.js' %}"></script>
<script src="{% static 'js/datatable.js' %}"></script>
<script src="{% static 'js/document-form.js' %}"></script>
<script src="{% static 'js/picker-base.js' %}"></script>
<script src="{% static 'js/item-picker.js' %}"></script>
<script src="{% static 'js/customer-picker.js' %}"></script>
<script src="{% static 'js/supplier-picker.js' %}"></script>
<script src="{% static 'js/picker-keyboard.js' %}"></script>
<script src="{% static 'js/payment-form.js' %}"></script>
<script src="{% static 'js/dashboard.js' %}"></script>
```

Keep in `base.html` (globally needed):
```html
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11/dist/sweetalert2.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.10/dist/htmx.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
{% block extra_js %}{% endblock %}
<script src="{% static 'js/modals.js' %}"></script>
<script src="{% static 'js/core.js' %}"></script>
<script src="{% static 'js/shell.js' %}"></script>
<script src="{% static 'js/alpine-components.js' %}"></script>
<script src="{% static 'js/app.js' %}"></script>
<script src="{% static 'js/date-range.js' %}"></script>
{% if user.is_authenticated %}
<script id="session-timeout-config" ...></script>
<script src="{% static 'js/session-timeout.js' %}"></script>
{% endif %}
```

- [ ] **Step 2: Add datatable JS to `templates/components/datatable/wrapper.html`**

The datatable wrapper is included by all list pages. Add at the bottom of `wrapper.html` (inside `{% block extra_js %}` if it supports that, otherwise use a new `{% block datatable_js %}{% endblock %}`):

Check if `wrapper.html` uses `{% block %}`. If not, add a template tag at the bottom:
```html
<!-- At the bottom of templates/components/datatable/wrapper.html -->
{% load static %}
...existing content...

{# datatable.js is required by all list views via this wrapper #}
{% block datatable_js %}
<script src="{% static 'js/datatable.js' %}"></script>
{% endblock %}
```

Since `wrapper.html` is an include (not extended), it cannot use `{% block %}`. Instead, move the script load to each list template's `{% block extra_js %}`. For each sales/purchases/items list template, add:

```html
{% block extra_js %}
<script src="{% static 'js/datatable.js' %}"></script>
{% endblock %}
```

Affected list templates (check each for existing `{% block extra_js %}`):
- `templates/sales/invoice_list.html`
- `templates/sales/quotation_list.html`
- `templates/sales/sale_order_list.html`
- `templates/sales/payment_list.html`
- `templates/sales/customer_list.html`
- `templates/items/item_list.html`
- `templates/purchases/purchase_order_list.html`
- `templates/purchases/supplier_invoice_list.html`
- `templates/purchases/supplier_payment_list.html`
- `templates/purchases/supplier_list.html`
- `templates/core/module_list.html`
- `templates/sales/ncf_sequence_list.html`
- `templates/sales/payment_term_list.html`

- [ ] **Step 3: Add document-form + picker scripts to document form templates**

For `templates/sales/invoice_form.html` — add to `{% block extra_js %}`:
```html
{% block extra_js %}
<script src="{% static 'vendor/tom-select/tom-select.complete.min.js' %}"></script>
<script src="{% static 'js/init-tomselect.js' %}"></script>
<script src="{% static 'js/document-form.js' %}"></script>
<script src="{% static 'js/picker-base.js' %}"></script>
<script src="{% static 'js/item-picker.js' %}"></script>
<script src="{% static 'js/customer-picker.js' %}"></script>
<script src="{% static 'js/picker-keyboard.js' %}"></script>
{% endblock %}
```

Repeat for: `quotation_form.html`, `sale_order_form.html`, `credit_note_form.html` (same scripts).

For purchase order forms (`purchase_order_form.html`, `supplier_invoice_form.html`):
```html
{% block extra_js %}
<script src="{% static 'vendor/tom-select/tom-select.complete.min.js' %}"></script>
<script src="{% static 'js/init-tomselect.js' %}"></script>
<script src="{% static 'js/document-form.js' %}"></script>
<script src="{% static 'js/picker-base.js' %}"></script>
<script src="{% static 'js/item-picker.js' %}"></script>
<script src="{% static 'js/supplier-picker.js' %}"></script>
<script src="{% static 'js/picker-keyboard.js' %}"></script>
{% endblock %}
```

For `payment_form.html`:
```html
{% block extra_js %}
<script src="{% static 'vendor/tom-select/tom-select.complete.min.js' %}"></script>
<script src="{% static 'js/init-tomselect.js' %}"></script>
<script src="{% static 'js/payment-form.js' %}"></script>
<script src="{% static 'js/picker-base.js' %}"></script>
<script src="{% static 'js/customer-picker.js' %}"></script>
{% endblock %}
```

For supplier payment create (check template name):
```html
{% block extra_js %}
<script src="{% static 'vendor/tom-select/tom-select.complete.min.js' %}"></script>
<script src="{% static 'js/init-tomselect.js' %}"></script>
<script src="{% static 'js/payment-form.js' %}"></script>
<script src="{% static 'js/picker-base.js' %}"></script>
<script src="{% static 'js/supplier-picker.js' %}"></script>
{% endblock %}
```

- [ ] **Step 4: Add dashboard.js to `templates/accounts/dashboard.html`**

The dashboard already has `{% block extra_js %}`. Add `dashboard.js` before the Chart.js script:
```html
{% block extra_js %}
<script src="{% static 'js/dashboard.js' %}"></script>
{% if has_sales_access %}
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
...
{% endif %}
{% endblock %}
```

- [ ] **Step 5: Verify — test every form and list page**

This is a high-risk task. Test methodically:

1. Dashboard loads and charts render ✓
2. Invoice list — sorting/filtering/pagination works ✓
3. Invoice create — item picker, customer picker, line totals work ✓
4. Quotation create — same ✓
5. Sale order create — same ✓
6. Purchase order create — item picker, supplier picker work ✓
7. Payment create — customer search, allocation works ✓
8. Customer list — datatable works ✓
9. Items list — datatable works ✓

If any page breaks with JS errors, add the missing script to that template's `{% block extra_js %}`.

- [ ] **Step 6: Commit**

```bash
git add templates/
git commit -m "perf(js): move 8 scripts from base.html to per-page conditional loading"
```

---

## Phase F — Accessibility: Touch Targets + ARIA

---

### Task 15: Increase touch targets for ribbon buttons and subnav

**Files:**
- Modify: `static/css/documents.css` (`.dt-ribbon .btn`)
- Modify: `static/css/shell.css` (`#subnav` height)

- [ ] **Step 1: Fix ribbon button padding**

In `documents.css`, find `.dt-ribbon .btn` (around line 524–528):
```css
/* BEFORE: */
.dt-ribbon .btn {
  font-size: 0.8rem;
  padding: 4px 10px;    /* ← 4px top/bottom gives ~30px height */
  border-radius: 4px;
  white-space: nowrap;
}

/* AFTER: */
.dt-ribbon .btn {
  font-size: 0.8rem;
  padding: 6px 10px;    /* 6px top/bottom gives ~34px — acceptable for ERP ribbon density */
  border-radius: 4px;
  white-space: nowrap;
  min-height: 32px;     /* explicit floor */
}
```

- [ ] **Step 2: Fix subnav height**

In `shell.css`, find `#subnav` (around line 273):
```css
/* BEFORE: */
#subnav {
  display: flex;
  align-items: stretch;
  height: 40px;          /* ← 40px fails 44px minimum */
  ...
}

/* AFTER: */
#subnav {
  display: flex;
  align-items: stretch;
  height: 44px;          /* WCAG 2.5.5 minimum touch target height */
  ...
}
```

- [ ] **Step 3: Verify**

Open any list page with a command ribbon. The buttons should be slightly taller. The subnav ("Clientes", "Artículos") should be slightly taller (4px diff — very subtle, but correct).

- [ ] **Step 4: Commit**

```bash
git add static/css/documents.css static/css/shell.css
git commit -m "fix(a11y): increase touch targets — ribbon buttons 30→34px, subnav 40→44px"
```

---

### Task 16: Add `aria-expanded` to sidebar toggle button

**Files:**
- Modify: `templates/partials/_navbar.html`
- Modify: `static/js/shell.js`

- [ ] **Step 1: Add `aria-expanded` to the toggle button in `_navbar.html`**

Find the hamburger button (line 6 in `_navbar.html`):
```html
<!-- BEFORE: -->
<button class="topbar-toggle" onclick="toggleSidebar()" aria-label="{% trans 'Toggle sidebar' %}">
  <i class="bi bi-list"></i>
</button>

<!-- AFTER: -->
<button class="topbar-toggle"
        id="sidebar-toggle-btn"
        onclick="toggleSidebar()"
        aria-label="{% trans 'Toggle sidebar' %}"
        aria-expanded="false"
        aria-controls="sidebar">
  <i class="bi bi-list"></i>
</button>
```

- [ ] **Step 2: Update `toggleSidebar()` in `static/js/shell.js`**

Find the `toggleSidebar` function in `shell.js` and add `aria-expanded` update:
```js
// Find the existing toggleSidebar function and add these lines inside it.
// The exact current implementation may vary — add the aria-expanded update wherever
// the open/close state is toggled.

function toggleSidebar() {
  // ... existing logic that adds/removes 'sidebar-open' or 'sidebar-collapsed' from body ...
  
  // Add this block at the end of the function:
  const btn = document.getElementById('sidebar-toggle-btn');
  if (btn) {
    const isOpen = document.body.classList.contains('sidebar-open');
    btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  }
}
```

If the sidebar has both a "collapsed" state (desktop icon-only) and an "open" state (mobile overlay), update `aria-expanded` for both cases — `true` when sidebar is visible, `false` when hidden.

- [ ] **Step 3: Verify**

Use your browser's accessibility inspector (Chrome: DevTools → Elements → Accessibility tab, or Axe extension). Click the hamburger button and confirm `aria-expanded` changes from `false` to `true` and back. Use Tab key to navigate to the button and press Space/Enter — sidebar should toggle.

- [ ] **Step 4: Commit**

```bash
git add templates/partials/_navbar.html static/js/shell.js
git commit -m "fix(a11y): add aria-expanded state management to sidebar toggle button"
```

---

### Task 17: Replace sidebar backdrop `<div>` with `<button>`

**Files:**
- Modify: `templates/partials/_sidebar.html`

- [ ] **Step 1: Edit the backdrop element**

Find the last line of `_sidebar.html`:
```html
<!-- BEFORE: -->
{# Mobile backdrop — clicking it closes the sidebar #}
<div id="sidebar-backdrop" onclick="toggleSidebar()"></div>

<!-- AFTER: -->
{# Mobile backdrop — clicking it closes the sidebar #}
<button id="sidebar-backdrop"
        type="button"
        onclick="toggleSidebar()"
        aria-label="{% trans 'Cerrar menú' %}"
        tabindex="-1">
</button>
```

`tabindex="-1"` keeps the backdrop out of the tab order (correct — it's a visual dismiss target, not a primary interactive element) while making it a proper semantic button that screen readers can identify.

- [ ] **Step 2: Verify**

Open the app on a narrow viewport (< 992px). Open the sidebar. The backdrop should still appear and close the sidebar when clicked. No visual change expected (the backdrop is an absolutely-positioned overlay).

- [ ] **Step 3: Commit**

```bash
git add templates/partials/_sidebar.html
git commit -m "fix(a11y): replace sidebar backdrop div with button for semantic correctness"
```

---

## Phase G — Template Content Fixes

---

### Task 18: Fix ITBIS rate badge semantic colors

**Files:**
- Modify: `templates/sales/invoice_detail.html`

**Context:** RATE_18 uses `badge-overdue` (red = "error/danger") and RATE_16 uses `badge-confirmed` (blue = arbitrary). Tax rates are neutral data — they should not use status colors.

- [ ] **Step 1: Edit `invoice_detail.html` around line 211–216**

```html
<!-- BEFORE: -->
<td class="text-center">
  {% if item.itbis_rate == 'RATE_18' %}
    <span class="badge-soft badge-overdue">{{ item.get_itbis_rate_display }}</span>
  {% elif item.itbis_rate == 'RATE_16' %}
    <span class="badge-soft badge-confirmed">{{ item.get_itbis_rate_display }}</span>
  {% else %}
    <span class="badge-soft badge-default">{{ item.get_itbis_rate_display }}</span>
  {% endif %}
</td>

<!-- AFTER: -->
<td class="text-center">
  <span class="badge-soft badge-default">{{ item.get_itbis_rate_display }}</span>
</td>
```

- [ ] **Step 2: Verify**

Open any invoice detail. The ITBIS column should show all rates (EXENTO, 16%, 18%) in the same neutral gray badge. No red/blue coloring.

- [ ] **Step 3: Commit**

```bash
git add templates/sales/invoice_detail.html
git commit -m "fix(ux): remove semantic status colors from ITBIS rate badges in invoice detail"
```

---

### Task 19: Remove "Próximamente" section from sidebar

**Files:**
- Modify: `templates/partials/_sidebar.html`

**Context:** Disabled "Inventario" and "Recursos Humanos" nav items remind users on every page load that they're missing features. Remove until modules are ready.

- [ ] **Step 1: Remove the Próximamente section**

Find and delete this block in `_sidebar.html`:
```html
    {# ── Coming soon modules (greyed out placeholders) ───────── #}
    <div class="sidebar-section-label">{% trans "Próximamente" %}</div>
    <ul class="sidebar-nav">
      <li>
        <span class="sidebar-nav-link sidebar-nav-link--disabled">
          <i class="bi bi-boxes"></i>
          <span>{% trans "Inventario" %}</span>
        </span>
      </li>
      <li>
        <span class="sidebar-nav-link sidebar-nav-link--disabled">
          <i class="bi bi-person-vcard-fill"></i>
          <span>{% trans "Recursos Humanos" %}</span>
        </span>
      </li>
    </ul>
```

Delete all 14 lines of this block.

Also clean up `static/css/shell.css` — remove the now-unused `.sidebar-nav-link--disabled` rule:
```css
/* Delete this rule from shell.css: */
.sidebar-nav-link--disabled {
  opacity: .4;
  cursor: default;
  pointer-events: none;
}
```

- [ ] **Step 2: Verify**

Open the app while logged in. The sidebar should no longer show "Próximamente" with the grayed-out items. The sidebar should end with the last active section (Organización or Administración depending on role).

- [ ] **Step 3: Commit**

```bash
git add templates/partials/_sidebar.html static/css/shell.css
git commit -m "fix(ux): remove Próximamente placeholder section from sidebar"
```

---

### Task 20: Remove inline `width:360px` from invoice form totals card

**Files:**
- Modify: `templates/sales/invoice_form.html:86`

- [ ] **Step 1: Remove inline style**

Find around line 84–87 in `invoice_form.html`:
```html
<!-- BEFORE: -->
  <div class="d-flex justify-content-end mb-3">
    <div class="doc-totals-card" style="width:360px">

<!-- AFTER: -->
  <div class="d-flex justify-content-end mb-3">
    <div class="doc-totals-card">
```

The `doc-totals-card` CSS in `documents.css` already has proper width/responsive behavior. The inline style was fighting it.

- [ ] **Step 2: Verify**

Open the invoice create form. The totals card at the bottom right should be the same visual width as before (the CSS already sets it). On a narrow viewport (< 768px), the card should now expand to full width (responsive grid collapses to 1fr).

- [ ] **Step 3: Commit**

```bash
git add templates/sales/invoice_form.html
git commit -m "fix(responsive): remove inline width:360px from invoice form totals card"
```

---

### Task 21: Remove inline styles from `invoice_detail.html`

**Files:**
- Modify: `templates/sales/invoice_detail.html`

- [ ] **Step 1: Replace inline layout style on the header**

Find around line 9 in `invoice_detail.html`:
```html
<!-- BEFORE: -->
  <div style="display:flex;align-items:center;gap:12px">

<!-- AFTER: -->
  <div class="d-flex align-items-center gap-3">
```

- [ ] **Step 2: Replace inline font-weight on audit timestamps**

Find around line 394 (in the Auditoría kv-card):
```html
<!-- BEFORE: -->
<span class="kv-v font-monospace" style="font-weight:500">{{ invoice.created_at|date:"d/m/Y H:i" }}</span>
...
<span class="kv-v font-monospace" style="font-weight:500">{{ invoice.updated_at|date:"d/m/Y H:i" }}</span>

<!-- AFTER: -->
<span class="kv-v font-monospace">{{ invoice.created_at|date:"d/m/Y H:i" }}</span>
...
<span class="kv-v font-monospace">{{ invoice.updated_at|date:"d/m/Y H:i" }}</span>
```

The `.kv-v` class already sets `font-weight: 700`. Removing the `font-weight:500` override is actually a promotion — kv-v will be bold. If you want the muted weight (500), add `class="kv-v font-monospace fw-medium"` instead.

- [ ] **Step 3: Fix pay modal inline styles**

Around line 422 in `invoice_detail.html`:
```html
<!-- BEFORE: -->
<div class="modal-content border-0" style="border-radius:8px;overflow:hidden">
...
<div class="modal-footer" style="background:#f9fafb;border-top:1px solid #e5e7eb">

<!-- AFTER: -->
<div class="modal-content border-0 rounded-3 overflow-hidden">
...
<div class="modal-footer surface-muted">
```

The `.surface-muted` class is defined in `components.css` with exactly `background: #f9fafb` and the modal-footer rule sets the border automatically.

- [ ] **Step 4: Verify**

Open an invoice detail. Visual appearance should be identical or slightly improved (bolder audit timestamps, cleaner modal).

- [ ] **Step 5: Commit**

```bash
git add templates/sales/invoice_detail.html
git commit -m "refactor(templates): remove inline styles from invoice_detail.html"
```

---

### Task 22: Replace customer form smart buttons with `db-kpi` component

**Files:**
- Modify: `templates/sales/customer_form.html`

**Context:** The "smart buttons" (invoice/payment count) on the customer edit form use raw inline styles instead of the `db-kpi` component. This makes them visually inconsistent with the rest of the app.

- [ ] **Step 1: Replace the smart buttons markup**

Find around lines 32–46 in `customer_form.html`:
```html
<!-- BEFORE: -->
{% if smart_buttons %}
<div class="d-flex gap-2 mb-3 flex-wrap">
  <a href="{{ smart_buttons.detail_url }}" class="text-decoration-none">
    <div class="app-table-wrap px-3 py-2 text-center" style="min-width:80px;cursor:pointer">
      <div class="fw-bold lh-1 mb-1" style="font-size:1.25rem;color:#1e2130">{{ smart_buttons.invoice_count }}</div>
      <div class="text-muted" style="font-size:.65rem;text-transform:uppercase;letter-spacing:.04em">{% trans "Facturas" %}</div>
    </div>
  </a>
  <a href="{{ smart_buttons.detail_url }}" class="text-decoration-none">
    <div class="app-table-wrap px-3 py-2 text-center" style="min-width:80px;cursor:pointer">
      <div class="fw-bold lh-1 mb-1" style="font-size:1.25rem;color:#1e2130">{{ smart_buttons.payment_count }}</div>
      <div class="text-muted" style="font-size:.65rem;text-transform:uppercase;letter-spacing:.04em">{% trans "Pagos" %}</div>
    </div>
  </a>
</div>
{% endif %}

<!-- AFTER: -->
{% if smart_buttons %}
<div class="row g-2 mb-3">
  <div class="col-auto">
    <a href="{{ smart_buttons.detail_url }}" class="db-kpi is-ar" style="min-width:120px">
      <span class="db-kpi-icon"><i class="bi bi-receipt"></i></span>
      <div class="db-kpi-body">
        <div class="db-kpi-value">{{ smart_buttons.invoice_count }}</div>
        <div class="db-kpi-label">{% trans "Facturas" %}</div>
      </div>
    </a>
  </div>
  <div class="col-auto">
    <a href="{{ smart_buttons.detail_url }}" class="db-kpi is-pos" style="min-width:120px">
      <span class="db-kpi-icon"><i class="bi bi-cash-stack"></i></span>
      <div class="db-kpi-body">
        <div class="db-kpi-value">{{ smart_buttons.payment_count }}</div>
        <div class="db-kpi-label">{% trans "Pagos" %}</div>
      </div>
    </a>
  </div>
</div>
{% endif %}
```

- [ ] **Step 2: Verify**

Open any customer edit page (`/sales/customers/<pk>/edit/`). The invoice/payment count should now appear as proper db-kpi cards (matching the style on list pages) instead of the old app-table-wrap mini tiles.

- [ ] **Step 3: Commit**

```bash
git add templates/sales/customer_form.html
git commit -m "fix(ux): replace customer form smart buttons with db-kpi component"
```

---

## Phase H — Structural Improvements

---

### Task 23: Reduce eyebrow label density in card section headers

**Files:**
- Modify: `static/css/components.css` (`.app-card-head`)

**Context:** `.app-card-head` uses `text-transform: uppercase; letter-spacing: .04em` on every card section header in the app. When every surface uses the same pattern, it stops communicating hierarchy. Card headers can be plain sentence-case semibold — reserve uppercase for navigation labels, table column headers, and KPI labels.

- [ ] **Step 1: Edit `.app-card-head` in `components.css`**

Find around line 461:
```css
/* BEFORE: */
.app-card-head {
  padding: 10px 14px 9px;
  border-bottom: 1px solid var(--hairline);
  font-size: .7rem;
  font-weight: 600;
  text-transform: uppercase;      /* ← remove */
  letter-spacing: .04em;          /* ← remove */
  color: var(--muted);
}

/* AFTER: */
.app-card-head {
  padding: 10px 14px 9px;
  border-bottom: 1px solid var(--hairline);
  font-size: .78rem;              /* slightly larger — readable without caps */
  font-weight: 700;
  /* text-transform removed */
  /* letter-spacing removed */
  color: #374151;                 /* slightly darker than var(--muted) for contrast */
}
```

Also update `.app-card-head--row .app-card-head-title` (the row variant) the same way:
```css
.app-card-head--row .app-card-head-title {
  font-size: .78rem;
  font-weight: 700;
  color: #374151;
  /* text-transform, letter-spacing, uppercase: all removed */
}
```

- [ ] **Step 2: Verify**

Open the customer create form. The section headers ("Datos generales", "Contacto", "Dirección", "Facturación") should now appear as plain semibold sentence-case text instead of tiny uppercase. This is a visible change — confirm it looks intentionally cleaner, not broken.

- [ ] **Step 3: Commit**

```bash
git add static/css/components.css
git commit -m "fix(design): remove uppercase tracking from app-card-head — reduce eyebrow noise"
```

---

### Task 24: Pass breadcrumbs to `DashboardView`

**Files:**
- Modify: `apps/accounts/views.py` (`DashboardView.get_context_data`)

**Context:** The topbar shows a breadcrumb nav, but `DashboardView` doesn't pass `breadcrumbs` context. The topbar title area is empty on the main dashboard page.

- [ ] **Step 1: Write a test first**

Add to `apps/accounts/tests/test_views.py` (create if it doesn't exist):
```python
from django.test import TestCase
from django.urls import reverse
from apps.accounts.tests.factories import UserFactory, OrganizationFactory, MembershipFactory


class DashboardViewTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.org = OrganizationFactory()
        self.membership = MembershipFactory(user=self.user, organization=self.org, role='OWNER')
        self.client.force_login(self.user)
        session = self.client.session
        session['active_org_slug'] = self.org.slug
        session.save()

    def test_dashboard_includes_breadcrumbs(self):
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('breadcrumbs', response.context)
        crumbs = response.context['breadcrumbs']
        self.assertEqual(len(crumbs), 1)
        self.assertEqual(crumbs[0]['label'], 'Dashboard')
```

- [ ] **Step 2: Run the test — verify it fails**

```bash
pytest apps/accounts/tests/test_views.py::DashboardViewTest::test_dashboard_includes_breadcrumbs -v
```

Expected: FAIL with `KeyError: 'breadcrumbs'` or `AssertionError`.

- [ ] **Step 3: Implement in `apps/accounts/views.py`**

Find the `DashboardView` class and its `get_context_data` method. Add breadcrumbs to the context:
```python
class DashboardView(ERPBaseViewMixin, TemplateView):
    # ... existing class attributes ...

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # ... existing context building code ...
        
        # Add breadcrumbs for topbar
        context["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": None}
        ]
        
        return context
```

Make sure `from django.utils.translation import gettext_lazy as _` is imported at the top of the file (it almost certainly already is).

- [ ] **Step 4: Run the test — verify it passes**

```bash
pytest apps/accounts/tests/test_views.py::DashboardViewTest::test_dashboard_includes_breadcrumbs -v
```

Expected: PASS

- [ ] **Step 5: Verify in browser**

Open the dashboard. The topbar should now show "Dashboard" as a breadcrumb item instead of being blank.

- [ ] **Step 6: Commit**

```bash
git add apps/accounts/views.py apps/accounts/tests/test_views.py
git commit -m "fix(ux): pass breadcrumbs context to DashboardView for topbar display"
```

---

### Task 25: Add left branding panel to auth layout

**Files:**
- Modify: `templates/base_anon.html`

**Context:** The auth split layout only renders the right panel. The CLAUDE.md documents a left panel (400px dark, logo, headline, feature list) that was never built. First-time users see a blank page with a form — no brand communication.

- [ ] **Step 1: Add the left panel markup to `base_anon.html`**

After the `<div class="auth-split">` opening tag, add before `<main class="auth-panel">`:

```html
{% load static %}
{% block body %}
<div class="auth-split">

  {# ── Left branding panel ──────────────────────────────────── #}
  <aside class="auth-brand d-none d-md-flex">
    <a href="/" class="auth-brand-logo-link">
      <img src="{% static 'img/sabsys-erp-logo.png' %}" alt="SabSys" style="height:36px;width:auto;filter:brightness(0) invert(1);">
    </a>
    <div class="auth-brand-copy">
      <p class="auth-brand-eyebrow">Sistema ERP</p>
      <h2 class="auth-brand-headline">Facturación electrónica para empresas dominicanas.</h2>
      <ul class="auth-brand-features">
        <li><i class="bi bi-check2-circle" aria-hidden="true"></i>Comprobantes fiscales electrónicos (e-CF)</li>
        <li><i class="bi bi-check2-circle" aria-hidden="true"></i>Reportes 606/607/608 para la DGII</li>
        <li><i class="bi bi-check2-circle" aria-hidden="true"></i>Gestión de compras y proveedores</li>
        <li><i class="bi bi-check2-circle" aria-hidden="true"></i>Control de clientes y pagos</li>
      </ul>
    </div>
    <p class="auth-brand-foot">© {% now "Y" %} SabSys · <a href="https://mysabsys.com" target="_blank" rel="noopener" class="auth-brand-foot-link">mysabsys.com</a></p>
  </aside>

  {# ── Form panel ──────────────────────────────────────────────── #}
  <main class="auth-panel">
```

- [ ] **Step 2: Add CSS for the left panel to the `<style>` block in `base_anon.html`**

Inside the existing `<style>` block, add after the `.auth-split` rule:
```css
/* ── Left branding panel ────────────────────────────────────── */
.auth-brand {
  width: 400px;
  min-width: 400px;
  min-height: 100vh;
  background: #1e2130;
  display: flex;
  flex-direction: column;
  padding: 48px 40px;
  gap: 32px;
  position: sticky;
  top: 0;
  max-height: 100vh;
}

.auth-brand-logo-link {
  display: block;
  text-decoration: none;
}

.auth-brand-copy {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 20px;
}

.auth-brand-eyebrow {
  font-size: 0.6875rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: #5b9af5;
  margin: 0;
}

.auth-brand-headline {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 1.9rem;
  font-weight: 700;
  color: #fff;
  line-height: 1.2;
  letter-spacing: -0.02em;
  margin: 0;
  text-wrap: balance;
}

.auth-brand-features {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.auth-brand-features li {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 0.875rem;
  color: #9ba3bf;
  line-height: 1.35;
}

.auth-brand-features i {
  color: #5b9af5;
  font-size: 1rem;
  flex-shrink: 0;
  margin-top: 1px;
}

.auth-brand-foot {
  font-size: 0.75rem;
  color: #4a5570;
  margin: 0;
}

.auth-brand-foot-link {
  color: #5b9af5;
  text-decoration: none;
}

.auth-brand-foot-link:hover { text-decoration: underline; }
```

- [ ] **Step 3: Verify**

Open the login page (`/accounts/login/`), signup page, and password reset page. On desktop (≥ 768px), the left dark panel should be visible with the logo, headline, and feature list. The form should be on the right. On mobile (< 768px), the left panel should be hidden (`d-none d-md-flex`) and only the form should show.

Check all auth pages: login, password reset, invite acceptance, email confirmation.

- [ ] **Step 4: Commit**

```bash
git add templates/base_anon.html
git commit -m "feat(ui): add left branding panel to auth layout (logo, headline, feature list)"
```

---

### Task 26: Restructure invoice detail action bar

**Files:**
- Modify: `templates/sales/invoice_detail.html`

**Context:** Up to 8 action buttons can appear simultaneously (Edit, Confirm, Delete, Mark Sent, Register Payment, Print, PDF, Credit Note, Cancel). This creates visual noise. Restructure: one primary action per status, secondary grouped, destructive actions in the overflow `doc-action-overflow` (hidden on mobile, shown in "Más" dropdown).

- [ ] **Step 1: Identify the current structure (lines 22–85)**

The existing template has several `{% if invoice.status == "..." %}` blocks all at the same level in `app-header-actions`. The restructured version collapses these into:
1. **Primary** — one `btn-brand` per status state
2. **Secondary** — outline secondary (Print always visible; PDF/Sent only when available)
3. **Overflow** — inside `.doc-action-overflow` (hidden on mobile): Credit Note, Cancel, Delete

- [ ] **Step 2: Replace the `app-header-actions` block**

Find lines 20–85 in `invoice_detail.html` and replace with:

```html
  <div class="app-header-actions">

    {# ── Primary action (one per status) ─── #}
    {% if invoice.status == "DRAFT" %}
      <form method="post" action="{% url 'sales:invoice_confirm' invoice.pk %}"
            x-data
            x-on:submit.prevent="swalConfirm($el, '{% trans "¿Confirmar y asignar e-NCF? Esta acción es irreversible." %}', {icon:'warning', color:'#10b981', ok:'Sí, confirmar'})">
        {% csrf_token %}
        <button class="btn btn-sm btn-brand">
          <i class="bi bi-check-circle me-1"></i>{% trans "Confirmar" %}
        </button>
      </form>
    {% elif invoice.status in "CONFIRMED,SENT,OVERDUE" %}
      <button class="btn btn-sm btn-brand"
              data-bs-toggle="modal" data-bs-target="#payModal">
        <i class="bi bi-cash-coin me-1"></i>{% trans "Registrar pago" %}
      </button>
    {% endif %}

    {# ── Secondary actions ─── #}
    {% if invoice.status == "DRAFT" %}
      <a href="{% url 'sales:invoice_edit' invoice.pk %}" class="btn btn-outline-secondary btn-sm">
        <i class="bi bi-pencil me-1"></i>{% trans "Editar" %}
      </a>
    {% endif %}

    {% if invoice.status == "CONFIRMED" %}
      <form method="post" action="{% url 'sales:invoice_send' invoice.pk %}">
        {% csrf_token %}
        <button class="btn btn-outline-secondary btn-sm">
          <i class="bi bi-send me-1"></i>{% trans "Marcar enviada" %}
        </button>
      </form>
    {% endif %}

    <a href="{% url 'sales:invoice_print' invoice.pk %}" target="_blank"
       class="btn btn-outline-secondary btn-sm">
      <i class="bi bi-printer me-1"></i>{% trans "Imprimir" %}
    </a>

    {# ── Overflow actions (collapsed on mobile) ─── #}
    <div class="doc-action-row">
      <div class="doc-action-overflow">
        {% if invoice.encf and invoice.status != "DRAFT" %}
          <a href="{% url 'sales:invoice_pdf' invoice.pk %}" class="btn btn-outline-secondary btn-sm">
            <i class="bi bi-file-earmark-pdf me-1"></i>PDF
          </a>
          <a href="{% url 'sales:credit_note_create' invoice.pk %}" class="btn btn-outline-warning btn-sm">
            <i class="bi bi-file-minus me-1"></i>{% trans "Nota de Crédito" %}
          </a>
        {% endif %}

        {% if invoice.status == "DRAFT" %}
          <form method="post" action="{% url 'sales:invoice_delete' invoice.pk %}"
                x-data
                x-on:submit.prevent="swalConfirm($el, '{% trans "¿Eliminar borrador?" %}', {icon:'warning', color:'#dc3545', ok:'Sí, eliminar'})">
            {% csrf_token %}
            <button class="btn btn-outline-danger btn-sm">
              <i class="bi bi-trash me-1"></i>{% trans "Eliminar" %}
            </button>
          </form>
        {% endif %}

        {% if invoice.status != "PAID" and invoice.status != "CANCELLED" and invoice.status != "DRAFT" %}
          <form method="post" action="{% url 'sales:invoice_cancel' invoice.pk %}"
                x-data
                x-on:submit.prevent="swalConfirm($el, '{% trans "¿Anular esta factura? El e-NCF quedará registrado en el formato 608." %}', {icon:'warning', color:'#dc3545', ok:'Sí, anular'})">
            {% csrf_token %}
            <button class="btn btn-outline-danger btn-sm">
              <i class="bi bi-x-circle me-1"></i>{% trans "Anular" %}
            </button>
          </form>
        {% endif %}
      </div>

      {# "Más" dropdown — visible only <720px via .doc-action-more CSS #}
      <div class="dropdown doc-action-more">
        <button class="btn btn-outline-secondary btn-sm dropdown-toggle dropdown-toggle-no-caret"
                type="button" data-bs-toggle="dropdown" aria-label="{% trans 'Más acciones' %}">
          <i class="bi bi-three-dots"></i>
        </button>
        <ul class="dropdown-menu dropdown-menu-end">
          {% if invoice.encf and invoice.status != "DRAFT" %}
          <li>
            <a class="dropdown-item" href="{% url 'sales:invoice_pdf' invoice.pk %}">
              <i class="bi bi-file-earmark-pdf me-2"></i>PDF
            </a>
          </li>
          <li>
            <a class="dropdown-item" href="{% url 'sales:credit_note_create' invoice.pk %}">
              <i class="bi bi-file-minus me-2"></i>{% trans "Nota de Crédito" %}
            </a>
          </li>
          {% endif %}
          {% if invoice.status == "DRAFT" %}
          <li>
            <form method="post" action="{% url 'sales:invoice_delete' invoice.pk %}"
                  x-data x-on:submit.prevent="swalConfirm($el, '{% trans "¿Eliminar borrador?" %}', {icon:'warning', color:'#dc3545', ok:'Sí, eliminar'})">
              {% csrf_token %}
              <button type="submit" class="dropdown-item text-danger">
                <i class="bi bi-trash me-2"></i>{% trans "Eliminar" %}
              </button>
            </form>
          </li>
          {% endif %}
          {% if invoice.status != "PAID" and invoice.status != "CANCELLED" and invoice.status != "DRAFT" %}
          <li>
            <form method="post" action="{% url 'sales:invoice_cancel' invoice.pk %}"
                  x-data x-on:submit.prevent="swalConfirm($el, '{% trans "¿Anular esta factura? El e-NCF quedará registrado en el formato 608." %}', {icon:'warning', color:'#dc3545', ok:'Sí, anular'})">
              {% csrf_token %}
              <button type="submit" class="dropdown-item text-danger">
                <i class="bi bi-x-circle me-2"></i>{% trans "Anular" %}
              </button>
            </form>
          </li>
          {% endif %}
        </ul>
      </div>
    </div>

  </div>
```

- [ ] **Step 3: Verify across all status states**

Test every invoice status:

| Status | Expected primary | Expected secondary | Overflow |
|---|---|---|---|
| DRAFT | "Confirmar" (btn-brand) | "Editar" + "Imprimir" | "Eliminar" (danger) |
| CONFIRMED | "Registrar pago" (btn-brand) | "Marcar enviada" + "Imprimir" | PDF, Nota Crédito, Anular |
| SENT | "Registrar pago" (btn-brand) | "Imprimir" | PDF, Nota Crédito, Anular |
| OVERDUE | "Registrar pago" (btn-brand) | "Imprimir" | PDF, Nota Crédito, Anular |
| PAID | *(no primary)* | "Imprimir" | PDF, Nota Crédito |
| CANCELLED | *(no primary)* | "Imprimir" | *(no destructive)* |

On a narrow viewport (< 720px): overflow buttons hidden; "⋯" (Más) dropdown appears.

- [ ] **Step 4: Commit**

```bash
git add templates/sales/invoice_detail.html
git commit -m "fix(ux): restructure invoice action bar — one primary per status, destructive in overflow"
```

---

## Self-Review

### Spec Coverage

| Audit Finding | Task |
|---|---|
| P0-1 Sticky bar class mismatch | Task 6 |
| P0-2 --warn token duplicate | Task 1 |
| P0-3 Side-stripe borders | Tasks 9, 10, 11, 12 |
| P1-1 #94a3b8 contrast on white | Task 2 |
| P1-2 Sidebar label contrast on dark | Task 3 |
| P1-3 Touch targets <44px | Task 15 |
| P1-4 12 JS files unconditional | Task 14 |
| P1-5 max-height animation | Task 13 |
| P1-6 Deprecated app_styles includes | Tasks 7, 8 |
| P1-7 Safari momentum scroll | Task 5 |
| P1-8 Invoice action bar overflow | Task 26 |
| P1-9 Eyebrow labels everywhere | Task 23 |
| P2-1 Inline styles in templates | Tasks 21, 22 |
| P2-2 Module accent per page | Task 12 (doc-paper border) |
| P2-3 Customer smart buttons inline styles | Task 22 |
| P2-4 Typography floor 9px | Task 4 |
| P2-5 Dual metric card systems | (documented intentional — no change) |
| P2-6 Dashboard breadcrumbs empty | Task 24 |
| P2-7 Auth left panel missing | Task 25 |
| P2-8 ITBIS badge semantics | Task 18 |
| P3-1 Próximamente section | Task 19 |
| P3-2 Sidebar aria-expanded | Task 16 |
| P3-3 Sidebar backdrop inline onclick | Task 17 |
| P3-4 CSS comment with HTML markup | (cosmetic — omitted from plan) |
| P3-5 invoice_form inline width:360px | Task 20 |

All 29 audit findings mapped. P3-4 (removing an HTML comment from CSS) is left as a manual 30-second fix — not worth a task.

### Placeholder Scan
No placeholders found. All tasks contain exact code.

### Type Consistency
- `db-kpi` class added in Task 22 uses the same structure as `_kpi_cards.html`
- `aria-expanded` attribute added in Task 16 is managed in `shell.js` by the same `toggleSidebar()` function referenced in the navbar template
- `app-form-bar` class in Task 6 matches the CSS definition in `components.css:951`
- `surface-muted` class in Task 21 is defined in `components.css:934`
- Breadcrumbs dict shape `{"label": ..., "url": ...}` in Task 24 matches `_navbar.html` iteration

---

**Plan saved to `docs/superpowers/plans/2026-06-17-ui-ux-audit-fixes.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task, review output between tasks, fast iteration. Use `superpowers:subagent-driven-development`.

**2. Inline Execution** — execute tasks in this session with checkpoints. Use `superpowers:executing-plans`.

Which approach?
