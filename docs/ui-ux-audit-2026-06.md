# SabSys ERP — UI/UX Design Audit
**Date:** 2026-06-17  
**Scope:** All templates in `templates/`, CSS in `static/css/`, JS in `static/js/`  
**Method:** Impeccable audit framework + frontend-design heuristic review  
**Audience:** Dominican Republic SMB owners and accountants  

---

## Audit Health Score

| # | Dimension | Score | Key Finding |
|---|-----------|-------|-------------|
| 1 | Accessibility | 2/4 | `#94a3b8` text on white fails WCAG AA; sidebar labels fail on dark |
| 2 | Performance | 2/4 | 12 JS files loaded unconditionally; `max-height` animation on notes panel |
| 3 | Responsive Design | 3/4 | Mostly responsive; inline `width:360px` totals and 30px touch targets |
| 4 | Theming | 2/4 | `--warn` token defined twice; 40+ hard-coded hex values outside token system |
| 5 | Anti-Patterns | 1/4 | Side-stripe borders on 8+ components; eyebrow labels on every section |
| **Total** | | **10/20** | **Acceptable — significant work needed** |

---

## Anti-Patterns Verdict

**Does this look AI-generated?** Partially — not obviously, but several tells accumulate:

- **Side-stripe borders everywhere** — `.db-kpi`, `.db-panel-overdue`, `.db-cash-net`, `.db-empty-state`, `.kv-note`, `.module-page-title`, `.dt-row-selected` all use `border-left: 3px–4px solid [color]` as the primary visual accent. This is the #1 banned pattern in the impeccable rules. It reads as "I needed to add color to a card and this was the easiest way."
- **Eyebrow labels on every section** — `.sidebar-section-label`, `.app-card-head`, `.kv-card-title`, `.db-panel-title`, `.doc-meta-label`, `.doc-lines-title` all use tiny uppercase tracked labels above every section. When literally every card/section/panel has one, none of them provide hierarchy — they add noise.
- **Hero-metric template on the dashboard** — `.db-kpi` with icon + mono number + uppercase label, in a 4-up grid, with accent stripe. Classic.

The design avoids the worst tells (no gradient text, no glassmorphism, no purple-on-white gradient), and the typography pair (Cormorant Garamond + Manrope + IBM Plex Mono) is distinctive. The module-accent system is smart. The overall aesthetic is coherent — it just needs the structural anti-patterns removed.

---

## Executive Summary

- **Audit Health Score: 10/20** (Acceptable)
- **Total issues: 7 P0, 9 P1, 8 P2, 5 P3**
- **Critical:** Side-stripe border pattern; `#94a3b8` contrast failure; sticky bar class mismatch (broken CSS)
- **Systemic:** Token system partially adopted — 40+ hard-coded hex values remain; eyebrow pattern everywhere
- **Next steps (priority order):** Fix broken sticky bars → fix contrast failures → replace side-stripe borders → consolidate `--warn` token → reduce JS bundle → remove eyebrow noise

---

## Detailed Findings by Severity

---

### P0 — Blocking

---

#### [P0-1] Sticky save bar has no CSS — buttons not sticky

**Location:** `templates/sales/customer_form.html:152`, `templates/sales/payment_term_form.html:33`, `templates/purchases/supplier_form.html:145`, `templates/items/item_form.html:39`  
**Category:** Accessibility / UX  
**Impact:** The save bar at the bottom of long forms uses class `.form-sticky-bar` but the CSS in `static/css/components.css:951` defines `.app-form-bar`. These do not match. The bar renders but is **not sticky** — on long forms, users must scroll to the bottom to save, and the save button may be hidden off-screen.  

**Fix:**

Option A — rename templates to use the existing CSS class:
```html
<!-- Before (in customer_form.html, supplier_form.html, item_form.html, payment_term_form.html) -->
<div class="form-sticky-bar">

<!-- After -->
<div class="app-form-bar">
```

Option B — add the alias to CSS (if you want to keep the template class name):
```css
/* components.css — add alias */
.form-sticky-bar {
  position: sticky;
  bottom: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  background: #f9fafb;
  border-top: 1px solid var(--hairline);
  border-radius: 0 0 8px 8px;
}
```

Option A preferred — single source of truth.

---

#### [P0-2] `--warn` token defined twice with conflicting values

**Location:** `static/css/components.css:101` and `static/css/components.css:1037`  
**Category:** Theming  
**Impact:** Line 101 sets `--warn: #d97706` (amber-600). Line 1037 sets `--warn: #b45309` (amber-800, darker). Since both are in `:root`, the last one wins globally. `.num-warn`, `.db-cash-dot.ap`, and any component using `var(--warn)` will silently use the darker value, while the design intent at line 101 was the lighter amber. If either value changes in the future, only the second definition needs changing — which developers won't know.

