# Reports Templates Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply a consistent "Professional/Financial" design language across all 7 report detail templates by rewriting shared CSS, updating the filter panel partial, and redesigning each template.

**Architecture:** All styles centralised in `report_shared_styles.html` (included by every detail template via `{% block extra_css %}`). The filter panel partial is updated in-place. The hub page `reports.html` is untouched. No Python, no migrations.

**Tech Stack:** Django templates, Bootstrap 5, Bootstrap Icons

---

## File Map

| Action | File |
|---|---|
| Rewrite | `templates/invoices/partials/report_shared_styles.html` |
| Rewrite | `templates/invoices/partials/report_filter_panel.html` |
| Rewrite | `templates/invoices/report_ncf_type.html` |
| Rewrite | `templates/invoices/report_itbis.html` |
| Rewrite | `templates/invoices/report_aging.html` |
| Rewrite | `templates/invoices/report_sales_period.html` |
| Rewrite | `templates/invoices/report_collections.html` |
| Rewrite | `templates/invoices/report_statement.html` |
| Rewrite | `templates/invoices/report_invoices_by_customer.html` |
| No change | `templates/invoices/reports.html` |

---

## CSS Classes Introduced

| Class | Purpose |
|---|---|
| `.rpt-header` | Flex page header with `border-bottom: 2px solid #1e2130` |
| `.rpt-header-title` | `h1` inside header, `fw-700 1.2rem` |
| `.rpt-header-sub` | Subtitle below title, `0.8rem #6b7280` |
| `.rpt-header-actions` | Flex group for back + print buttons |
| `.rpt-filter-panel` | Gray filter box, `#f9fafb bg, #e5e7eb border, 8px radius` |
| `.rpt-filter-label` | "Filtros" uppercase label inside panel |
| `.rpt-metric-card` | KPI card: centered, `border #e5e7eb, radius 6px, white bg` |
| `.rpt-metric-value` | `fw-700 1.35rem` number in card |
| `.rpt-metric-label` | `9px uppercase #6b7280` label under value |
| `.rpt-table-wrap` | Table wrapper: `border #e5e7eb, radius 8px, overflow hidden` |
| `.rpt-table-wrap thead th` | `#f9fafb bg, 0.7rem uppercase #6b7280` |
| `.rpt-table-wrap tfoot` | `#f9fafb bg, border-top 2px solid #1e2130, fw-700` |
| `.badge-soft` | Status badge base — **name unchanged** from current system |
| `.customer-block` | Customer info row — **name unchanged** from current system |
| `.customer-avatar` | Avatar circle — **name unchanged** from current system |

---

## Task 1: Rewrite report_shared_styles.html

**Files:**
- Rewrite: `templates/invoices/partials/report_shared_styles.html`

- [ ] **Step 1: Overwrite the file with the new CSS system**

```html
<style>
/* ── Print ───────────────────────────────────────────────── */
.print-header { display: none; }
@media print {
  @page { size: A4 landscape; }
  .no-print { display: none !important; }
  .print-header { display: block !important; }
  .rpt-table-wrap { border: 1px solid #dee2e6 !important; box-shadow: none !important; }
  .rpt-metric-card { border: 1px solid #dee2e6 !important; }
  .badge-soft { background: none !important; border: none !important; padding: 0 !important; color: inherit !important; font-weight: 600; }
}

/* ── Page header ─────────────────────────────────────────── */
.rpt-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding-bottom: 14px;
  border-bottom: 2px solid #1e2130;
  margin-bottom: 1.25rem;
  flex-wrap: wrap;
  gap: .5rem;
}
.rpt-header-title { font-size: 1.2rem; font-weight: 700; color: #111827; letter-spacing: -.2px; margin: 0; }
.rpt-header-sub { font-size: .8rem; color: #6b7280; margin: 3px 0 0; }
.rpt-header-actions { display: flex; gap: .5rem; flex-shrink: 0; }

/* ── Filter panel ────────────────────────────────────────── */
.rpt-filter-panel {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 1rem;
}
.rpt-filter-label {
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .08em;
  color: #9ca3af;
  margin-bottom: 10px;
}

/* ── Metric cards ────────────────────────────────────────── */
.rpt-metric-card {
  text-align: center;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fff;
}
.rpt-metric-value {
  font-size: 1.35rem;
  font-weight: 700;
  line-height: 1.2;
  color: #111827;
}
.rpt-metric-label {
  font-size: 9px;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: .05em;
  margin-top: 3px;
}

/* ── Table wrapper ───────────────────────────────────────── */
.rpt-table-wrap {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}
.rpt-table-wrap .table { margin-bottom: 0; font-size: .875rem; }
.rpt-table-wrap thead th {
  background: #f9fafb;
  font-size: .7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .04em;
  color: #6b7280;
  border-bottom: 1px solid #e5e7eb;
  padding-top: .65rem;
  padding-bottom: .65rem;
}
.rpt-table-wrap tfoot td,
.rpt-table-wrap tfoot th {
  background: #f9fafb;
  border-top: 2px solid #1e2130;
  font-weight: 700;
}
.rpt-table-wrap tbody tr:nth-child(even) { background: #fafafa; }

/* ── Status badges (class names unchanged) ───────────────── */
.badge-soft {
  font-size: .72rem;
  font-weight: 500;
  padding: .3em .65em;
  border-radius: 6px;
  display: inline-block;
}
.badge-confirmed { background: #E6F1FB; color: #185FA5; }
.badge-sent      { background: #D1ECF1; color: #0C5460; }
.badge-paid      { background: #D1E7DD; color: #0A6640; }
.badge-overdue   { background: #F8D7DA; color: #842029; }
.badge-cancelled { background: #E9ECEF; color: #495057; }
.badge-default   { background: #E9ECEF; color: #495057; }
.badge-invoice   { background: #E9ECEF; color: #495057; }
.badge-payment   { background: #D1E7DD; color: #0A6640; }

/* ── Customer block (class names unchanged) ──────────────── */
.customer-block {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: .85rem 1.1rem;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  background: #fff;
  margin-bottom: 1rem;
}
.customer-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #f3f4f6;
  color: #374151;
  font-weight: 600;
  font-size: .9rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
</style>
```

- [ ] **Step 2: Verify the file saved correctly**

