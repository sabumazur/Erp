# Dashboard Redesign — Clean Accent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dashboard template with a polished "Clean Accent" design — colored left-border KPI cards, top-border stat pills, unified panel cards for charts and tables, and soft badge colors.

**Architecture:** Pure template rewrite. All data, view logic, URL routing, and Chart.js configuration remain identical. Changes are scoped entirely to `templates/accounts/dashboard.html` via a `{% block extra_css %}` style block and updated HTML structure. The existing shell layout (`app.css`) provides the `#f4f6fb` page background — no global CSS changes needed.

**Tech Stack:** Django templates, Bootstrap 5 (utility classes where applicable), Bootstrap Icons (`bi-*`), Chart.js 4.4.4 (unchanged).

---

## File Map

| File | Action |
|---|---|
| `templates/accounts/dashboard.html` | Full rewrite — new CSS block + new HTML structure |
| `.gitignore` | Add `.superpowers/` if not already present |

---

## Task 1: Rewrite dashboard template — CSS block + page header

**Files:**
- Modify: `templates/accounts/dashboard.html`

- [ ] **Step 1: Replace the entire file with the new template (CSS block + page header only)**

  Open `templates/accounts/dashboard.html` and replace its full content with:

  ```django
  {% extends "base.html" %}
  {% load i18n humanize %}

  {% block title %}Dashboard — {{ organization.name }}{% endblock %}

  {% block extra_css %}
  <style>
  /* ── KPI Cards ─────────────────────────── */
  .db-kpi-card {
    background: #fff;
    border-radius: 10px;
    padding: 16px 16px 14px;
    border-left: 4px solid transparent;
    box-shadow: 0 1px 3px rgba(0,0,0,.06), 0 1px 2px rgba(0,0,0,.04);
    position: relative;
    overflow: hidden;
    height: 100%;
  }
  .db-kpi-label {
    font-size: 11px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: .5px;
    margin-bottom: 8px;
  }
  .db-kpi-value {
    font-size: 22px;
    font-weight: 800;
    letter-spacing: -.5px;
    line-height: 1;
  }
  .db-kpi-sub { font-size: 11px; color: #94a3b8; margin-top: 6px; }
  .db-kpi-icon {
    position: absolute; bottom: 12px; right: 14px;
    font-size: 28px; opacity: .10; line-height: 1;
  }
  .db-kpi-blue  { border-left-color: #0d6efd; }
  .db-kpi-blue .db-kpi-value  { color: #0d6efd; }
  .db-kpi-blue .db-kpi-icon   { color: #0d6efd; }
  .db-kpi-green { border-left-color: #198754; }
  .db-kpi-green .db-kpi-value { color: #198754; }
  .db-kpi-green .db-kpi-icon  { color: #198754; }
  .db-kpi-amber { border-left-color: #f59e0b; }
  .db-kpi-amber .db-kpi-value { color: #b45309; }
  .db-kpi-amber .db-kpi-icon  { color: #f59e0b; }
  .db-kpi-red   { border-left-color: #dc3545; }
  .db-kpi-red .db-kpi-value   { color: #dc3545; }
  .db-kpi-red .db-kpi-icon    { color: #dc3545; }

  /* ── Stat pills ────────────────────────── */
  .db-stat-card {
    background: #fff;
    border-radius: 10px;
    padding: 14px 16px;
    display: flex;
    align-items: center;
    gap: 14px;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
    border-top: 3px solid transparent;
    height: 100%;
  }
  .db-stat-card.db-teal   { border-top-color: #0ea5e9; }
  .db-stat-card.db-indigo { border-top-color: #6366f1; }
  .db-stat-card.db-orange { border-top-color: #f97316; }
  .db-stat-icon {
    width: 40px; height: 40px; border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0; font-size: 18px;
  }
  .db-teal   .db-stat-icon { background: #f0f9ff; color: #0ea5e9; }
  .db-indigo .db-stat-icon { background: #eef2ff; color: #6366f1; }
  .db-orange .db-stat-icon { background: #fff7ed; color: #f97316; }
  .db-stat-num { font-size: 20px; font-weight: 800; color: #0f172a; }
  .db-stat-lbl { font-size: 11px; color: #64748b; }
  .db-stat-link {
    margin-left: auto; font-size: 11px; color: #64748b;
    border: 1px solid #e2e8f0; padding: 4px 10px;
    border-radius: 6px; text-decoration: none;
    white-space: nowrap; flex-shrink: 0;
  }
  .db-stat-link:hover { background: #f8fafc; color: #374151; }

  /* ── Panels (charts + tables) ──────────── */
  .db-panel {
    background: #fff;
    border-radius: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
    overflow: hidden;
    height: 100%;
  }
  .db-panel-header {
    padding: 13px 16px 11px;
    border-bottom: 1px solid #f1f5f9;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .db-panel-title { font-size: 13px; font-weight: 600; color: #1e293b; }
  .db-panel-badge {
    font-size: 10px; color: #64748b;
    background: #f1f5f9; padding: 2px 8px; border-radius: 10px;
  }
  .db-panel-body { padding: 14px 16px; }

  /* ── Tables ────────────────────────────── */
  .db-table { width: 100%; border-collapse: collapse; }
  .db-table thead th {
    padding: 8px 12px;
    font-size: 11px; font-weight: 600; color: #64748b;
    text-transform: uppercase; letter-spacing: .4px;
    background: #f8fafc;
    border-bottom: 1px solid #f1f5f9;
    white-space: nowrap;
  }
  .db-table tbody tr { border-bottom: 1px solid #f8fafc; }
  .db-table tbody tr:last-child { border-bottom: none; }
  .db-table tbody td { padding: 9px 12px; font-size: 12.5px; color: #334155; }
  .db-table tbody tr:hover td { background: #fafbfc; }

  /* Soft badges */
  .db-badge {
    font-size: 10px; font-weight: 600;
    padding: 2px 7px; border-radius: 10px; display: inline-block;
  }
  .db-badge-paid    { background: #dcfce7; color: #166534; }
  .db-badge-sent    { background: #e0f2fe; color: #0369a1; }
  .db-badge-overdue { background: #fee2e2; color: #991b1b; }
  .db-badge-confirm { background: #eff6ff; color: #1e40af; }
  .db-badge-draft   { background: #f1f5f9; color: #64748b; }

  /* Payment method chips */
  .db-method {
    font-size: 10px; font-weight: 600;
    padding: 2px 7px; border-radius: 10px; display: inline-block;
  }
  .db-method-transfer { background: #e0f2fe; color: #0369a1; }
  .db-method-cash     { background: #dcfce7; color: #166534; }
  .db-method-check    { background: #f1f5f9; color: #475569; }

  /* ── Page header ───────────────────────── */
  .db-page-header {
    display: flex; align-items: center;
    justify-content: space-between; margin-bottom: 20px;
  }
  .db-page-title { font-size: 18px; font-weight: 800; color: #0f172a; margin: 0; }
  .db-page-org   { font-size: 12px; color: #94a3b8; margin-top: 2px; }
  .db-date-chip  {
    background: #fff; border: 1px solid #e2e8f0;
    border-radius: 6px; padding: 5px 12px;
    font-size: 12px; color: #64748b; font-weight: 500;
    box-shadow: 0 1px 2px rgba(0,0,0,.04);
  }
  .db-section { margin-bottom: 16px; }
  </style>
  {% endblock %}

  {% block content %}

  {# ── Page header ── #}
  <div class="db-page-header">
    <div>
      <h4 class="db-page-title">{% trans "Dashboard" %}</h4>
      <div class="db-page-org"><i class="bi bi-building me-1"></i>{{ organization.name }}</div>
    </div>
    <div class="db-date-chip">{{ today|date:"d/m/Y" }}</div>
  </div>

  {% endblock %}

  {% block extra_js %}{% endblock %}
  ```

  > **Note:** `{% block extra_js %}{% endblock %}` is a placeholder — it will be filled in Task 5. Do not leave it empty in the final file.