**Fix — `static/css/components.css:101`:**
```css
:root {
  /* Remove --warn from this first block entirely. */
  /* It is already defined with the correct value in the KV-card section below. */
  --brand-ink: #1e2130;
  --brand-ink-2: #2a3050;
  --brand-accent: #3f6fd6;
  --brand-soft: #eef3fc;
  --pos: #16a34a;
  --neg: #b42318;
  /* --warn was here: REMOVE IT */
  --muted: #6b7280;
  --muted-2: #9ca3af;
  --hairline: #e5e7eb;
  --hairline-soft: #eef0f6;
}
```

Then update `static/css/components.css:1037` to be the single definition:
```css
:root {
  --warn: #b45309;   /* outstanding / aging / amber — single definition */
  /* ... rest of kv-card tokens */
}
```

---

#### [P0-3] Side-stripe borders as primary visual accent (8+ instances)

**Location:** `static/css/components.css:326` (KPI cards), `static/css/dashboard.css:144` (overdue panel), `static/css/dashboard.css:207` (empty state), `static/css/dashboard.css:251` (cash position), `static/css/components.css:1187` (kv-note), `static/css/documents.css:13` (module page title), `static/css/documents.css:595` (selected row)  
**Category:** Anti-Pattern  
**WCAG/Standard:** Impeccable absolute ban — "border-left or border-right greater than 1px as a colored accent on cards, list items, callouts, or alerts"  
**Impact:** When the left-border accent appears on KPI cards, info panels, overdue tables, cash position, empty states, notes callouts, and page titles simultaneously, it stops communicating meaning and becomes visual wallpaper. It also creates an expectation of meaning (left = something) that isn't delivered consistently.

**Fix — replace with background tints:**

For `.db-kpi` variants (KPI accent stripe):
```css
/* Before */
.db-kpi {
  border-left: 3px solid #9ca3af;
}
.db-kpi.is-ar {
  border-left-color: #3f6fd6;
}

/* After — full top border or background tint */
.db-kpi {
  border-top: 3px solid #e5e7eb;
}
.db-kpi.is-ar {
  border-top-color: #3f6fd6;
  background: linear-gradient(180deg, rgba(63,111,214,.04) 0%, #fff 24px);
}
.db-kpi.is-ap {
  border-top-color: #d97706;
  background: linear-gradient(180deg, rgba(217,119,6,.04) 0%, #fff 24px);
}
.db-kpi.is-neg {
  border-top-color: #b42318;
  background: linear-gradient(180deg, rgba(180,35,24,.04) 0%, #fff 24px);
}
.db-kpi.is-pos {
  border-top-color: #16a34a;
  background: linear-gradient(180deg, rgba(22,163,74,.04) 0%, #fff 24px);
}
.db-kpi.is-net {
  border-top-color: #1e2130;
  background: linear-gradient(180deg, rgba(30,33,48,.04) 0%, #fff 24px);
}
```

For `.kv-note` callout — replace left border with full tinted background:
```css
/* Before */
.kv-note {
  border-left: 3px solid var(--brand-accent);
}

/* After */
.kv-note {
  background: #eef3fc;
  border: 1px solid rgba(63,111,214,.2);
  border-radius: 8px;
}
```

For `.db-empty-state`:
```css
/* Before */
.db-empty-state {
  border-left: 3px solid #1e2130;
}

/* After */
.db-empty-state {
  border: 1px solid #dfe5ee;
  border-radius: 8px;
  background: #f8fafc;
}
```

For `.db-panel-overdue`:
```css
/* Before */
.db-panel-overdue {
  border-left: 3px solid #dc2626;
}

/* After */
.db-panel-overdue {
  border-top: 3px solid #dc2626;
}
```

---

### P1 — Major

---

#### [P1-1] `#94a3b8` text on white backgrounds fails WCAG AA

**Location:** `static/css/base_anon.html` (`.auth-card-sub`, `.auth-page-footer`), `static/css/documents.css:121,306,369,391,481,559,672` (doc meta labels, status card headers, notes labels)  
**Category:** Accessibility  
**WCAG:** 1.4.3 Contrast (Minimum) — AA requires 4.5:1 for normal text  
**Impact:** `#94a3b8` on `#ffffff` = **~2.8:1 contrast** — fails AA by a wide margin. Affects subtitle text and metadata labels that users actively read when processing documents. Accountants using this under office lighting will strain.