```bash
python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Commit**

```bash
git add templates/invoices/partials/report_shared_styles.html
git commit -m "style: rewrite report_shared_styles.html with unified CSS system"
```

---

## Task 2: Rewrite report_filter_panel.html

**Files:**
- Rewrite: `templates/invoices/partials/report_filter_panel.html`

Key changes:
- `div.card.border.shadow-none` → `div.rpt-filter-panel`
- "Filtros" `<p>` → `<p class="rpt-filter-label">`
- Submit button: `btn btn-{{ btn_color }} btn-sm` → `btn btn-dark btn-sm`
- Add `month_required` flag support for `report_ncf_type` (required month select)

- [ ] **Step 1: Overwrite the file**

```html
<div class="rpt-filter-panel no-print">
  <p class="rpt-filter-label">Filtros</p>
  <form method="get" class="row g-3 align-items-end">

    {% if show_customer %}
    <div class="col-md-4">
      <label class="form-label small fw-semibold">Cliente</label>
      <select name="customer" class="form-select form-select-sm"
        {% if customer_required %}required
        oninvalid="this.setCustomValidity('Debe seleccionar un cliente.')"
        onchange="this.setCustomValidity('')"{% endif %}>
        <option value="">{% if customer_required %}— Seleccionar —{% else %}— Todos los clientes —{% endif %}</option>
        {% for c in customers %}
        <option value="{{ c.pk }}"{% if c.pk|stringformat:"s" == customer_id %} selected{% endif %}>{{ c.name }}</option>
        {% endfor %}
      </select>
    </div>
    {% endif %}

    {% if show_dates %}
    <div class="col-md-3">
      <label class="form-label small fw-semibold">Desde</label>
      <input type="date" name="date_from" value="{{ date_from }}"
             class="form-control form-control-sm" required
             oninvalid="this.setCustomValidity('Este campo es obligatorio.')"
             oninput="this.setCustomValidity('')">
    </div>
    <div class="col-md-3">
      <label class="form-label small fw-semibold">Hasta</label>
      <input type="date" name="date_to" value="{{ date_to }}"
             class="form-control form-control-sm" required
             oninvalid="this.setCustomValidity('Este campo es obligatorio.')"
             oninput="this.setCustomValidity('')">
    </div>
    {% endif %}

    {% if show_year %}
    <div class="col-md-3">
      <label class="form-label small fw-semibold">Año</label>
      <input type="number" name="year" value="{{ year_input|default:today.year }}"
             min="2020" max="2099"
             class="form-control form-control-sm" required
             oninvalid="this.setCustomValidity('Este campo es obligatorio.')"
             oninput="this.setCustomValidity('')">
    </div>
    {% endif %}

    {% if show_month %}
    <div class="col-md-3">
      <label class="form-label small fw-semibold">
        Mes{% if not month_required %} <span class="text-muted fw-normal">(opcional)</span>{% endif %}
      </label>
      <select name="month" class="form-select form-select-sm"
        {% if month_required %}required
        oninvalid="this.setCustomValidity('Debe seleccionar un mes.')"
        onchange="this.setCustomValidity('')"{% endif %}>
        <option value="">{% if month_required %}— Seleccionar —{% else %}— Todos —{% endif %}</option>
        <option value="1"  {% if month_input == "1"  %}selected{% endif %}>Enero</option>
        <option value="2"  {% if month_input == "2"  %}selected{% endif %}>Febrero</option>
        <option value="3"  {% if month_input == "3"  %}selected{% endif %}>Marzo</option>
        <option value="4"  {% if month_input == "4"  %}selected{% endif %}>Abril</option>
        <option value="5"  {% if month_input == "5"  %}selected{% endif %}>Mayo</option>
        <option value="6"  {% if month_input == "6"  %}selected{% endif %}>Junio</option>
        <option value="7"  {% if month_input == "7"  %}selected{% endif %}>Julio</option>
        <option value="8"  {% if month_input == "8"  %}selected{% endif %}>Agosto</option>
        <option value="9"  {% if month_input == "9"  %}selected{% endif %}>Septiembre</option>
        <option value="10" {% if month_input == "10" %}selected{% endif %}>Octubre</option>
        <option value="11" {% if month_input == "11" %}selected{% endif %}>Noviembre</option>
        <option value="12" {% if month_input == "12" %}selected{% endif %}>Diciembre</option>
      </select>
    </div>
    {% endif %}

    <div class="col-md-2">
      <button type="submit" class="btn btn-dark btn-sm w-100">
        <i class="bi bi-search me-1"></i>Consultar
      </button>
    </div>

  </form>
</div>
```

- [ ] **Step 2: Verify**

```bash
python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Commit**

```bash
git add templates/invoices/partials/report_filter_panel.html
git commit -m "style: update report_filter_panel.html — new rpt-filter-panel style, dark submit btn, month_required flag"
```

---

## Task 3: Redesign report_ncf_type.html

**Files:**
- Rewrite: `templates/invoices/report_ncf_type.html`

Changes: add shared styles include, replace inline filter form with partial (`month_required=True`), new `.rpt-header`, `bg-light` pills → `.rpt-metric-card`, `card shadow-sm` table → `.rpt-table-wrap`.

- [ ] **Step 1: Overwrite the file**

```django
{% extends "base.html" %}
{% load humanize %}

{% block title %}Ventas por Tipo de Comprobante{% endblock %}

{% block extra_css %}
{% include "invoices/partials/report_shared_styles.html" %}
{% endblock %}

{% block content %}

{# ── Print-only document header ───────────────────────────────────────────── #}
<div class="print-header">
  <p class="print-org">{{ organization.name }}</p>
  <h1 class="print-title">Ventas por Tipo de Comprobante</h1>
  {% if month and year %}
  <p class="print-meta">{{ today|date:"F" }} {{ year }}</p>
  {% endif %}
</div>

{# ── Screen header ────────────────────────────────────────────────────────── #}
<div class="rpt-header no-print">
  <div>
    <h1 class="rpt-header-title">Ventas por Tipo de Comprobante</h1>
    {% if month and year %}<p class="rpt-header-sub">{{ today|date:"F" }} {{ year }}</p>{% endif %}
  </div>
  <div class="rpt-header-actions">
    <a href="{% url 'invoices:reports' %}" class="btn btn-outline-secondary btn-sm">
      <i class="bi bi-arrow-left me-1"></i>Reportes
    </a>
    {% if rows %}
    <button type="button" class="btn btn-outline-secondary btn-sm" onclick="window.print()">
      <i class="bi bi-printer me-1"></i>Imprimir
    </button>
    {% endif %}
  </div>
</div>

{# ── Filter form ──────────────────────────────────────────────────────────── #}
{% include "invoices/partials/report_filter_panel.html" with show_year=True show_month=True month_required=True %}

{% if month and year %}
{% if rows %}

{# ── Summary metric cards ──────────────────────────────────────────────────── #}
<div class="row g-2 mb-3 no-print">
  <div class="col-6 col-sm-3">
    <div class="rpt-metric-card">
      <div class="rpt-metric-value">{{ rows|length }}</div>
      <div class="rpt-metric-label">Tipos usados</div>
    </div>
  </div>
  <div class="col-6 col-sm-3">
    <div class="rpt-metric-card">
      <div class="rpt-metric-value">{{ total_count }}</div>
      <div class="rpt-metric-label">Documentos</div>
    </div>
  </div>
  <div class="col-6 col-sm-3">
    <div class="rpt-metric-card">
      <div class="rpt-metric-value text-danger">{{ totals.itbis|floatformat:2|intcomma }}</div>
      <div class="rpt-metric-label">Total ITBIS</div>
    </div>
  </div>
  <div class="col-6 col-sm-3">
    <div class="rpt-metric-card">
      <div class="rpt-metric-value text-success">{{ totals.total|floatformat:2|intcomma }}</div>
      <div class="rpt-metric-label">Total facturado</div>
    </div>
  </div>
</div>

{# ── Table ─────────────────────────────────────────────────────────────────── #}
<div class="rpt-table-wrap">
  <div class="table-responsive">
    <table class="table table-hover table-sm mb-0">
      <thead>
        <tr>
          <th style="width:5%">#</th>
          <th>Tipo de Comprobante</th>
          <th class="text-center">Documentos</th>
          <th class="text-end">Subtotal</th>
          <th class="text-end text-danger">ITBIS</th>
          <th class="text-end">Total</th>
        </tr>
      </thead>
      <tbody>
        {% for row in rows %}
        <tr>
          <td class="text-muted font-monospace">{{ row.ncf_type|stringformat:"02d" }}</td>
          <td>{{ row.ncf_label }}</td>
          <td class="text-center">{{ row.count }}</td>
          <td class="text-end font-monospace">{{ row.subtotal|floatformat:2|intcomma }}</td>
          <td class="text-end font-monospace text-danger">{{ row.itbis|floatformat:2|intcomma }}</td>
          <td class="text-end font-monospace fw-semibold">{{ row.total|floatformat:2|intcomma }}</td>
        </tr>
        {% endfor %}
      </tbody>
      <tfoot>
        <tr>
          <td colspan="2">Total</td>
          <td class="text-center">{{ total_count }}</td>
          <td class="text-end font-monospace">{{ totals.subtotal|floatformat:2|intcomma }}</td>
          <td class="text-end font-monospace text-danger">{{ totals.itbis|floatformat:2|intcomma }}</td>
          <td class="text-end font-monospace">{{ totals.total|floatformat:2|intcomma }}</td>
        </tr>
      </tfoot>
    </table>
  </div>
</div>

{% else %}
<div class="alert alert-info">
  <i class="bi bi-info-circle me-1"></i>
  No hay facturas registradas para el mes {{ month }}/{{ year }}.
</div>
{% endif %}
{% endif %}

{% endblock %}
```