- [ ] **Step 2: Start dev server and verify page loads without errors**

  ```bash
  python manage.py runserver
  ```

  Open `http://localhost:8000/` in a browser. Expected: the dashboard shows only the page header (title + org name + date chip) with no Python errors in the terminal.

---

## Task 2: Add KPI cards section

**Files:**
- Modify: `templates/accounts/dashboard.html`

- [ ] **Step 1: Replace `{% block content %}` ... `{% endblock %}` with KPI cards added after the page header**

  Inside `{% block content %}`, after the `</div>` closing the `db-page-header`, add:

  ```django
  {# ── KPI Cards ── #}
  <div class="row g-3 db-section">
    <div class="col-sm-6 col-xl-3">
      <div class="db-kpi-card db-kpi-blue">
        <div class="db-kpi-label">{% trans "Facturado (mes actual)" %}</div>
        <div class="db-kpi-value">{{ month_invoiced|floatformat:2|intcomma }}</div>
        <div class="db-kpi-sub">{% trans "Mes en curso" %}</div>
        <div class="db-kpi-icon"><i class="bi bi-receipt"></i></div>
      </div>
    </div>

    <div class="col-sm-6 col-xl-3">
      <div class="db-kpi-card db-kpi-green">
        <div class="db-kpi-label">{% trans "Cobrado (mes actual)" %}</div>
        <div class="db-kpi-value">{{ month_collected|floatformat:2|intcomma }}</div>
        <div class="db-kpi-sub">{% trans "Pagos recibidos" %}</div>
        <div class="db-kpi-icon"><i class="bi bi-cash-stack"></i></div>
      </div>
    </div>

    <div class="col-sm-6 col-xl-3">
      <div class="db-kpi-card db-kpi-amber">
        <div class="db-kpi-label">{% trans "Por cobrar" %}</div>
        <div class="db-kpi-value">{{ outstanding|floatformat:2|intcomma }}</div>
        <div class="db-kpi-sub">{% trans "Pendiente de pago" %}</div>
        <div class="db-kpi-icon"><i class="bi bi-hourglass-split"></i></div>
      </div>
    </div>

    <div class="col-sm-6 col-xl-3">
      <div class="db-kpi-card db-kpi-red">
        <div class="db-kpi-label">{% trans "Vencido" %}</div>
        <div class="db-kpi-value">{{ overdue_total|floatformat:2|intcomma }}</div>
        {% if overdue_count %}
        <div class="db-kpi-sub" style="color:#dc3545;">{{ overdue_count }} {% trans "factura(s) vencida(s)" %}</div>
        {% else %}
        <div class="db-kpi-sub">{% trans "Sin facturas vencidas" %}</div>
        {% endif %}
        <div class="db-kpi-icon"><i class="bi bi-exclamation-triangle"></i></div>
      </div>
    </div>
  </div>
  ```