**Fix — use `#6b7280` minimum for readable text on white:**
```css
/* Before (multiple files) */
.auth-card-sub { color: #94a3b8; }
.doc-meta-label { color: #94a3b8; }
.doc-status-card-header { color: #94a3b8; }

/* After — #6b7280 gives ~4.6:1 on white; use for ALL secondary text */
.auth-card-sub { color: #6b7280; }
.doc-meta-label { color: #6b7280; }
.doc-status-card-header { color: #6b7280; }
```

For truly decorative micro-labels (`.db-kpi-label` at 0.64rem / 800 weight), `#9ca3af` is acceptable as the label is reinforced by the metric value above it. But all *readable* text labels must be ≥ `#6b7280`.

---

#### [P1-2] Sidebar section labels fail WCAG AA on dark background

**Location:** `static/css/shell.css:72–79` — `.sidebar-section-label { color: #5c6480 }` on `background-color: #1e2130`  
**Category:** Accessibility  
**WCAG:** 1.4.3 — `#5c6480` on `#1e2130` ≈ **~2.9:1** (fails AA for text)  
**Impact:** Section labels like "FACTURACIÓN", "COMPRAS", "ORGANIZACIÓN" in the sidebar are how users navigate to modules. They're currently unreadable for users with reduced contrast sensitivity.

**Fix:**
```css
/* static/css/shell.css:76 */
.sidebar-section-label {
  color: #8892b0;  /* ~4.5:1 on #1e2130 */
}
```

---

#### [P1-3] Touch targets below 44px minimum

**Location:** `static/css/documents.css:524–528` (ribbon buttons), `static/css/shell.css:279–297` (subnav links)  
**Category:** Responsive / Accessibility  
**WCAG:** 2.5.5 Target Size  
**Impact:** `.dt-ribbon .btn { padding: 4px 10px; font-size: 0.8rem }` renders at ~30px height. Subnav links at 40px height. Both fail the 44px minimum. On tablet, users tapping quickly will mis-tap adjacent controls.

**Fix:**
```css
/* documents.css — ribbon buttons */
.dt-ribbon .btn {
  padding: 6px 10px;   /* was 4px — now ~34px; acceptable compromise given density */
  font-size: 0.8rem;
  border-radius: 4px;
  min-height: 32px;    /* explicit floor */
}

/* shell.css — subnav */
#subnav {
  height: 44px;        /* was 40px */
  min-height: 44px;
}
```

---

#### [P1-4] All 12 JS files loaded unconditionally on every page

**Location:** `templates/base.html:51–76`  
**Category:** Performance  
**Impact:** `document-form.js`, `item-picker.js`, `customer-picker.js`, `supplier-picker.js`, `payment-form.js`, `dashboard.js`, and `picker-keyboard.js` are all loaded on every page including reports, lists, and detail pages that use none of them. On a mobile connection this is ~200KB+ of unnecessary JS parsing on every navigation.

**Fix — use `{% block extra_js %}` conditional loading:**

Move picker/form scripts out of `base.html` and into the templates that need them:

```html
<!-- base.html: keep only truly universal scripts -->
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11/dist/sweetalert2.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.10/dist/htmx.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
<script src="{% static 'js/core.js' %}"></script>
<script src="{% static 'js/shell.js' %}"></script>
<script src="{% static 'js/alpine-components.js' %}"></script>
<script src="{% static 'js/app.js' %}"></script>
{% block extra_js %}{% endblock %}
```

Then in `invoice_form.html`, `quotation_form.html`, `sale_order_form.html`:
```html
{% block extra_js %}
<script src="{% static 'vendor/tom-select/tom-select.complete.min.js' %}"></script>
<script src="{% static 'js/init-tomselect.js' %}"></script>
<script src="{% static 'js/datatable.js' %}"></script>
<script src="{% static 'js/document-form.js' %}"></script>
<script src="{% static 'js/picker-base.js' %}"></script>
<script src="{% static 'js/item-picker.js' %}"></script>
<script src="{% static 'js/customer-picker.js' %}"></script>
<script src="{% static 'js/picker-keyboard.js' %}"></script>
{% endblock %}
```

---

#### [P1-5] `max-height` animation causes layout recalculation on every frame

**Location:** `static/css/documents.css:1102` — `.doc-notes-panel { transition: max-height .26s ease }`  
**Category:** Performance  
**Impact:** `max-height` transitions force the browser to recalculate layout on every animation frame. The correct technique (already used in `.doc-card-collapse`) is `grid-template-rows`.

**Fix — `static/css/documents.css:1102`:**
```css
/* Before */
.doc-notes-panel { max-height: 0; overflow: hidden; transition: max-height .26s ease; }
.doc-notes-acc.open .doc-notes-panel { max-height: 320px; }

/* After — same grid-rows trick used in doc-card-collapse */
.doc-notes-panel {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows .26s cubic-bezier(.4, 0, .2, 1);
}
.doc-notes-acc.open .doc-notes-panel {
  grid-template-rows: 1fr;
}
.doc-notes-panel-inner {
  min-height: 0;  /* required for 0fr to work */
  overflow: hidden;
}
```