- [ ] **Step 2: Start dev server and verify page loads**

```bash
python manage.py runserver
```

Navigate to Reports → Ventas por Tipo de Comprobante. Verify: page loads with no 500 error, header has dark bottom border, filter panel is gray box with dark "Consultar" button, month select shows "— Seleccionar —" (required).

- [ ] **Step 3: Commit**

```bash
git add templates/invoices/report_ncf_type.html
git commit -m "style: redesign report_ncf_type — rpt-header, rpt-metric-card, rpt-table-wrap, use filter partial"
```

---

## Task 4: Redesign report_itbis.html

**Files:**
- Rewrite: `templates/invoices/report_itbis.html`

Changes: same as Task 3 but month is optional (no `month_required`). `show_year=True show_month=True` without `month_required`.

- [ ] **Step 1: Overwrite the file**

```django
{% extends "base.html" %}
{% load humanize %}

{% block title %}Resumen de ITBIS{% endblock %}

{% block extra_css %}
{% include "invoices/partials/report_shared_styles.html" %}
{% endblock %}

{% block content %}

{# ── Print-only document header ───────────────────────────────────────────── #}
<div class="print-header">
  <p class="print-org">{{ organization.name }}</p>
  <h1 class="print-title">Resumen de ITBIS</h1>
  {% if year %}
  <p class="print-meta">
    {% if month %}{{ rows.0.period|date:"F Y" }}{% else %}Año {{ year }}{% endif %}
  </p>
  {% endif %}
</div>

{# ── Screen header ────────────────────────────────────────────────────────── #}
<div class="rpt-header no-print">
  <div>
    <h1 class="rpt-header-title">Resumen de ITBIS</h1>
    {% if year %}<p class="rpt-header-sub">{% if month %}{{ rows.0.period|date:"F Y" }}{% else %}Año {{ year }}{% endif %}</p>{% endif %}
  </div>
  <div class="rpt-header-actions">
    <a href="{% url 'invoices:reports' %}" class="btn btn-outline-secondary btn-sm">
      <i class="bi bi-arrow-left me-1"></i>Reportes
    </a>
    {% if rows %}
    <button type="button" class="btn btn-outline-secondary btn-sm" onclick="window.print()">
      <i class="bi bi-printer me-1"></i>Imprimir
    </button>
    {% endif %}
  </div>
</div>

{# ── Filter form ──────────────────────────────────────────────────────────── #}
{% include "invoices/partials/report_filter_panel.html" with show_year=True show_month=True %}

{% if year %}
{% if rows %}

{# ── Summary metric cards ──────────────────────────────────────────────────── #}
<div class="row g-2 mb-3 no-print">
  <div class="col-6 col-sm-3">
    <div class="rpt-metric-card">
      <div class="rpt-metric-value">{{ totals.total_base|floatformat:2|intcomma }}</div>
      <div class="rpt-metric-label">Total base</div>
    </div>
  </div>
  <div class="col-6 col-sm-3">
    <div class="rpt-metric-card">
      <div class="rpt-metric-value text-warning">{{ totals.itbis_16|floatformat:2|intcomma }}</div>
      <div class="rpt-metric-label">ITBIS 16%</div>
    </div>
  </div>
  <div class="col-6 col-sm-3">
    <div class="rpt-metric-card">
      <div class="rpt-metric-value text-danger">{{ totals.itbis_18|floatformat:2|intcomma }}</div>
      <div class="rpt-metric-label">ITBIS 18%</div>
    </div>
  </div>
  <div class="col-6 col-sm-3">
    <div class="rpt-metric-card">
      <div class="rpt-metric-value text-danger">{{ totals.total_itbis|floatformat:2|intcomma }}</div>
      <div class="rpt-metric-label">Total ITBIS</div>
    </div>
  </div>
</div>

{# ── Table ─────────────────────────────────────────────────────────────────── #}
<div class="rpt-table-wrap">
  <div class="table-responsive">
    <table class="table table-hover table-sm mb-0">
      <thead>
        <tr>
          <th>{% if by_day %}Día{% else %}Mes{% endif %}</th>
          <th class="text-end">Exento / Tasa 0%</th>
          <th class="text-end">Base Grav. 16%</th>
          <th class="text-end text-warning">ITBIS 16%</th>
          <th class="text-end">Base Grav. 18%</th>
          <th class="text-end text-danger">ITBIS 18%</th>
          <th class="text-end">Total Base</th>
          <th class="text-end text-danger">Total ITBIS</th>
          <th class="text-end">Total</th>
        </tr>
      </thead>
      <tbody>
        {% for row in rows %}
        <tr>
          <td class="fw-semibold">
            {% if by_day %}{{ row.period|date:"d/m/Y" }}{% else %}{{ row.period|date:"F Y" }}{% endif %}
          </td>
          <td class="text-end font-monospace text-muted">
            {% if row.exempt %}{{ row.exempt|floatformat:2|intcomma }}{% else %}<span class="text-muted">—</span>{% endif %}
          </td>
          <td class="text-end font-monospace">
            {% if row.base_16 %}{{ row.base_16|floatformat:2|intcomma }}{% else %}<span class="text-muted">—</span>{% endif %}
          </td>
          <td class="text-end font-monospace text-warning">
            {% if row.itbis_16 %}{{ row.itbis_16|floatformat:2|intcomma }}{% else %}<span class="text-muted">—</span>{% endif %}
          </td>
          <td class="text-end font-monospace">
            {% if row.base_18 %}{{ row.base_18|floatformat:2|intcomma }}{% else %}<span class="text-muted">—</span>{% endif %}
          </td>
          <td class="text-end font-monospace text-danger">
            {% if row.itbis_18 %}{{ row.itbis_18|floatformat:2|intcomma }}{% else %}<span class="text-muted">—</span>{% endif %}
          </td>
          <td class="text-end font-monospace">{{ row.total_base|floatformat:2|intcomma }}</td>
          <td class="text-end font-monospace text-danger">{{ row.total_itbis|floatformat:2|intcomma }}</td>
          <td class="text-end font-monospace fw-semibold">{{ row.grand_total|floatformat:2|intcomma }}</td>
        </tr>
        {% endfor %}
      </tbody>
      <tfoot>
        <tr>
          <td>Total</td>
          <td class="text-end font-monospace text-muted">{{ totals.exempt|floatformat:2|intcomma }}</td>
          <td class="text-end font-monospace">{{ totals.base_16|floatformat:2|intcomma }}</td>
          <td class="text-end font-monospace text-warning">{{ totals.itbis_16|floatformat:2|intcomma }}</td>
          <td class="text-end font-monospace">{{ totals.base_18|floatformat:2|intcomma }}</td>
          <td class="text-end font-monospace text-danger">{{ totals.itbis_18|floatformat:2|intcomma }}</td>
          <td class="text-end font-monospace">{{ totals.total_base|floatformat:2|intcomma }}</td>
          <td class="text-end font-monospace text-danger">{{ totals.total_itbis|floatformat:2|intcomma }}</td>
          <td class="text-end font-monospace">{{ totals.grand_total|floatformat:2|intcomma }}</td>
        </tr>
      </tfoot>
    </table>
  </div>
</div>

{% else %}
<div class="alert alert-info">
  <i class="bi bi-info-circle me-1"></i>
  {% if month %}
    No hay facturas con ITBIS registradas para el mes {{ month }}/{{ year }}.
  {% else %}
    No hay facturas con ITBIS registradas para el año {{ year }}.
  {% endif %}
</div>
{% endif %}
{% endif %}

{% endblock %}
```