- [ ] **Step 2: Verify in browser**

  Reload `http://localhost:8000/`. Expected: four KPI cards appear in a row, each with a colored left border, bold number in matching color, and ghost icon at bottom-right.

---

## Task 3: Add stat pills section

**Files:**
- Modify: `templates/accounts/dashboard.html`

- [ ] **Step 1: Add stat pills after the KPI cards row inside `{% block content %}`**

  After the closing `</div>` of the KPI cards `row`, add:

  ```django
  {# ── Stat pills ── #}
  <div class="row g-3 db-section">
    <div class="col-sm-4">
      <div class="db-stat-card db-teal">
        <div class="db-stat-icon"><i class="bi bi-people"></i></div>
        <div>
          <div class="db-stat-num">{{ customer_count|intcomma }}</div>
          <div class="db-stat-lbl">{% trans "Clientes" %}</div>
        </div>
        <a href="{% url 'invoices:customer_list' %}" class="db-stat-link">{% trans "Ver" %} →</a>
      </div>
    </div>
    <div class="col-sm-4">
      <div class="db-stat-card db-indigo">
        <div class="db-stat-icon"><i class="bi bi-file-earmark-text"></i></div>
        <div>
          <div class="db-stat-num">{{ pending_quotations|intcomma }}</div>
          <div class="db-stat-lbl">{% trans "Cotizaciones activas" %}</div>
        </div>
        <a href="{% url 'invoices:quotation_list' %}" class="db-stat-link">{% trans "Ver" %} →</a>
      </div>
    </div>
    <div class="col-sm-4">
      <div class="db-stat-card db-orange">
        <div class="db-stat-icon"><i class="bi bi-cart"></i></div>
        <div>
          <div class="db-stat-num">{{ pending_sale_orders|intcomma }}</div>
          <div class="db-stat-lbl">{% trans "Órdenes pendientes" %}</div>
        </div>
        <a href="{% url 'invoices:sale_order_list' %}" class="db-stat-link">{% trans "Ver" %} →</a>
      </div>
    </div>
  </div>
  ```

- [ ] **Step 2: Verify in browser**

  Reload `http://localhost:8000/`. Expected: three stat cards appear below KPI cards, each with a colored top border, icon box on the left, and a subtle "Ver →" link on the right.