Also apply same fix to `.doc-ribbon-body` in `documents.css:1173`.

---

#### [P1-6] `deprecated` `app_styles.html` still included in 20+ templates

**Location:** `templates/components/app_styles.html` (empty), referenced in 20+ templates  
**Category:** Performance / Maintenance  
**Impact:** Every include adds a Django template parsing step and HTTP request for an intentionally empty file. The comment in the file itself says to remove the includes. This is accumulated debt.

**Fix — remove includes from each template listed in the deprecation comment:**
```
accounts/dashboard, create_org, members, org_settings, team_form, teams, profile
core/module_detail, module_form, module_list
items/* 
purchases/* (incl. reports/*)
sales/* (incl. reports)
```

For each template:
```django
{# REMOVE this line: #}
{% include "components/app_styles.html" %}
```

Then delete `templates/components/app_styles.html`.

---

#### [P1-7] `body { overflow: hidden }` breaks Safari momentum scrolling

**Location:** `static/css/app.css:10–17`  
**Category:** Responsive / Performance  
**Impact:** The ERP shell pattern requires `overflow: hidden` on `html/body` with `overflow-y: auto` on `#main-content` for the fixed sidebar layout. Safari iOS does not apply momentum scrolling to non-body scrollers without `-webkit-overflow-scrolling: touch`. Users on iPad (common for SMB owners reviewing reports) get jerky scrolling.

**Fix — `static/css/app.css`:**
```css
#main-content {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;  /* add this */
  padding: 28px 28px;
}
```

---

#### [P1-8] Invoice detail action bar overflows with 7+ buttons

**Location:** `templates/sales/invoice_detail.html:22–85`  
**Category:** UX / Responsive  
**Impact:** An OVERDUE confirmed invoice shows simultaneously: Edit, Confirm, Delete, Register Payment, Print, PDF, Credit Note, Cancel — 8 buttons. On a 1280px screen this wraps. On mobile it becomes unusable. Users won't know which action is primary.

**Fix — establish a clear hierarchy:**

Primary (always visible, high emphasis):
- DRAFT: "Confirmar" (btn-brand), "Editar" (btn-outline-secondary)  
- CONFIRMED+: "Registrar pago" (btn-brand)

Secondary (btn-outline-secondary):
- Print, PDF, Marcar enviada

Destructive (collapse into "Más acciones" dropdown below 720px):
- Anular, Nota de Crédito

```html
<!-- Simplified action structure for invoice_detail.html -->
<div class="doc-action-row">
  <!-- Primary action (one per status) -->
  {% if invoice.status == "DRAFT" %}
    <form method="post" action="..." x-data x-on:submit.prevent="...">
      {% csrf_token %}
      <button class="btn btn-sm btn-brand"><i class="bi bi-check-circle me-1"></i>Confirmar</button>
    </form>
    <a href="..." class="btn btn-outline-secondary btn-sm">Editar</a>
  {% elif invoice.status in "CONFIRMED,SENT,OVERDUE" %}
    <button class="btn btn-sm btn-brand" data-bs-toggle="modal" data-bs-target="#payModal">
      <i class="bi bi-cash-coin me-1"></i>Registrar pago
    </button>
  {% endif %}

  <!-- Secondary -->
  <a href="..." class="btn btn-outline-secondary btn-sm"><i class="bi bi-printer me-1"></i>Imprimir</a>

  <!-- Overflow -->
  <div class="doc-action-overflow">
    {% if invoice.encf %}
      <a href="..." class="btn btn-outline-secondary btn-sm">PDF</a>
      <a href="..." class="btn btn-outline-warning btn-sm">Nota de Crédito</a>
    {% endif %}
    {% if can_cancel %}
      <form method="post" action="..." x-data x-on:submit.prevent="...">
        {% csrf_token %}
        <button class="btn btn-outline-danger btn-sm">Anular</button>
      </form>
    {% endif %}
  </div>

  <!-- "Más" dropdown (visible only <720px via .doc-action-more) -->
  <div class="dropdown doc-action-more">...</div>
</div>
```

---

#### [P1-9] Eyebrow labels on every section collapse visual hierarchy

**Location:** Systemic — `shell.css:72`, `components.css:461`, `documents.css:269`, `documents.css:365`, `documents.css:667`, `dashboard.css:10`, `slate-list.css:105`  
**Category:** Anti-Pattern  
**Impact:** `.sidebar-section-label`, `.app-card-head`, `.kv-card-title`, `.doc-meta-label`, `.doc-type-eyebrow`, `.db-panel-title`, `.db-section-label`, `.db-flow-label`, `.db-cash-eyebrow` — every surface uses the same small-caps uppercase pattern. When the pattern is everywhere, it communicates nothing. Hierarchy requires contrast between levels.