- [ ] **Step 2: Verify page loads**

Navigate to Reports → Resumen de ITBIS. Verify: month select shows "— Todos —" (optional, no required attribute), header has dark underline, filter panel uses dark Consultar button.

- [ ] **Step 3: Commit**

```bash
git add templates/invoices/report_itbis.html
git commit -m "style: redesign report_itbis — rpt-header, rpt-metric-card, rpt-table-wrap, use filter partial"
```

---

## Task 5: Redesign report_aging.html

**Files:**
- Rewrite: `templates/invoices/report_aging.html`

Changes: add shared styles include, new `.rpt-header`, replace `card shadow-sm` table with `.rpt-table-wrap`, remove `table-light` from thead/tfoot (handled by `.rpt-table-wrap` CSS).

- [ ] **Step 1: Overwrite the file**

```django
{% extends "base.html" %}
{% load i18n humanize %}

{% block title %}{% trans "Antigüedad de Cuentas por Cobrar" %}{% endblock %}

{% block extra_css %}
{% include "invoices/partials/report_shared_styles.html" %}
{% endblock %}

{% block content %}

{# ── Print-only document header ───────────────────────────────────────────── #}
<div class="print-header">
  <p class="print-org">{{ organization.name }}</p>
  <h1 class="print-title">{% trans "Antigüedad de Cuentas por Cobrar" %}</h1>
  <p class="print-meta">
    {% if selected_customer %}{{ selected_customer.name }} · {% endif %}{% trans "Al" %} {{ today|date:"d/m/Y" }}
  </p>
</div>

{# ── Screen header ────────────────────────────────────────────────────────── #}
<div class="rpt-header no-print">
  <div>
    <h1 class="rpt-header-title">{% trans "Antigüedad de Cuentas por Cobrar" %}</h1>
    <p class="rpt-header-sub">
      {% if selected_customer %}{{ selected_customer.name }} · {% endif %}{% trans "Al" %} {{ today|date:"d/m/Y" }}
    </p>
  </div>
  <div class="rpt-header-actions">
    <a href="{% url 'invoices:reports' %}" class="btn btn-outline-secondary btn-sm">
      <i class="bi bi-arrow-left me-1"></i>{% trans "Reportes" %}
    </a>
    <button type="button" class="btn btn-outline-secondary btn-sm" onclick="window.print()">
      <i class="bi bi-printer me-1"></i>{% trans "Imprimir" %}
    </button>
  </div>
</div>

{# ── Filter form ──────────────────────────────────────────────────────────── #}
{% include "invoices/partials/report_filter_panel.html" with show_customer=True %}
{% if selected_customer %}
<div class="text-end mb-3 no-print" style="margin-top:-.75rem">
  <a href="{% url 'invoices:report_aging' %}" class="small text-muted text-decoration-none">
    <i class="bi bi-x me-1"></i>Ver todos los clientes
  </a>
</div>
{% endif %}

{% if rows %}
<div class="rpt-table-wrap">
  <div class="table-responsive">
    <table class="table table-hover table-sm mb-0">
      <thead>
        <tr>
          <th>{% trans "Cliente" %}</th>
          {% for bh in bucket_headers %}
          <th class="text-end {{ bh.css }}">{{ bh.label }}</th>
          {% endfor %}
          <th class="text-end">{% trans "Total" %}</th>
        </tr>
      </thead>
      <tbody>
        {% for row in rows %}
        <tr>
          <td>
            <a href="{% url 'invoices:customer_detail' row.customer.pk %}"
               class="text-decoration-none fw-semibold">
              {{ row.customer.name }}
            </a>
          </td>
          {% for bc in row.bucket_cells %}
          <td class="text-end font-monospace {{ bc.css }}">
            {% if bc.amount %}{{ bc.amount|floatformat:2|intcomma }}{% else %}<span class="text-muted">—</span>{% endif %}
          </td>
          {% endfor %}
          <td class="text-end font-monospace fw-semibold">{{ row.total|floatformat:2|intcomma }}</td>
        </tr>
        {% endfor %}
      </tbody>
      <tfoot>
        <tr>
          <td>{% trans "Total" %}</td>
          {% for ctc in col_total_cells %}
          <td class="text-end font-monospace {{ ctc.css }}">{{ ctc.amount|floatformat:2|intcomma }}</td>
          {% endfor %}
          <td class="text-end font-monospace">{{ grand_total|floatformat:2|intcomma }}</td>
        </tr>
      </tfoot>
    </table>
  </div>
</div>
{% else %}
<div class="alert alert-success">
  <i class="bi bi-check-circle me-1"></i>
  {% trans "No hay cuentas por cobrar pendientes." %}
</div>
{% endif %}

{% endblock %}
```

- [ ] **Step 2: Verify page loads**

Navigate to Reports → Antigüedad de Cuentas por Cobrar. Verify: page loads, table footer has dark top border, no `table-light` class visible in source.

- [ ] **Step 3: Commit**

```bash
git add templates/invoices/report_aging.html
git commit -m "style: redesign report_aging — rpt-header, rpt-table-wrap"
```

---

## Task 6: Redesign report_sales_period.html

**Files:**
- Rewrite: `templates/invoices/report_sales_period.html`

Changes: add shared styles include, new `.rpt-header`, `bg-light` pill cards → `.rpt-metric-card`, table → `.rpt-table-wrap`, remove `btn_color="success"` from filter include.

- [ ] **Step 1: Overwrite the file**