---

## Task 4: Add charts section

**Files:**
- Modify: `templates/accounts/dashboard.html`

- [ ] **Step 1: Add chart panels after the stat pills row**

  ```django
  {# ── Charts ── #}
  <div class="row g-3 db-section">
    <div class="col-lg-5">
      <div class="db-panel">
        <div class="db-panel-header">
          <span class="db-panel-title">{% trans "Facturación vs Cobros" %}</span>
          <span class="db-panel-badge">{% trans "Últimos 6 meses" %}</span>
        </div>
        <div class="db-panel-body">
          <canvas id="revenueChart"></canvas>
        </div>
      </div>
    </div>
    <div class="col-lg-4">
      <div class="db-panel">
        <div class="db-panel-header">
          <span class="db-panel-title">{% trans "Facturación por cliente" %}</span>
          <span class="db-panel-badge">{% trans "Top 6 · 6 meses" %}</span>
        </div>
        <div class="db-panel-body">
          <canvas id="customerChart"></canvas>
        </div>
      </div>
    </div>
    <div class="col-lg-3">
      <div class="db-panel">
        <div class="db-panel-header">
          <span class="db-panel-title">{% trans "Estado de facturas" %}</span>
        </div>
        <div class="db-panel-body d-flex align-items-center justify-content-center">
          <canvas id="statusChart" style="max-height:220px"></canvas>
        </div>
      </div>
    </div>
  </div>
  ```

- [ ] **Step 2: Add the Chart.js script block**

  Replace the empty `{% block extra_js %}{% endblock %}` at the bottom of the file with the full script block:

  ```django
  {% block extra_js %}
  {{ chart_months|json_script:"chart-months" }}
  {{ chart_invoiced|json_script:"chart-invoiced" }}
  {{ chart_collected|json_script:"chart-collected" }}
  {{ chart_status_labels|json_script:"chart-status-labels" }}
  {{ chart_status_counts|json_script:"chart-status-counts" }}
  {{ chart_status_colors|json_script:"chart-status-colors" }}
  {{ chart_customer_datasets|json_script:"chart-customer-datasets" }}
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
  <script>
  (function () {
    var months       = JSON.parse(document.getElementById('chart-months').textContent);
    var invoiced     = JSON.parse(document.getElementById('chart-invoiced').textContent);
    var collected    = JSON.parse(document.getElementById('chart-collected').textContent);
    var stLabels     = JSON.parse(document.getElementById('chart-status-labels').textContent);
    var stCounts     = JSON.parse(document.getElementById('chart-status-counts').textContent);
    var stColors     = JSON.parse(document.getElementById('chart-status-colors').textContent);
    var custDatasets = JSON.parse(document.getElementById('chart-customer-datasets').textContent);

    new Chart(document.getElementById('revenueChart'), {
      type: 'bar',
      data: {
        labels: months,
        datasets: [
          { label: '{% trans "Facturado" %}', data: invoiced,   backgroundColor: 'rgba(13,110,253,0.75)', borderRadius: 4 },
          { label: '{% trans "Cobrado" %}',   data: collected,  backgroundColor: 'rgba(25,135,84,0.75)',  borderRadius: 4 },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { position: 'top' } },
        scales: { y: { beginAtZero: true, ticks: { maxTicksLimit: 6 } } },
      },
    });

    if (stCounts.length) {
      new Chart(document.getElementById('statusChart'), {
        type: 'doughnut',
        data: { labels: stLabels, datasets: [{ data: stCounts, backgroundColor: stColors, borderWidth: 2 }] },
        options: { responsive: true, plugins: { legend: { position: 'bottom', labels: { boxWidth: 12 } } } },
      });
    } else {
      document.getElementById('statusChart').closest('.db-panel-body').innerHTML =
        '<p class="text-muted small text-center mb-0">{% trans "Sin facturas registradas." %}</p>';
    }

    if (custDatasets.length) {
      new Chart(document.getElementById('customerChart'), {
        type: 'bar',
        data: { labels: months, datasets: custDatasets },
        options: {
          responsive: true,
          plugins: { legend: { position: 'top', labels: { boxWidth: 12 } } },
          scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, ticks: { maxTicksLimit: 6 } } },
        },
      });
    } else {
      document.getElementById('customerChart').closest('.db-panel-body').innerHTML =
        '<p class="text-muted small text-center py-3 mb-0">{% trans "Sin datos de clientes." %}</p>';
    }
  })();
  </script>
  {% endblock %}
  ```