**Fix — differentiate by context:**

Keep uppercase tracking for:
- Sidebar section labels (navigation context, users scan these)
- Table column headers (data-dense context, scan-by-column)
- Status badge text

Replace with larger/heavier plain labels for:
- Card section titles (`.app-card-head`): use 0.75rem font-weight 700, no uppercase
- KPI labels (`.db-kpi-label`): current 0.64rem uppercase 800 is fine — it's so small it needs the caps for legibility
- Detail page field labels (`.kv-k`, `.doc-meta-label`): use 0.75rem / weight 500 / no uppercase

```css
/* components.css — app-card-head: drop uppercase */
.app-card-head {
  padding: 10px 14px 9px;
  border-bottom: 1px solid var(--hairline);
  font-size: .78rem;       /* was .7rem */
  font-weight: 700;
  /* text-transform: uppercase; REMOVE */
  /* letter-spacing: .04em;     REMOVE */
  color: #374151;           /* was var(--muted) — more contrast */
}
```

---

### P2 — Minor

---

#### [P2-1] Inline styles persist in templates

**Location:** `templates/sales/invoice_detail.html:9,394`, `templates/sales/customer_form.html:36,43`, `templates/accounts/dashboard.html` (various)  
**Category:** Theming / Maintainability  
**Impact:** `style="display:flex;align-items:center;gap:12px"`, `style="font-weight:500"`, `style="font-size:1.25rem;color:#1e2130"` bypass the token system and can't be updated globally.

**Fix — extract to utility classes or existing tokens:**
```html
<!-- invoice_detail.html:9 -->
<!-- Before: -->
<div style="display:flex;align-items:center;gap:12px">
<!-- After: use Bootstrap d-flex + gap-3 -->
<div class="d-flex align-items-center gap-3">

<!-- customer_form.html smart button -->
<!-- Before: -->
<div class="fw-bold lh-1 mb-1" style="font-size:1.25rem;color:#1e2130">
<!-- After: -->
<div class="fw-bold lh-1 mb-1 fs-5 link-brand">
```

---

#### [P2-2] Module accent color switching creates fragmented identity

**Location:** `static/css/app.css:89–129` — `[data-module="invoice"] { --module-accent: #10b981 }`, `[data-module="quotation"] { --module-accent: #f59e0b }`, etc.  
**Category:** Theming  
**Impact:** The invoice page is green. The quotation page is amber. The sale order page is indigo. The customer page is violet. Every major page uses a different primary color. For accountants moving between modules rapidly, this creates constant visual reorientation. A consistent brand accent with per-module secondary tints would be less disorienting.

**Recommendation:** Keep module accents for list page KPI icons and status stamps, but stop using `var(--module-accent)` for the `.doc-paper` top border (which is the first thing users see on every detail page). The `border-top: 4px solid var(--module-accent)` on `documents.css:72` changes the primary document color per module. Replace with `var(--brand-ink)` for consistency, keep module accent only for status stamps and icon tints.

---

#### [P2-3] `customer_form.html` smart buttons use inline styles instead of tokens

**Location:** `templates/sales/customer_form.html:34–46`  
**Category:** Theming  
**Impact:** The quick-stat cards (invoice count, payment count) are built with raw inline styles. They also miss the `.db-kpi` component entirely, duplicating its structure without the token system.

**Fix:**
```html
<!-- Before: -->
<div class="app-table-wrap px-3 py-2 text-center" style="min-width:80px;cursor:pointer">
  <div class="fw-bold lh-1 mb-1" style="font-size:1.25rem;color:#1e2130">{{ smart_buttons.invoice_count }}</div>
  <div class="text-muted" style="font-size:.65rem;text-transform:uppercase;letter-spacing:.04em">Facturas</div>
</div>

<!-- After — use db-kpi: -->
<div class="db-kpi is-ar">
  <span class="db-kpi-icon"><i class="bi bi-receipt"></i></span>
  <div class="db-kpi-body">
    <div class="db-kpi-value">{{ smart_buttons.invoice_count }}</div>
    <div class="db-kpi-label">{% trans "Facturas" %}</div>
  </div>
</div>
```

---

#### [P2-4] Typography floor too low — micro-labels below 10px

**Location:** `static/css/components.css:609` (`.app-filter-label: 9px`), `components.css:639` (`.app-metric-label: 9px`), `documents.css:269` (`.doc-type-eyebrow: 0.6rem = 9.6px`), `documents.css:365` (`.doc-meta-label: 0.62rem`), multiple others  
**Category:** Accessibility  
**Impact:** 9px text is genuinely unreadable on high-DPI screens at arm's length. DR accounting regulations require document fields to be clearly labeled. At 9px, a 50-year-old accountant with mild presbyopia cannot reliably read field labels.