```django
{% extends "base.html" %}
{% load i18n humanize %}

{% block title %}{% trans "Ventas por Período" %}{% endblock %}

{% block extra_css %}
{% include "invoices/partials/report_shared_styles.html" %}
{% endblock %}

{% block content %}

{# ── Print-only document header ───────────────────────────────────────────── #}
<div class="print-header">
  <p class="print-org">{{ organization.name }}</p>
  <h1 class="print-title">{% trans "Ventas por Período" %}</h1>
  {% if year %}
  <p class="print-meta">
    {% if month %}{{ rows.0.period|date:"F Y" }}{% else %}{% trans "Año" %} {{ year }}{% endif %}
  </p>
  {% endif %}
</div>

{# ── Screen header ────────────────────────────────────────────────────────── #}
<div class="rpt-header no-print">
  <div>
    <h1 class="rpt-header-title">{% trans "Ventas por Período" %}</h1>
    {% if year %}<p class="rpt-header-sub">{% if month %}{{ rows.0.period|date:"F Y" }}{% else %}{% trans "Año" %} {{ year }}{% endif %}</p>{% endif %}
  </div>
  <div class="rpt-header-actions">
    <a href="{% url 'invoices:reports' %}" class="btn btn-outline-secondary btn-sm">
      <i class="bi bi-arrow-left me-1"></i>{% trans "Reportes" %}
    </a>
    <button type="button" class="btn btn-outline-secondary btn-sm" onclick="window.print()">
      <i class="bi bi-printer me-1"></i>{% trans "Imprimir" %}
    </button>
  </div>
</div>

{# ── Filter form ──────────────────────────────────────────────────────────── #}
{% include "invoices/partials/report_filter_panel.html" with show_year=True show_month=True %}

{% if year %}

{% if rows %}
{# ── Summary metric cards ──────────────────────────────────────────────────── #}
<div class="row g-2 mb-3 no-print">
  <div class="col-6 col-sm-4">
    <div class="rpt-metric-card">
      <div class="rpt-metric-value">{{ totals.invoiced|floatformat:2|intcomma }}</div>
      <div class="rpt-metric-label">{% trans "Total facturado" %}</div>
    </div>
  </div>
  <div class="col-6 col-sm-4">
    <div class="rpt-metric-card">
      <div class="rpt-metric-value text-success">{{ totals.collected|floatformat:2|intcomma }}</div>
      <div class="rpt-metric-label">{% trans "Total cobrado" %}</div>
    </div>
  </div>
  <div class="col-6 col-sm-4">
    <div class="rpt-metric-card">
      <div class="rpt-metric-value {% if totals.net > 0 %}text-warning{% elif totals.net < 0 %}text-danger{% endif %}">
        {{ totals.net|floatformat:2|intcomma }}
      </div>
      <div class="rpt-metric-label">
        {% if by_day %}{% trans "Neto del mes" %}{% else %}{% trans "Neto del año" %}{% endif %}
      </div>
    </div>
  </div>
</div>

{# ── Breakdown table ───────────────────────────────────────────────────────── #}
<div class="rpt-table-wrap">
  <table class="table table-hover table-sm mb-0">
    <thead>
      <tr>
        <th>{% if by_day %}{% trans "Día" %}{% else %}{% trans "Mes" %}{% endif %}</th>
        <th class="text-end">{% trans "Facturado" %}</th>
        <th class="text-end">{% trans "Cobrado" %}</th>
        <th class="text-end">{% trans "Neto" %}</th>
      </tr>
    </thead>
    <tbody>
      {% for row in rows %}
      <tr>
        <td class="fw-semibold">
          {% if by_day %}{{ row.period|date:"d/m/Y" }}{% else %}{{ row.period|date:"F Y" }}{% endif %}
        </td>
        <td class="text-end font-monospace">{{ row.invoiced|floatformat:2|intcomma }}</td>
        <td class="text-end font-monospace text-success">{{ row.collected|floatformat:2|intcomma }}</td>
        <td class="text-end font-monospace fw-semibold {% if row.net > 0 %}text-warning{% elif row.net < 0 %}text-danger{% endif %}">
          {{ row.net|floatformat:2|intcomma }}
        </td>
      </tr>
      {% endfor %}
    </tbody>
    <tfoot>
      <tr>
        <td>{% trans "Total" %}</td>
        <td class="text-end font-monospace">{{ totals.invoiced|floatformat:2|intcomma }}</td>
        <td class="text-end font-monospace text-success">{{ totals.collected|floatformat:2|intcomma }}</td>
        <td class="text-end font-monospace {% if totals.net > 0 %}text-warning{% elif totals.net < 0 %}text-danger{% endif %}">
          {{ totals.net|floatformat:2|intcomma }}
        </td>
      </tr>
    </tfoot>
  </table>
</div>
{% else %}
<div class="alert alert-info">
  <i class="bi bi-info-circle me-1"></i>
  {% if by_day %}
    {% blocktrans with y=year m=month %}No hay actividad registrada para el mes {{ m }}/{{ y }}.{% endblocktrans %}
  {% else %}
    {% blocktrans with y=year %}No hay actividad registrada para el año {{ y }}.{% endblocktrans %}
  {% endif %}
</div>
{% endif %}

{% endif %}
{% endblock %}
```

- [ ] **Step 2: Verify page loads**

Navigate to Reports → Ventas por Período. Verify: metric cards show white background with border, table footer dark top border.

- [ ] **Step 3: Commit**

```bash
git add templates/invoices/report_sales_period.html
git commit -m "style: redesign report_sales_period — rpt-header, rpt-metric-card, rpt-table-wrap"
```

---

## Task 7: Redesign report_collections.html

**Files:**
- Rewrite: `templates/invoices/report_collections.html`

Changes: add shared styles include, new `.rpt-header`, method summary `bg-light` cards → `.rpt-metric-card`, table → `.rpt-table-wrap`, remove `btn_color="info"` from filter include.

- [ ] **Step 1: Overwrite the file**