- [ ] **Step 3: Verify in browser**

  Reload `http://localhost:8000/`. Expected: three chart panels appear with the new card styling. All three charts render correctly — bar chart, stacked bar, and doughnut.

---

## Task 5: Add recent invoices table

**Files:**
- Modify: `templates/accounts/dashboard.html`

- [ ] **Step 1: Add recent invoices panel after the charts row, inside `{% block content %}`**

  ```django
  {# ── Recent invoices ── #}
  <div class="db-panel db-section">
    <div class="db-panel-header">
      <span class="db-panel-title">{% trans "Facturas recientes" %}</span>
      <a href="{% url 'invoices:invoice_list' %}" class="btn btn-sm btn-outline-primary" style="font-size:11px;">{% trans "Ver todas" %} →</a>
    </div>
    <table class="db-table">
      <thead>
        <tr>
          <th>{% trans "N° Factura" %}</th>
          <th>{% trans "Cliente" %}</th>
          <th>{% trans "Emisión" %}</th>
          <th>{% trans "Vence" %}</th>
          <th>{% trans "Estado" %}</th>
          <th class="text-end">{% trans "Total" %}</th>
        </tr>
      </thead>
      <tbody>
        {% for inv in recent_invoices %}
        <tr>
          <td class="font-monospace fw-semibold" style="font-size:11px;">
            <a href="{% url 'invoices:invoice_detail' inv.pk %}" class="text-decoration-none" style="color:#0d6efd;">{{ inv.display_number }}</a>
          </td>
          <td>{{ inv.customer.name }}</td>
          <td class="text-nowrap" style="color:#64748b;font-size:12px;">{{ inv.issue_date|date:"d/m/Y" }}</td>
          <td class="text-nowrap {% if inv.status == 'OVERDUE' %}fw-semibold{% endif %}"
              style="{% if inv.status == 'OVERDUE' %}color:#dc3545;{% else %}color:#64748b;{% endif %}font-size:12px;">
            {{ inv.due_date|date:"d/m/Y"|default:"—" }}
          </td>
          <td>
            {% if inv.status == 'PAID' %}<span class="db-badge db-badge-paid">{{ inv.get_status_display }}</span>
            {% elif inv.status == 'OVERDUE' %}<span class="db-badge db-badge-overdue">{{ inv.get_status_display }}</span>
            {% elif inv.status == 'CONFIRMED' %}<span class="db-badge db-badge-confirm">{{ inv.get_status_display }}</span>
            {% elif inv.status == 'SENT' %}<span class="db-badge db-badge-sent">{{ inv.get_status_display }}</span>
            {% else %}<span class="db-badge db-badge-draft">{{ inv.get_status_display }}</span>
            {% endif %}
          </td>
          <td class="text-end fw-bold">{{ inv.total|floatformat:2|intcomma }}</td>
        </tr>
        {% empty %}
        <tr><td colspan="6" class="text-center py-4" style="color:#94a3b8;">{% trans "No hay facturas registradas." %}</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  ```

- [ ] **Step 2: Verify in browser**

  Reload `http://localhost:8000/`. Expected: the recent invoices table appears with a slate-tinted header row, soft-color status badges, monospace invoice numbers in blue, and right-aligned bold totals.

---

## Task 6: Add overdue invoices + recent payments

**Files:**
- Modify: `templates/accounts/dashboard.html`