**Fix — set a minimum floor of 11px (0.6875rem) for all visible text:**
```css
/* components.css */
.app-filter-label {
  font-size: 0.6875rem;  /* was 9px — minimum floor */
}
.app-metric-label {
  font-size: 0.6875rem;  /* was 9px */
}

/* documents.css */
.doc-type-eyebrow {
  font-size: 0.6875rem;  /* was 0.6rem */
}
.doc-meta-label {
  font-size: 0.7rem;     /* was 0.62rem */
}
```

---

#### [P2-5] Two separate CSS for the same role: `.app-metric-card` vs `.db-kpi`

**Location:** `static/css/components.css:617–638` (`.app-metric-card`) vs `components.css:316–454` (`.db-kpi`)  
**Category:** Theming / Maintainability  
**Impact:** Reports use `.app-metric-card` (print-tuned, icon-less, compact). Dashboard and list pages use `.db-kpi` (interactive, icon-tinted, mono). The CLAUDE.md documents this as intentional. However, the two systems have grown separately: `.app-metric-card` lacks `prefers-reduced-motion`, has no focus styles, and still uses `#111827` hardcoded. If reports ever become interactive (click to filter), this will be hard to extend.

**Recommendation:** No immediate change needed — this is documented intentionally. However, extract shared layout primitives (padding, border, border-radius, box-shadow) into a `.metric-base` mixin to share between both when the next report iteration happens.

---

#### [P2-6] Dashboard breadcrumbs empty — topbar title shows nothing on main page

**Location:** `templates/partials/_navbar.html:12–27`, `templates/accounts/dashboard.html`  
**Category:** UX  
**Impact:** The topbar renders an empty `<div class="topbar-title">` on the dashboard because no `breadcrumbs` context is passed. Users have no visual anchor in the topbar showing where they are.

**Fix — pass breadcrumbs from `DashboardView` OR show the org name in the topbar title always:**
```python
# apps/accounts/views.py — DashboardView.get_context_data()
context["breadcrumbs"] = [
    {"label": _("Dashboard"), "url": None}  # Current page — no link
]
```

Or in `_navbar.html`, add a fallback:
```html
<div class="topbar-title">
  {% if breadcrumbs %}
    <nav aria-label="breadcrumb">...</nav>
  {% elif page_title %}
    <span style="font-size:.9rem;color:#374151;font-weight:600">{{ page_title }}</span>
  {% endif %}
</div>
```

---

#### [P2-7] Auth page missing the left branding panel

**Location:** `templates/base_anon.html:5–23`  
**Category:** UX / Brand  
**Impact:** The CLAUDE.md documents a two-column auth layout with a left panel (400px, dark `#1e2130`, Cormorant Garamond headline, feature list, logo). The current template only renders the right panel. First-time users see a blank page with just a form — no brand communication, no product positioning.

**Fix — add the left panel back:**
```html
<!-- base_anon.html — add before <main class="auth-panel"> -->
<aside class="auth-brand d-none d-md-flex">
  <a href="/" class="auth-brand-logo">
    <img src="{% static 'img/sabsys-logo-white.png' %}" alt="SabSys" style="height:36px;width:auto;">
  </a>
  <div class="auth-brand-copy">
    <p class="auth-eyebrow">Sistema ERP</p>
    <h2 class="auth-brand-headline">Facturación electrónica para empresas dominicanas</h2>
    <ul class="auth-brand-features">
      <li><i class="bi bi-check2-circle"></i> Comprobantes fiscales electrónicos (e-CF)</li>
      <li><i class="bi bi-check2-circle"></i> Reportes 606/607 para la DGII</li>
      <li><i class="bi bi-check2-circle"></i> Gestión de compras y proveedores</li>
    </ul>
  </div>
  <p class="auth-brand-copy-foot">© {% now "Y" %} SabSys</p>
</aside>
```

Add to the `<style>` block:
```css
.auth-brand {
  width: 400px;
  min-width: 400px;
  background: #1e2130;
  color: #c9cdd8;
  display: flex;
  flex-direction: column;
  padding: 48px 40px;
  gap: 24px;
}
.auth-brand-headline {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 2rem;
  font-weight: 700;
  color: #fff;
  line-height: 1.15;
  letter-spacing: -.02em;
}
.auth-brand-features {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  font-size: .875rem;
  color: #9ba3bf;
}
.auth-brand-features i {
  color: #5b9af5;
  margin-right: 8px;
}
```