```django
{% extends "base.html" %}
{% load i18n humanize %}

{% block title %}{% trans "Cobros del Período" %}{% endblock %}

{% block extra_css %}
{% include "invoices/partials/report_shared_styles.html" %}
{% endblock %}

{% block content %}

{# ── Print-only document header ───────────────────────────────────────────── #}
<div class="print-header">
  <p class="print-org">{{ organization.name }}</p>
  <h1 class="print-title">{% trans "Cobros del Período" %}</h1>
  {% if date_from and date_to %}<p class="print-meta">{{ date_from }} — {{ date_to }}</p>{% endif %}
</div>

{# ── Screen header ────────────────────────────────────────────────────────── #}
<div class="rpt-header no-print">
  <div>
    <h1 class="rpt-header-title">{% trans "Cobros del Período" %}</h1>
    {% if date_from and date_to %}<p class="rpt-header-sub">{{ date_from }} — {{ date_to }}</p>{% endif %}
  </div>
  <div class="rpt-header-actions">
    <a href="{% url 'invoices:reports' %}" class="btn btn-outline-secondary btn-sm">
      <i class="bi bi-arrow-left me-1"></i>{% trans "Reportes" %}
    </a>
    <button type="button" class="btn btn-outline-secondary btn-sm" onclick="window.print()">
      <i class="bi bi-printer me-1"></i>{% trans "Imprimir" %}
    </button>
  </div>
</div>

{# ── Filter form ──────────────────────────────────────────────────────────── #}
{% include "invoices/partials/report_filter_panel.html" with show_dates=True %}

{% if error %}
<div class="alert alert-danger">{{ error }}</div>
{% endif %}

{% if date_from and date_to %}

{% if payments %}
{# ── Summary by method ────────────────────────────────────────────────────── #}
<div class="row g-3 mb-4 no-print">
  {% for m in by_method %}
  <div class="col-6 col-sm-4 col-md-3">
    <div class="rpt-metric-card">
      <div class="rpt-metric-value text-success">{{ m.total|floatformat:2|intcomma }}</div>
      <div class="rpt-metric-label">{{ m.method_display }}</div>
      <div class="text-muted" style="font-size:.72rem">{{ m.count }} {% trans "pago(s)" %}</div>
    </div>
  </div>
  {% endfor %}
  <div class="col-6 col-sm-4 col-md-3">
    <div class="rpt-metric-card" style="border-color:#16a34a">
      <div class="rpt-metric-value text-success">{{ grand_total|floatformat:2|intcomma }}</div>
      <div class="rpt-metric-label">{% trans "Total cobrado" %}</div>
      <div class="text-muted" style="font-size:.72rem">{{ payments|length }} {% trans "pago(s)" %}</div>
    </div>
  </div>
</div>

{# ── Detail table ─────────────────────────────────────────────────────────── #}
<div class="rpt-table-wrap">
  <div class="table-responsive">
    <table class="table table-hover table-sm mb-0">
      <thead>
        <tr>
          <th>{% trans "N°" %}</th>
          <th>{% trans "Fecha" %}</th>
          <th>{% trans "Cliente" %}</th>
          <th>{% trans "Método" %}</th>
          <th>{% trans "Referencia" %}</th>
          <th class="text-end">{% trans "Monto" %}</th>
        </tr>
      </thead>
      <tbody>
        {% for pmt in payments %}
        <tr>
          <td class="font-monospace small">
            <a href="{% url 'invoices:payment_detail' pmt.pk %}" class="text-decoration-none">
              PAG-{{ pmt.pk.hex|slice:":8"|upper }}
            </a>
          </td>
          <td class="small text-nowrap">{{ pmt.date|date:"d/m/Y" }}</td>
          <td>
            <a href="{% url 'invoices:customer_detail' pmt.customer.pk %}"
               class="text-decoration-none fw-semibold">
              {{ pmt.customer.name }}
            </a>
          </td>
          <td class="small">
            <span class="badge {% if pmt.method == 'TRANSFER' %}bg-info text-dark{% else %}bg-secondary{% endif %}">
              {{ pmt.get_method_display }}
            </span>
          </td>
          <td class="small text-muted">{{ pmt.reference|default:"—" }}</td>
          <td class="text-end font-monospace text-success fw-semibold">{{ pmt.amount|floatformat:2|intcomma }}</td>
        </tr>
        {% endfor %}
      </tbody>
      <tfoot>
        <tr>
          <td colspan="5" class="text-end">{% trans "Total" %}</td>
          <td class="text-end font-monospace text-success">{{ grand_total|floatformat:2|intcomma }}</td>
        </tr>
      </tfoot>
    </table>
  </div>
</div>
{% else %}
<div class="alert alert-info">
  <i class="bi bi-info-circle me-1"></i>
  {% trans "No se registraron cobros en el período seleccionado." %}
</div>
{% endif %}

{% endif %}
{% endblock %}
```

- [ ] **Step 2: Verify page loads**

Navigate to Reports → Cobros del Período. Verify: page loads with dark header border, filter panel is gray, "Total cobrado" metric card has green border.

- [ ] **Step 3: Commit**

```bash
git add templates/invoices/report_collections.html
git commit -m "style: redesign report_collections — rpt-header, rpt-metric-card, rpt-table-wrap"
```

---

## Task 8: Redesign report_statement.html

**Files:**
- Rewrite: `templates/invoices/report_statement.html`

Changes: replace old `.metric-card` inline styles with `.rpt-metric-card`, standardise page header to `.rpt-header`, wrap table in `.rpt-table-wrap`, strip inline `style=` from all `<th>` elements (covered by `.rpt-table-wrap thead th` CSS), replace inline error div with `alert alert-danger`.

- [ ] **Step 1: Overwrite the file**