- [ ] **Step 1: Add the bottom two-column row as the last section inside `{% block content %}`**

  ```django
  {# ── Overdue + Recent payments ── #}
  <div class="row g-3">
    <div class="col-lg-6">
      <div class="db-panel">
        <div class="db-panel-header">
          <span class="db-panel-title" style="color:#dc3545;">
            <i class="bi bi-exclamation-circle me-1"></i>{% trans "Facturas vencidas" %}
          </span>
          {% if overdue_count > 6 %}
          <a href="{% url 'invoices:invoice_list' %}?status=OVERDUE"
             style="font-size:11px;color:#dc3545;border:1px solid #fecaca;background:#fff5f5;padding:4px 10px;border-radius:6px;text-decoration:none;">
            {% trans "Ver todas" %} →
          </a>
          {% endif %}
        </div>
        <table class="db-table">
          <thead>
            <tr>
              <th>{% trans "Factura" %}</th>
              <th>{% trans "Cliente" %}</th>
              <th class="text-end">{% trans "Días" %}</th>
              <th class="text-end">{% trans "Total" %}</th>
            </tr>
          </thead>
          <tbody>
            {% for inv in overdue_invoices %}
            <tr>
              <td class="font-monospace" style="font-size:11px;">
                <a href="{% url 'invoices:invoice_detail' inv.pk %}" class="text-decoration-none" style="color:#dc3545;">{{ inv.display_number }}</a>
              </td>
              <td style="font-size:12px;">{{ inv.customer.name }}</td>
              <td class="text-end fw-bold" style="color:#dc3545;font-size:12px;">{{ inv.days_overdue }}</td>
              <td class="text-end fw-bold" style="font-size:12px;">{{ inv.total|floatformat:2|intcomma }}</td>
            </tr>
            {% empty %}
            <tr>
              <td colspan="4" class="text-center py-4" style="color:#94a3b8;">
                <i class="bi bi-check-circle text-success me-1"></i>{% trans "Sin facturas vencidas." %}
              </td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>

    <div class="col-lg-6">
      <div class="db-panel">
        <div class="db-panel-header">
          <span class="db-panel-title">{% trans "Pagos recientes" %}</span>
          <a href="{% url 'invoices:payment_list' %}" class="btn btn-sm btn-outline-secondary" style="font-size:11px;">{% trans "Ver todos" %} →</a>
        </div>
        <table class="db-table">
          <thead>
            <tr>
              <th>{% trans "Fecha" %}</th>
              <th>{% trans "Cliente" %}</th>
              <th>{% trans "Método" %}</th>
              <th class="text-end">{% trans "Monto" %}</th>
            </tr>
          </thead>
          <tbody>
            {% for pmt in recent_payments %}
            <tr>
              <td class="text-nowrap" style="color:#64748b;font-size:12px;">{{ pmt.date|date:"d/m/Y" }}</td>
              <td style="font-size:12px;">
                <a href="{% url 'invoices:customer_detail' pmt.customer.pk %}" class="text-decoration-none" style="color:#334155;">{{ pmt.customer.name }}</a>
              </td>
              <td>
                {% if pmt.method == 'TRANSFER' %}<span class="db-method db-method-transfer">{{ pmt.get_method_display }}</span>
                {% elif pmt.method == 'CASH' %}<span class="db-method db-method-cash">{{ pmt.get_method_display }}</span>
                {% else %}<span class="db-method db-method-check">{{ pmt.get_method_display }}</span>
                {% endif %}
              </td>
              <td class="text-end fw-bold" style="color:#198754;font-size:12px;">{{ pmt.amount|floatformat:2|intcomma }}</td>
            </tr>
            {% empty %}
            <tr><td colspan="4" class="text-center py-4" style="color:#94a3b8;">{% trans "Sin pagos recientes." %}</td></tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>
  ```

- [ ] **Step 2: Close `{% block content %}`**

  Make sure `{% endblock %}` appears after the closing `</div>` of the two-column row.

- [ ] **Step 3: Final visual check in browser**

  Reload `http://localhost:8000/`. Walk through every section:
  - ✅ Page header: bold title, org name with building icon, date chip
  - ✅ KPI cards: colored left border, large bold number, ghost icon, sub-text
  - ✅ Stat pills: top border, colored icon box, bold count, "Ver →" link
  - ✅ Charts: three panels with header + badge, all charts render
  - ✅ Recent invoices: slate header row, soft badges, monospace numbers
  - ✅ Overdue table: red title and link tint, days in red
  - ✅ Payments: method chips in correct colors, green amounts

---

## Task 7: Add .superpowers/ to .gitignore and commit

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add `.superpowers/` to `.gitignore` if not already present**

  Open `.gitignore` and add this line if it's not already there:

  ```
  .superpowers/
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add templates/accounts/dashboard.html .gitignore
  git commit -m "feat: redesign dashboard with Clean Accent style

  - KPI cards: colored left borders, bold values, ghost icon watermarks
  - Stat pills: top border accents, colored icon boxes, subtle Ver link
  - Charts + tables: unified db-panel card style with slate header rows
  - Soft badge colors replacing solid Bootstrap badges
  - Scoped CSS in extra_css block, no global stylesheet changes"
  ```

  Expected output: `1 file changed` (or 2 if `.gitignore` was modified), clean working tree.