---

#### [P2-8] ITBIS rate badge reuses wrong semantic colors

**Location:** `templates/sales/invoice_detail.html:211–216`  
**Category:** UX / Theming  
**Impact:** RATE_18 uses `badge-overdue` (red) and RATE_16 uses `badge-confirmed` (blue). Red for an 18% tax rate implies an error/warning. Blue for 16% is arbitrary. These are neutral rate categories, not statuses.

**Fix:**
```html
<!-- Before: -->
{% if item.itbis_rate == 'RATE_18' %}
  <span class="badge-soft badge-overdue">{{ item.get_itbis_rate_display }}</span>
{% elif item.itbis_rate == 'RATE_16' %}
  <span class="badge-soft badge-confirmed">{{ item.get_itbis_rate_display }}</span>
{% else %}
  <span class="badge-soft badge-default">{{ item.get_itbis_rate_display }}</span>
{% endif %}

<!-- After: -->
<span class="badge-soft badge-default">{{ item.get_itbis_rate_display }}</span>
```

All ITBIS rates get neutral `badge-default`. The rate percentage already communicates the value — no color coding needed.

---

### P3 — Polish

---

#### [P3-1] "Próximamente" section in sidebar creates sense of incompleteness

**Location:** `templates/partials/_sidebar.html:144–160`  
**Category:** UX  
**Impact:** The greyed-out "Inventario" and "Recursos Humanos" items in every user's sidebar signal unfinished work on every page load. For paying customers, this is a constant reminder of what they're not getting.

**Fix:** Remove the "Próximamente" section entirely until modules are ready for public preview. If marketing purposes require it, gate it behind `is_staff`.

---

#### [P3-2] Sidebar toggle aria state not managed

**Location:** `templates/partials/_sidebar.html`, `templates/partials/_navbar.html:6`  
**Category:** Accessibility  
**Impact:** The hamburger toggle button (`class="topbar-toggle"`) has `aria-label="Toggle sidebar"` but no `aria-expanded` attribute. Screen reader users can't tell if the sidebar is open or closed.

**Fix — `templates/partials/_navbar.html:6`:**
```html
<button class="topbar-toggle"
        onclick="toggleSidebar()"
        id="sidebar-toggle-btn"
        aria-label="{% trans 'Toggle sidebar' %}"
        aria-expanded="false"
        aria-controls="sidebar">
  <i class="bi bi-list"></i>
</button>
```

Then in `static/js/shell.js`, update `toggleSidebar()` to toggle `aria-expanded`:
```js
function toggleSidebar() {
  // ... existing toggle logic ...
  const btn = document.getElementById('sidebar-toggle-btn');
  if (btn) {
    btn.setAttribute('aria-expanded', 
      document.body.classList.contains('sidebar-open') ? 'true' : 'false'
    );
  }
}
```

---

#### [P3-3] Sidebar backdrop uses inline onclick

**Location:** `templates/partials/_sidebar.html:215`  
**Category:** Accessibility  
**Impact:** `<div id="sidebar-backdrop" onclick="toggleSidebar()">` — a non-interactive `<div>` with an inline onclick handler. Not reachable by keyboard, not announced by screen readers.

**Fix:**
```html
<!-- Before: -->
<div id="sidebar-backdrop" onclick="toggleSidebar()"></div>

<!-- After: -->
<button id="sidebar-backdrop"
        onclick="toggleSidebar()"
        aria-label="{% trans 'Cerrar menú' %}"
        tabindex="-1">
</button>
```