```django
{% extends "base.html" %}
{% load i18n humanize %}

{% block title %}{% trans "Estado de Cuenta" %}{% endblock %}

{% block extra_css %}
{% include "invoices/partials/report_shared_styles.html" %}
{% endblock %}

{% block content %}

{# ── Print-only document header ───────────────────────────────────────────── #}
<div class="print-header mb-4">
  <p style="font-size:.8rem;color:#6c757d;margin:0">{{ organization.name }}</p>
  <h1 style="font-size:1.2rem;font-weight:600;margin:.25rem 0">{% trans "Estado de Cuenta" %}</h1>
  {% if customer %}
  <p style="font-size:.8rem;color:#495057;margin:0">
    {{ customer.name }}{% if customer.rnc_cedula %} · {{ customer.get_id_type_display }} {{ customer.rnc_cedula }}{% endif %}<br>
    {% trans "Período" %}: {{ date_from }} — {{ date_to }}
  </p>
  {% endif %}
</div>

{# ── Screen header ────────────────────────────────────────────────────────── #}
<div class="rpt-header no-print">
  <div>
    <h1 class="rpt-header-title">{% trans "Estado de Cuenta" %}</h1>
    <p class="rpt-header-sub">
      {% trans "Movimientos de un cliente en un período: facturas emitidas, pagos recibidos y saldo acumulado." %}
    </p>
  </div>
  <div class="rpt-header-actions">
    <a href="{% url 'invoices:reports' %}" class="btn btn-outline-secondary btn-sm">
      <i class="bi bi-arrow-left me-1"></i>{% trans "Reportes" %}
    </a>
    {% if customer and lines %}
    <button type="button" class="btn btn-outline-secondary btn-sm" onclick="window.print()">
      <i class="bi bi-printer me-1"></i>{% trans "Imprimir" %}
    </button>
    {% endif %}
  </div>
</div>

{# ── Filter form ──────────────────────────────────────────────────────────── #}
{% include "invoices/partials/report_filter_panel.html" with show_customer=True customer_required=True show_dates=True %}

{# ── Validation error ─────────────────────────────────────────────────────── #}
{% if error %}
<div class="alert alert-danger no-print">
  <i class="bi bi-exclamation-circle-fill me-2"></i>{{ error }}
</div>
{% endif %}

{% if customer %}

{# ── Customer info block ──────────────────────────────────────────────────── #}
<div class="customer-block no-print">
  <div class="customer-avatar">{{ customer.name|slice:":2"|upper }}</div>
  <div class="flex-grow-1">
    <p class="fw-semibold mb-0" style="font-size:.95rem">{{ customer.name }}</p>
    {% if customer.rnc_cedula %}
    <p class="text-muted mb-0" style="font-size:.8rem">{{ customer.get_id_type_display }} {{ customer.rnc_cedula }}</p>
    {% endif %}
  </div>
  {% if date_from and date_to %}
  <span class="badge-soft badge-confirmed ms-auto">
    <i class="bi bi-calendar3 me-1"></i>{{ date_from }} — {{ date_to }}
  </span>
  {% endif %}
</div>

{# ── Summary metric cards ─────────────────────────────────────────────────── #}
<div class="row g-2 mb-4 no-print">
  <div class="col-6 col-sm-3">
    <div class="rpt-metric-card">
      <div class="rpt-metric-value {% if opening_balance > 0 %}text-warning{% endif %}">
        {{ opening_balance|floatformat:2|intcomma }}
      </div>
      <div class="rpt-metric-label">{% trans "Saldo inicial" %}</div>
    </div>
  </div>
  <div class="col-6 col-sm-3">
    <div class="rpt-metric-card">
      <div class="rpt-metric-value">{{ period_invoiced|floatformat:2|intcomma }}</div>
      <div class="rpt-metric-label">{% trans "Facturado" %}</div>
    </div>
  </div>
  <div class="col-6 col-sm-3">
    <div class="rpt-metric-card">
      <div class="rpt-metric-value text-success">{{ period_collected|floatformat:2|intcomma }}</div>
      <div class="rpt-metric-label">{% trans "Cobrado" %}</div>
    </div>
  </div>
  <div class="col-6 col-sm-3">
    <div class="rpt-metric-card">
      <div class="rpt-metric-value {% if closing_balance > 0 %}text-warning{% elif closing_balance < 0 %}text-danger{% else %}text-success{% endif %}">
        {{ closing_balance|floatformat:2|intcomma }}
      </div>
      <div class="rpt-metric-label">{% trans "Saldo final" %}</div>
    </div>
  </div>
</div>

{% if lines %}

{# ── Statement table ──────────────────────────────────────────────────────── #}
<div class="rpt-table-wrap">
  <div class="table-responsive">
    <table class="table table-hover table-sm mb-0" style="font-size:.875rem">
      <thead>
        <tr>
          <th class="ps-4">{% trans "Fecha" %}</th>
          <th>{% trans "Tipo" %}</th>
          <th>{% trans "Referencia" %}</th>
          <th class="text-end">{% trans "Débito" %}</th>
          <th class="text-end">{% trans "Crédito" %}</th>
          <th class="pe-4 text-end">{% trans "Saldo" %}</th>
        </tr>
      </thead>
      <tbody>
        <tr class="table-light">
          <td class="ps-4 text-muted" style="font-size:.8rem" colspan="5">{% trans "Saldo anterior al período" %}</td>
          <td class="pe-4 text-end font-monospace fw-semibold {% if opening_balance > 0 %}text-warning{% endif %}"
              style="font-size:.8rem">
            {{ opening_balance|floatformat:2|intcomma }}
          </td>
        </tr>
        {% for line in lines %}
        <tr>
          <td class="ps-4 text-nowrap">{{ line.date|date:"d/m/Y" }}</td>
          <td>
            {% if line.type == 'invoice' %}
              <span class="badge-soft badge-invoice">{% trans "Factura" %}</span>
            {% else %}
              <span class="badge-soft badge-payment">{% trans "Cobro" %}</span>
            {% endif %}
          </td>
          <td>
            <a href="{{ line.url }}" class="text-decoration-none font-monospace fw-semibold text-dark" style="font-size:.82rem">
              {% if line.type == 'invoice' %}<i class="bi bi-receipt me-1 text-muted no-print" style="font-size:.75rem"></i>
              {% else %}<i class="bi bi-cash me-1 text-muted no-print" style="font-size:.75rem"></i>{% endif %}
              {{ line.ref }}
            </a>
          </td>
          <td class="text-end font-monospace">
            {% if line.debit %}{{ line.debit|floatformat:2|intcomma }}{% else %}<span class="text-muted">—</span>{% endif %}
          </td>
          <td class="text-end font-monospace text-success">
            {% if line.credit %}{{ line.credit|floatformat:2|intcomma }}{% else %}<span class="text-muted">—</span>{% endif %}
          </td>
          <td class="pe-4 text-end font-monospace fw-semibold
            {% if line.balance > 0 %}text-warning{% elif line.balance < 0 %}text-danger{% endif %}">
            {{ line.balance|floatformat:2|intcomma }}
          </td>
        </tr>
        {% endfor %}
      </tbody>
      <tfoot>
        <tr>
          <td class="ps-4" colspan="5">{% trans "Saldo final" %}</td>
          <td class="pe-4 text-end font-monospace
            {% if closing_balance > 0 %}text-warning{% elif closing_balance < 0 %}text-danger{% else %}text-success{% endif %}">
            {{ closing_balance|floatformat:2|intcomma }}
          </td>
        </tr>
      </tfoot>
    </table>
  </div>
</div>

{% else %}

{# ── Empty state ──────────────────────────────────────────────────────────── #}
<div class="alert alert-info no-print">
  <i class="bi bi-person-lines-fill me-2"></i>
  {% trans "No hay movimientos en el período seleccionado. Prueba con un rango de fechas diferente." %}
</div>

{% endif %}

{% endif %}

{% endblock %}
```

- [ ] **Step 2: Verify page loads**

Navigate to Reports → Estado de Cuenta. Verify: no 500 error, metric cards render correctly, table `<th>` elements have no `style=` attribute (inspect in browser devtools — uppercase gray text should come from CSS, not inline styles).

- [ ] **Step 3: Commit**

```bash
git add templates/invoices/report_statement.html
git commit -m "style: redesign report_statement — rpt-header, rpt-metric-card, rpt-table-wrap, strip inline th styles"
```

---

## Task 9: Redesign report_invoices_by_customer.html

**Files:**
- Rewrite: `templates/invoices/report_invoices_by_customer.html`

Changes: same pattern as Task 8 — replace old `.metric-card` inline styles with `.rpt-metric-card`, standardise header to `.rpt-header`, wrap table in `.rpt-table-wrap`, strip inline `style=` from `<th>` elements, replace inline error div with `alert alert-danger`.

- [ ] **Step 1: Overwrite the file**

```django
{% extends "base.html" %}
{% load i18n humanize %}

{% block title %}{% trans "Facturas por Cliente" %}{% endblock %}

{% block extra_css %}
{% include "invoices/partials/report_shared_styles.html" %}
{% endblock %}

{% block content %}

{# ── Print-only document header ───────────────────────────────────────────── #}
<div class="print-header mb-4">
  <p style="font-size:.8rem;color:#6c757d;margin:0">{{ organization.name }}</p>
  <h1 style="font-size:1.2rem;font-weight:600;margin:.25rem 0">{% trans "Facturas por Cliente" %}</h1>
  {% if customer %}
  <p style="font-size:.8rem;color:#495057;margin:0">
    {{ customer.name }}{% if customer.rnc_cedula %} · {{ customer.get_id_type_display }} {{ customer.rnc_cedula }}{% endif %}<br>
    {% trans "Período" %}: {{ date_from }} — {{ date_to }}
  </p>
  {% endif %}
</div>

{# ── Screen header ────────────────────────────────────────────────────────── #}
<div class="rpt-header no-print">
  <div>
    <h1 class="rpt-header-title">{% trans "Facturas por Cliente" %}</h1>
    <p class="rpt-header-sub">
      {% trans "Consulta el historial de facturación de un cliente en un período específico." %}
    </p>
  </div>
  <div class="rpt-header-actions">
    <a href="{% url 'invoices:reports' %}" class="btn btn-outline-secondary btn-sm">
      <i class="bi bi-arrow-left me-1"></i>{% trans "Reportes" %}
    </a>
    {% if customer and invoices %}
    <button type="button" class="btn btn-outline-secondary btn-sm" onclick="window.print()">
      <i class="bi bi-printer me-1"></i>{% trans "Imprimir" %}
    </button>
    {% endif %}
  </div>
</div>

{# ── Filter form ──────────────────────────────────────────────────────────── #}
{% include "invoices/partials/report_filter_panel.html" with show_customer=True customer_required=True show_dates=True %}

{# ── Validation error ─────────────────────────────────────────────────────── #}
{% if error %}
<div class="alert alert-danger no-print">
  <i class="bi bi-exclamation-circle-fill me-2"></i>{{ error }}
</div>
{% endif %}

{% if customer %}

{# ── Customer info block ──────────────────────────────────────────────────── #}
<div class="customer-block no-print">
  <div class="customer-avatar">{{ customer.name|slice:":2"|upper }}</div>
  <div class="flex-grow-1">
    <p class="fw-semibold mb-0" style="font-size:.95rem">{{ customer.name }}</p>
    {% if customer.rnc_cedula %}
    <p class="text-muted mb-0" style="font-size:.8rem">{{ customer.get_id_type_display }} {{ customer.rnc_cedula }}</p>
    {% endif %}
  </div>
  {% if date_from and date_to %}
  <span class="badge-soft badge-confirmed ms-auto">
    <i class="bi bi-calendar3 me-1"></i>{{ date_from }} — {{ date_to }}
  </span>
  {% endif %}
</div>

{% if invoices %}

{# ── Summary metric cards ─────────────────────────────────────────────────── #}
<div class="row g-2 mb-4 no-print">
  <div class="col-6 col-sm-3">
    <div class="rpt-metric-card">
      <div class="rpt-metric-value">{{ invoices|length }}</div>
      <div class="rpt-metric-label">{% trans "Facturas" %}</div>
    </div>
  </div>
  <div class="col-6 col-sm-3">
    <div class="rpt-metric-card">
      <div class="rpt-metric-value">{{ totals.subtotal|floatformat:2|intcomma }}</div>
      <div class="rpt-metric-label">{% trans "Subtotal" %}</div>
    </div>
  </div>
  <div class="col-6 col-sm-3">
    <div class="rpt-metric-card">
      <div class="rpt-metric-value text-warning">{{ totals.itbis_18|floatformat:2|intcomma }}</div>
      <div class="rpt-metric-label">{% trans "ITBIS 18%" %}</div>
    </div>
  </div>
  <div class="col-6 col-sm-3">
    <div class="rpt-metric-card">
      <div class="rpt-metric-value text-success">{{ totals.total|floatformat:2|intcomma }}</div>
      <div class="rpt-metric-label">{% trans "Total" %}</div>
    </div>
  </div>
</div>

{# ── Invoices table ───────────────────────────────────────────────────────── #}
<div class="rpt-table-wrap">
  <div class="table-responsive">
    <table class="table table-hover table-sm mb-0" style="font-size:.875rem">
      <thead>
        <tr>
          <th class="ps-4">{% trans "NCF / Doc." %}</th>
          <th>{% trans "Emisión" %}</th>
          <th>{% trans "Vence" %}</th>
          <th>{% trans "Condición" %}</th>
          <th class="text-end">{% trans "Subtotal" %}</th>
          <th class="text-end">{% trans "ITBIS 18%" %}</th>
          <th class="text-end">{% trans "Total" %}</th>
          <th class="pe-4 text-center">{% trans "Estado" %}</th>
        </tr>
      </thead>
      <tbody>
        {% for inv in invoices %}
        <tr>
          <td class="ps-4 font-monospace fw-semibold" style="font-size:.82rem">
            <a href="{% url 'invoices:invoice_detail' inv.pk %}" class="text-decoration-none text-dark">
              <i class="bi bi-receipt me-1 text-muted no-print" style="font-size:.75rem"></i>{{ inv.display_number }}
            </a>
          </td>
          <td>{{ inv.issue_date|date:"d/m/Y" }}</td>
          <td>
            {% if inv.due_date %}
              {% if inv.status == 'OVERDUE' %}
                <span class="text-danger fw-semibold"><i class="bi bi-exclamation-circle me-1" style="font-size:.75rem"></i>{{ inv.due_date|date:"d/m/Y" }}</span>
              {% else %}
                {{ inv.due_date|date:"d/m/Y" }}
              {% endif %}
            {% else %}<span class="text-muted">—</span>{% endif %}
          </td>
          <td>{{ inv.get_payment_condition_display }}</td>
          <td class="text-end font-monospace">{{ inv.subtotal|floatformat:2|intcomma }}</td>
          <td class="text-end font-monospace">{{ inv.itbis_18|floatformat:2|intcomma }}</td>
          <td class="text-end font-monospace fw-semibold">{{ inv.total|floatformat:2|intcomma }}</td>
          <td class="pe-4 text-center">
            {% if inv.status == "CONFIRMED" %}<span class="badge-soft badge-confirmed">{% trans "Confirmada" %}</span>
            {% elif inv.status == "SENT" %}<span class="badge-soft badge-sent">{% trans "Enviada" %}</span>
            {% elif inv.status == "PAID" %}<span class="badge-soft badge-paid">{% trans "Pagada" %}</span>
            {% elif inv.status == "OVERDUE" %}<span class="badge-soft badge-overdue">{% trans "Vencida" %}</span>
            {% elif inv.status == "CANCELLED" %}<span class="badge-soft badge-cancelled">{% trans "Anulada" %}</span>
            {% else %}<span class="badge-soft badge-default">{{ inv.get_status_display }}</span>{% endif %}
          </td>
        </tr>
        {% endfor %}
      </tbody>
      <tfoot>
        <tr>
          <td class="ps-4" colspan="4">{% trans "Total del período" %}</td>
          <td class="text-end font-monospace">{{ totals.subtotal|floatformat:2|intcomma }}</td>
          <td class="text-end font-monospace">{{ totals.itbis_18|floatformat:2|intcomma }}</td>
          <td class="text-end font-monospace text-success">{{ totals.total|floatformat:2|intcomma }}</td>
          <td class="pe-4"></td>
        </tr>
      </tfoot>
    </table>
  </div>
</div>

{% else %}

{# ── Empty state ──────────────────────────────────────────────────────────── #}
<div class="alert alert-info no-print">
  <i class="bi bi-receipt me-2"></i>
  {% trans "No hay facturas para el cliente y período seleccionados. Prueba con un rango de fechas diferente." %}
</div>

{% endif %}

{% endif %}

{% endblock %}
```

- [ ] **Step 2: Verify page loads**

Navigate to Reports → Facturas por Cliente. Verify: no 500 error, metric cards render correctly (no inline style= colors), `<th>` elements have no `style=` attributes, status badges still appear correctly, table footer has dark top border.

- [ ] **Step 3: Commit**

```bash
git add templates/invoices/report_invoices_by_customer.html
git commit -m "style: redesign report_invoices_by_customer — rpt-header, rpt-metric-card, rpt-table-wrap, strip inline th styles"
```

---

## Final Verification

- [ ] **Visit all 7 report pages** — no 500 errors, consistent layout across all
- [ ] **Check hub page** — `reports.html` unchanged, colorful cards still display correctly
- [ ] **Spot-check print** — open any report with data, use browser print preview, verify filter panel is hidden and print-header is visible
- [ ] **Run system check**

```bash
python manage.py check
```

Expected: `System check identified no issues (0 silenced).`