`tabindex="-1"` keeps it out of tab order (intentional — it's a visual dismiss target), but makes it keyboard-accessible when focused programmatically.

---

#### [P3-4] `doc-notes-ribbon` CSS includes an inline comment with HTML markup

**Location:** `static/css/documents.css:1119–1135`  
**Category:** Maintainability  
**Impact:** A 15-line HTML template example is embedded as a CSS comment. This is the right intent (document the alternative) but it belongs in a `.md` file or the template itself as a `{% comment %}`.

---

#### [P3-5] `invoice_form.html` inline `width:360px` on totals card

**Location:** `templates/sales/invoice_form.html:86`  
**Category:** Responsive  
**Impact:** `<div class="doc-totals-card" style="width:360px">` bypasses the CSS `.doc-totals-card` responsive handling. On viewports below 400px the card can overflow.

**Fix:**
```html
<!-- Before: -->
<div class="doc-totals-card" style="width:360px">

<!-- After: remove inline style — CSS already handles width -->
<div class="doc-totals-card">
```

The `.doc-bottom-grid { grid-template-columns: 1fr 360px }` in `documents.css:879` already constrains the totals card width at desktop. The `@media (max-width: 767.98px)` rule collapses to `1fr`. The inline style fights both.

---

## Patterns & Systemic Issues

1. **Side-stripe borders as the default accent** — appears in 8 separate CSS components. The pattern was added once and then copied. Every new card/panel that needed "something visual" got a left border.

2. **Hardcoded colors outside the token system** — `#94a3b8`, `#6b7280`, `#1e2130`, `#111827`, `#0f172a`, `#1e293b`, `#334155` appear across all 5 CSS files. The token system (`--brand-ink`, `--muted`, etc.) is defined but adoption is ~40%. New CSS goes into tokens; old CSS hasn't been migrated.

3. **Two parallel sticky-bar systems** — `.app-form-bar` (documented in components.css) and `.form-sticky-bar` (used in 4 templates, no CSS). The templates were written against an older or different spec.

4. **Eyebrow label pattern applied universally** — every section/card/panel uses the same `text-transform: uppercase; letter-spacing: .04–.14em; font-size: .62–.7rem` pattern for its heading. Without variation, hierarchy disappears.

5. **`#94a3b8` as the default "muted" text color** — used for secondary text, labels, and metadata throughout, but it consistently fails contrast on white. The correct muted text floor is `#6b7280` (4.6:1 on white).

---

## Positive Findings

1. **Typography pair is excellent** — Cormorant Garamond (display), Manrope (body), IBM Plex Mono (numerics) is a strong, distinctive choice that differentiates from generic SaaS. The font-feature-settings `"tnum"` on monetary values is professional.

2. **Module accent CSS variable system** — per-module `--module-accent` with four semantic sub-tokens (`dark`, `subtle`, `border`) is architecturally clean and extensible.

3. **Status badge system is complete and semantic** — `status_badge.html` covers all 11 document states. The `badge-soft` pattern with background tints is well-executed.

4. **`@media (prefers-reduced-motion)` in multiple files** — `components.css:446`, `documents.css:149`, `dashboard.css:545`. Good habit.

5. **KPI card component is reusable and well-documented** — `_kpi_cards.html` with full context API documentation in the comment block. Easy for new pages to adopt.

6. **Document form chrome is excellent** — `.doc-order-card` with collapsible head (grid-template-rows animation), `.doc-lines-card`, `.doc-totals-card` form a coherent, data-dense form pattern. The sticky totals card at the bottom-right with real-time calculation is UX best practice for invoice entry.

7. **`dt-slate` opt-in skin** — the opt-in scoped CSS for the list skin avoids global style pollution. Smart pattern.

8. **`suspend_recompute()` context manager for bulk saves** — prevents N+1 recompute. This is the kind of detail that makes the app feel fast.

9. **`bool` toggle card** — `.boolean-status-card` is a well-designed replacement for a boring checkbox. The focus-visible ring, checked state transitions, and embedded badge all work correctly.

---

## Recommended Actions (Priority Order)

1. **[P0] `/impeccable harden`** — Fix broken `.form-sticky-bar` → `.app-form-bar` mismatch in 4 templates (customer, supplier, item, payment-term forms)
2. **[P0] `/impeccable colorize`** — Replace side-stripe `border-left` accents with background tints across all 8 components
3. **[P0] `/impeccable harden`** — Deduplicate `--warn` token (remove first definition at `components.css:101`)
4. **[P1] `/impeccable adapt`** — Fix `#94a3b8` contrast failures on white (change to `#6b7280` minimum)
5. **[P1] `/impeccable adapt`** — Fix sidebar section label contrast on dark background (`#5c6480` → `#8892b0`)
6. **[P1] `/impeccable adapt`** — Increase touch targets for ribbon buttons (4px → 6px padding) and subnav (40px → 44px)
7. **[P1] `/impeccable optimize`** — Move 8 JS files out of `base.html` into conditional per-page loading
8. **[P1] `/impeccable optimize`** — Replace `max-height` animation with `grid-template-rows` in `.doc-notes-panel`
9. **[P1] `/impeccable distill`** — Remove deprecated `app_styles.html` includes from 20+ templates
10. **[P1] `/impeccable typeset`** — Differentiate eyebrow label hierarchy (keep for nav/table-headers, replace for card titles)
11. **[P2] `/impeccable clarify`** — Fix ITBIS rate badge semantics (red for 18% reads as error)
12. **[P2] `/impeccable layout`** — Add auth left-panel branding back to `base_anon.html`
13. **[P3] `/impeccable polish`** — All remaining P3 fixes (aria-expanded, backdrop button, inline styles, `width:360px`)

After all fixes, re-run `/impeccable audit` to verify score improvement.

---

*You can ask me to run these one at a time, all at once, or in any order you prefer.*

*Re-run `/impeccable audit` after fixes to see your score improve.*
