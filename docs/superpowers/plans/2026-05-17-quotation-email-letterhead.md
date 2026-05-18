# Quotation Email & PDF Letterhead Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the quotation email body and PDF attachment visual design with Café Tropical branded letterhead format.

**Architecture:** Three file changes — `email.py` adds `letterhead_url` to email context; `quotation_print.html` uses the letterhead as CSS background for WeasyPrint PDF; `quotation_email.html` shows the letterhead image as a header banner and updates brand colors to match.

**Tech Stack:** Django, WeasyPrint (optional, already guarded), Django template system, inline-CSS HTML email.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `apps/invoices/email.py` | Modify | Add `letterhead_url` absolute URL to `send_quotation_email` context |
| `apps/invoices/tests/test_email.py` | Create | Unit test: context includes `letterhead_url` |
| `templates/invoices/quotation_print.html` | Modify | Letterhead as CSS background; updated padding and brand colors for PDF |
| `templates/invoices/email/quotation_email.html` | Modify | Letterhead image banner at top; replace amber scheme with CT red/brown |

---

## Task 1: Add `letterhead_url` to email context and write a test

**Files:**
- Modify: `apps/invoices/email.py`
- Create: `apps/invoices/tests/test_email.py`

- [ ] **Step 1: Create failing test**

Create `apps/invoices/tests/test_email.py`:

```python
from unittest.mock import patch, MagicMock
import pytest
from apps.invoices.tests.factories import InvoiceFactory, CustomerFactory
from apps.accounts.tests.factories import OrganizationFactory
from apps.invoices.email import send_quotation_email


@pytest.mark.django_db
def test_send_quotation_email_context_includes_letterhead_url(mailoutbox):
    org = OrganizationFactory()
    customer = CustomerFactory(organization=org, email="test@example.com")
    quotation = InvoiceFactory(
        organization=org,
        customer=customer,
        doc_type="QUOTATION",
        status="SENT",
    )

    request = MagicMock()
    request.build_absolute_uri.side_effect = lambda path: f"http://testserver{path}"

    captured_ctx = {}

    def capture_render(template_name, ctx, **kwargs):
        captured_ctx.update(ctx)
        return "<html></html>"

    with patch("apps.invoices.email.render_to_string", side_effect=capture_render):
        send_quotation_email(quotation, request)

    assert "letterhead_url" in captured_ctx
    assert "hoja timbrada cafe tropical mod" in captured_ctx["letterhead_url"]
    assert captured_ctx["letterhead_url"].startswith("http://testserver")
```

- [ ] **Step 2: Run test to confirm it fails**

```
pytest apps/invoices/tests/test_email.py::test_send_quotation_email_context_includes_letterhead_url -v
```

Expected: `FAILED` — `AssertionError: assert "letterhead_url" in {...}` (key missing from ctx).

- [ ] **Step 3: Add `letterhead_url` to `send_quotation_email` context**

In `apps/invoices/email.py`, add import at top:

```python
from django.templatetags.static import static
```

Then update `send_quotation_email` — replace the `ctx = { ... }` block:

```python
def send_quotation_email(quotation: Invoice, request) -> bool:
    """Render quotation_email.html and send to customer with PDF attachment. Returns True if sent."""
    to_email = quotation.customer.email
    if not to_email:
        return False
    org = quotation.organization
    ctx = {
        "quotation": quotation,
        "items": quotation.items.all(),
        "org": org,
        "logo_url": _logo_url(org, request),
        "letterhead_url": request.build_absolute_uri(
            static("img/hoja timbrada cafe tropical mod.jpg")
        ),
    }
    html_body = render_to_string("invoices/email/quotation_email.html", ctx, request=request)
    doc_ref = quotation.doc_number or _("Borrador")
    subject = f"Cotización {doc_ref} – {org.name}"
    plain = f"Cotización {doc_ref}\nTotal: {quotation.total}\n\nRevise este correo en un cliente compatible con HTML."
    msg = EmailMultiAlternatives(subject, plain, settings.DEFAULT_FROM_EMAIL, [to_email])
    msg.attach_alternative(html_body, "text/html")
    pdf = _quotation_pdf_bytes(quotation, request)
    if pdf:
        msg.attach(f"cotizacion_{doc_ref}.pdf", pdf, "application/pdf")
    msg.send(fail_silently=False)
    return True
```

- [ ] **Step 4: Run test to confirm it passes**

```
pytest apps/invoices/tests/test_email.py::test_send_quotation_email_context_includes_letterhead_url -v
```

Expected: `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add apps/invoices/email.py apps/invoices/tests/test_email.py
git commit -m "feat(invoices): add letterhead_url to quotation email context"
```

---

## Task 2: Redesign `quotation_print.html` — letterhead background + brand colors

**Files:**
- Modify: `templates/invoices/quotation_print.html`

This template is rendered by WeasyPrint via `_quotation_pdf_bytes()`. WeasyPrint supports CSS `background-image` with `print-color-adjust: exact`.

- [ ] **Step 1: Replace the `<style>` block in `quotation_print.html`**

Open `templates/invoices/quotation_print.html`. Replace the entire `<style>` block (lines 7–66) with:

```css
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 12px;
    color: #1a1a1a;
    background-color: #fff;
    background-image: url("{% static 'img/hoja timbrada cafe tropical mod.jpg' %}");
    background-size: 216mm 279mm;
    background-repeat: no-repeat;
    background-position: top left;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
    padding: 38mm 24mm 30mm 22mm;
  }

  .doc-header { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #c0392b; padding-bottom: 10px; margin-bottom: 16px; }
  .org-name { font-size: 16px; font-weight: 700; }
  .org-meta { font-size: 10px; color: #555; margin-top: 4px; }
  .doc-title { text-align: right; }
  .doc-title h1 { font-size: 22px; font-weight: 800; text-transform: uppercase; letter-spacing: 1px; color: #c0392b; }
  .doc-title .doc-number { font-size: 13px; font-family: monospace; color: #333; margin-top: 4px; }
  .doc-title .doc-status { display: inline-block; margin-top: 6px; padding: 2px 10px; border-radius: 20px; font-size: 10px; font-weight: 700; text-transform: uppercase; background: #e9ecef; color: #495057; border: 1px solid #ced4da; }
  .doc-title .doc-status.confirmed { background: #cfe2ff; color: #084298; border-color: #b6d4fe; }
  .doc-title .doc-status.sent     { background: #d1ecf1; color: #0c5460; border-color: #bee5eb; }
  .doc-title .doc-status.accepted { background: #d1e7dd; color: #0f5132; border-color: #badbcc; }
  .doc-title .doc-status.rejected { background: #f8d7da; color: #842029; border-color: #f5c2c7; }

  .parties { display: flex; gap: 20px; margin-bottom: 16px; }
  .party { flex: 1; background: #f8f9fa; border-left: 3px solid #c0392b; border-radius: 0 4px 4px 0; padding: 9px 12px; }
  .party-label { font-size: 9px; text-transform: uppercase; letter-spacing: 0.6px; color: #999; font-weight: 700; margin-bottom: 3px; }
  .party-name { font-weight: 700; font-size: 13px; }
  .party-meta { font-size: 11px; color: #555; margin-top: 2px; }

  .doc-meta { display: flex; gap: 20px; margin-bottom: 16px; flex-wrap: wrap; }
  .meta-label { font-size: 9px; text-transform: uppercase; letter-spacing: 0.5px; color: #999; font-weight: 700; }
  .meta-value { font-weight: 700; font-size: 12px; margin-top: 1px; }

  table { width: 100%; border-collapse: collapse; margin-bottom: 14px; }
  thead th { background: #3d2314; color: #fff; padding: 7px 8px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px; }
  thead th.text-end { text-align: right; }
  thead th.text-center { text-align: center; }
  tbody tr:nth-child(even) { background: #fdf8f6; }
  tbody td { padding: 6px 8px; vertical-align: top; border-bottom: 1px solid #e9ecef; font-size: 12px; }
  tbody td.text-end { text-align: right; }
  tbody td.text-center { text-align: center; }

  .totals-wrap { display: flex; justify-content: flex-end; margin-bottom: 18px; }
  .totals-table { width: 260px; border-collapse: collapse; }
  .totals-table td { padding: 4px 8px; font-size: 12px; }
  .totals-table td:last-child { text-align: right; font-weight: 600; }
  .totals-table tr.grand { border-top: 2px solid #c0392b; }
  .totals-table tr.grand td { font-weight: 800; font-size: 15px; padding-top: 6px; color: #c0392b; }

  .validity-notice { border: 1px dashed #e0a89a; border-radius: 4px; padding: 8px 12px; font-size: 11px; color: #6b2416; background: #fdf3f1; margin-bottom: 14px; }
  .validity-notice strong { color: #c0392b; }

  .footer-notes { border-top: 1px solid #dee2e6; padding-top: 10px; margin-top: 6px; }
  .footer-notes .note-label { font-size: 9px; text-transform: uppercase; letter-spacing: 0.5px; color: #999; font-weight: 700; margin-bottom: 2px; }
  .footer-notes .note-text { font-size: 11px; color: #444; margin-bottom: 10px; }

  .page-footer { margin-top: 24px; border-top: 1px solid #dee2e6; padding-top: 6px; font-size: 10px; color: #aaa; text-align: center; }

  @media print {
    body { padding: 38mm 24mm 30mm 22mm; }
    .no-print { display: none !important; }
    @page { margin: 0; size: letter portrait; }
  }
  .print-btn { position: fixed; top: 12px; right: 16px; padding: 8px 18px; background: #c0392b; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; z-index: 999; }
  .print-btn:hover { background: #a93226; }
</style>
```

- [ ] **Step 2: Verify `{% load %}` tags are present**

Confirm line 1 of `quotation_print.html` starts with:

```django
{% load i18n humanize static %}<!DOCTYPE html>
```

`{% load static %}` must be present for `{% static %}` in the CSS background URL. It is already in the file — no change needed.

- [ ] **Step 3: Remove the `@page` rule that was inside the old `@media print` block**

The old `@media print` block had `@page { margin: 12mm; size: letter portrait; }`. In the new CSS, `@page { margin: 0; size: letter portrait; }` is used instead — `margin: 0` lets the letterhead image bleed to the page edges without white gutters. This is already written in the new `<style>` block above.

- [ ] **Step 4: Manual visual verification**

Open a browser to any quotation detail page and click "Imprimir" (or navigate to the print URL). Verify:
- Letterhead background visible behind content (brown stripe left, green stripe right, logo top-right, red stripe bottom)
- "COTIZACIÓN" title is red `#c0392b`
- Table header is dark brown `#3d2314`
- TOTAL row text is red `#c0392b`
- Content text does not overlap the logo or side stripes

- [ ] **Step 5: Commit**

```bash
git add templates/invoices/quotation_print.html
git commit -m "feat(invoices): apply Cafe Tropical letterhead to quotation PDF"
```

---

## Task 3: Redesign `quotation_email.html` — letterhead banner + brand colors

**Files:**
- Modify: `templates/invoices/email/quotation_email.html`

This template renders as the HTML body of the sent email. Must use table-based, inline-CSS layout for email client compatibility. The `letterhead_url` variable (absolute URL) is now available in context from Task 1.

- [ ] **Step 1: Replace the entire `quotation_email.html` file**

Overwrite `templates/invoices/email/quotation_email.html` with:

```html
{% load i18n humanize %}<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% trans "Cotización" %} {{ quotation.doc_number|default:"Borrador" }} – {{ org.name }}</title>
  <style>
    body, table, td { -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }
    table { border-spacing: 0; }
    td { padding: 0; }
    img { border: 0; display: block; }
    body { margin: 0; padding: 0; background: #f4f4f4; font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif; }
  </style>
</head>
<body bgcolor="#f4f4f4">

<!-- Wrapper -->
<table width="100%" cellpadding="0" cellspacing="0" bgcolor="#f4f4f4">
  <tr>
    <td align="center" style="padding: 24px 16px;">

      <!-- Card -->
      <table width="620" cellpadding="0" cellspacing="0" style="max-width:620px;width:100%;background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">

        <!-- ── LETTERHEAD BANNER ── -->
        {% if letterhead_url %}
        <tr>
          <td style="padding:0;font-size:0;line-height:0;overflow:hidden;max-height:160px;">
            <img src="{{ letterhead_url }}" width="620" alt="{{ org.name }}"
                 style="width:100%;max-width:620px;height:160px;object-fit:cover;object-position:top center;display:block;">
          </td>
        </tr>
        {% else %}
        <!-- Fallback top bar when image blocked -->
        <tr>
          <td bgcolor="#c0392b" height="6" style="height:6px;font-size:0;line-height:0;">&nbsp;</td>
        </tr>
        {% endif %}

        <!-- ── HEADER META (doc number + status) ── -->
        <tr>
          <td style="padding: 18px 28px 14px; border-bottom: 2px solid #c0392b;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td valign="middle">
                  <div style="font-size:20px;font-weight:800;text-transform:uppercase;letter-spacing:2px;color:#c0392b;">{% trans "Cotización" %}</div>
                  <div style="font-size:13px;font-family:monospace;color:#374151;margin-top:4px;">{{ quotation.doc_number|default:"Borrador" }}</div>
                </td>
                <td valign="middle" align="right">
                  <div style="display:inline-block;padding:4px 14px;border-radius:20px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.6px;
                    {% if quotation.status == 'ACCEPTED' %}background:#d1e7dd;color:#0f5132;
                    {% elif quotation.status == 'REJECTED' %}background:#f8d7da;color:#842029;
                    {% elif quotation.status == 'SENT' %}background:#d1ecf1;color:#0c5460;
                    {% elif quotation.status == 'CONFIRMED' %}background:#cfe2ff;color:#084298;
                    {% elif quotation.status == 'EXPIRED' %}background:#f3f4f6;color:#9ca3af;
                    {% else %}background:#fef3c7;color:#92400e;{% endif %}">
                    {{ quotation.get_status_display }}
                  </div>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- ── PARTIES ── -->
        <tr>
          <td style="padding: 18px 28px 0;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td width="50%" valign="top" style="padding-right:8px;">
                  <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                      <td style="background:#f8f9fa;border-left:3px solid #c0392b;border-radius:0 4px 4px 0;padding:10px 12px;">
                        <div style="font-size:9px;text-transform:uppercase;letter-spacing:0.8px;color:#9ca3af;font-weight:700;margin-bottom:4px;">{% trans "Cliente" %}</div>
                        <div style="font-weight:700;font-size:13px;color:#1a1a1a;">{{ quotation.customer.name }}</div>
                        {% if quotation.customer.rnc_cedula %}<div style="font-size:11px;color:#555;margin-top:2px;">{{ quotation.customer.get_id_type_display }}: {{ quotation.customer.rnc_cedula }}</div>{% endif %}
                        {% if quotation.customer.address %}<div style="font-size:11px;color:#555;margin-top:2px;">{{ quotation.customer.address }}</div>{% endif %}
                      </td>
                    </tr>
                  </table>
                </td>
                <td width="50%" valign="top" style="padding-left:8px;">
                  <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                      <td style="background:#f8f9fa;border-left:3px solid #c0392b;border-radius:0 4px 4px 0;padding:10px 12px;">
                        <div style="font-size:9px;text-transform:uppercase;letter-spacing:0.8px;color:#9ca3af;font-weight:700;margin-bottom:4px;">{% trans "Emisor" %}</div>
                        <div style="font-weight:700;font-size:13px;color:#1a1a1a;">{{ org.name }}</div>
                        {% if org.tax_id %}<div style="font-size:11px;color:#555;margin-top:2px;">RNC: {{ org.tax_id }}</div>{% endif %}
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- ── META ── -->
        <tr>
          <td style="padding: 14px 28px 0;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="border-bottom:1px solid #e5e7eb;padding-bottom:12px;">
                  <table cellpadding="0" cellspacing="0">
                    <tr>
                      <td style="padding-right:24px;">
                        <div style="font-size:9px;text-transform:uppercase;letter-spacing:0.6px;color:#9ca3af;font-weight:700;">{% trans "Fecha emisión" %}</div>
                        <div style="font-weight:700;font-size:12px;color:#1a1a1a;margin-top:2px;">{{ quotation.issue_date|date:"d/m/Y" }}</div>
                      </td>
                      {% if quotation.valid_until %}
                      <td style="padding-right:24px;">
                        <div style="font-size:9px;text-transform:uppercase;letter-spacing:0.6px;color:#9ca3af;font-weight:700;">{% trans "Válida hasta" %}</div>
                        <div style="font-weight:700;font-size:12px;color:#c0392b;margin-top:2px;">{{ quotation.valid_until|date:"d/m/Y" }}</div>
                      </td>
                      {% endif %}
                      <td>
                        <div style="font-size:9px;text-transform:uppercase;letter-spacing:0.6px;color:#9ca3af;font-weight:700;">{% trans "Condición pago" %}</div>
                        <div style="font-weight:700;font-size:12px;color:#1a1a1a;margin-top:2px;">{{ quotation.get_payment_condition_display }}</div>
                      </td>
                      {% if quotation.currency != "DOP" %}
                      <td style="padding-left:24px;">
                        <div style="font-size:9px;text-transform:uppercase;letter-spacing:0.6px;color:#9ca3af;font-weight:700;">{% trans "Moneda" %}</div>
                        <div style="font-weight:700;font-size:12px;color:#1a1a1a;margin-top:2px;">{{ quotation.currency }} @ {{ quotation.exchange_rate }}</div>
                      </td>
                      {% endif %}
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- ── VALIDITY CALLOUT ── -->
        {% if quotation.valid_until %}
        <tr>
          <td style="padding: 12px 28px 0;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td bgcolor="#fdf3f1" style="background:#fdf3f1;border-left:4px solid #c0392b;border-radius:0 4px 4px 0;padding:9px 12px;font-size:11px;color:#6b2416;">
                  {% trans "Esta cotización es válida hasta el" %}
                  <strong style="color:#c0392b;">{{ quotation.valid_until|date:"d/m/Y" }}</strong>.
                  {% trans "Los precios indicados pueden estar sujetos a cambios luego de dicha fecha." %}
                </td>
              </tr>
            </table>
          </td>
        </tr>
        {% endif %}

        <!-- ── ITEMS TABLE ── -->
        <tr>
          <td style="padding: 16px 28px 0;">
            <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
              <thead>
                <tr bgcolor="#3d2314">
                  <th align="left"   style="padding:8px 9px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:#ffffff;">{% trans "Descripción" %}</th>
                  <th align="right"  style="padding:8px 9px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:#ffffff;width:60px;">{% trans "Cant." %}</th>
                  <th align="right"  style="padding:8px 9px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:#ffffff;width:90px;">{% trans "P. Unit." %}</th>
                  <th align="center" style="padding:8px 9px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:#ffffff;width:60px;">{% trans "ITBIS" %}</th>
                  <th align="right"  style="padding:8px 9px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:#ffffff;width:90px;">{% trans "Subtotal" %}</th>
                  <th align="right"  style="padding:8px 9px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:#ffffff;width:100px;">{% trans "Total" %}</th>
                </tr>
              </thead>
              <tbody>
                {% for item in items %}
                <tr bgcolor="{% cycle '#ffffff' '#fdf8f6' %}">
                  <td style="padding:7px 9px;font-size:12px;border-bottom:1px solid #e5e7eb;vertical-align:top;">{{ item.description }}</td>
                  <td align="right"  style="padding:7px 9px;font-size:12px;border-bottom:1px solid #e5e7eb;vertical-align:top;">{{ item.quantity|floatformat:"-4" }}</td>
                  <td align="right"  style="padding:7px 9px;font-size:12px;border-bottom:1px solid #e5e7eb;vertical-align:top;">{{ item.unit_price|floatformat:2|intcomma }}</td>
                  <td align="center" style="padding:7px 9px;font-size:12px;border-bottom:1px solid #e5e7eb;vertical-align:top;">{{ item.get_itbis_rate_display }}</td>
                  <td align="right"  style="padding:7px 9px;font-size:12px;border-bottom:1px solid #e5e7eb;vertical-align:top;">{{ item.line_total|floatformat:2|intcomma }}</td>
                  <td align="right"  style="padding:7px 9px;font-size:12px;border-bottom:1px solid #e5e7eb;vertical-align:top;">{{ item.line_total_with_itbis|floatformat:2|intcomma }}</td>
                </tr>
                {% endfor %}
              </tbody>
            </table>
          </td>
        </tr>

        <!-- ── TOTALS ── -->
        <tr>
          <td style="padding: 10px 28px 0;" align="right">
            <table cellpadding="0" cellspacing="0" width="260">
              <tr>
                <td style="padding:4px 9px;font-size:12px;color:#374151;">{% trans "Subtotal" %}</td>
                <td align="right" style="padding:4px 9px;font-size:12px;font-weight:600;color:#374151;">{{ quotation.subtotal|floatformat:2|intcomma }}</td>
              </tr>
              {% if quotation.itbis_18 %}
              <tr>
                <td style="padding:4px 9px;font-size:11px;color:#6b7280;">{% trans "ITBIS 18%" %}</td>
                <td align="right" style="padding:4px 9px;font-size:11px;font-weight:600;color:#6b7280;">{{ quotation.itbis_18|floatformat:2|intcomma }}</td>
              </tr>
              {% endif %}
              {% if quotation.itbis_16 %}
              <tr>
                <td style="padding:4px 9px;font-size:11px;color:#6b7280;">{% trans "ITBIS 16%" %}</td>
                <td align="right" style="padding:4px 9px;font-size:11px;font-weight:600;color:#6b7280;">{{ quotation.itbis_16|floatformat:2|intcomma }}</td>
              </tr>
              {% endif %}
              <tr>
                <td style="padding:8px 9px 4px;font-size:15px;font-weight:800;color:#c0392b;border-top:2.5px solid #c0392b;">{% trans "TOTAL" %}</td>
                <td align="right" style="padding:8px 9px 4px;font-size:15px;font-weight:800;color:#c0392b;border-top:2.5px solid #c0392b;">{{ quotation.total|floatformat:2|intcomma }}</td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- ── NOTES ── -->
        {% if quotation.notes or quotation.terms %}
        <tr>
          <td style="padding: 16px 28px 0;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr><td style="border-top:1px solid #e5e7eb;padding-top:12px;">
                {% if quotation.notes %}
                <div style="font-size:9px;text-transform:uppercase;letter-spacing:0.6px;color:#9ca3af;font-weight:700;margin-bottom:3px;">{% trans "Notas" %}</div>
                <div style="font-size:11px;color:#4b5563;margin-bottom:10px;">{{ quotation.notes }}</div>
                {% endif %}
                {% if quotation.terms %}
                <div style="font-size:9px;text-transform:uppercase;letter-spacing:0.6px;color:#9ca3af;font-weight:700;margin-bottom:3px;">{% trans "Términos y condiciones" %}</div>
                <div style="font-size:11px;color:#4b5563;">{{ quotation.terms }}</div>
                {% endif %}
              </td></tr>
            </table>
          </td>
        </tr>
        {% endif %}

        <!-- ── FOOTER ── -->
        <tr>
          <td bgcolor="#f8f9fa" style="padding:14px 28px;border-top:1px solid #e5e7eb;border-radius:0 0 8px 8px;">
            <div style="font-size:10px;color:#9ca3af;text-align:center;">
              {{ org.name }}{% if org.tax_id %} · RNC {{ org.tax_id }}{% endif %}
              &nbsp;—&nbsp;{% trans "Documento generado el" %} {% now "d/m/Y H:i" %}
            </div>
          </td>
        </tr>

      </table>
      <!-- /Card -->

    </td>
  </tr>
</table>

</body>
</html>
```

- [ ] **Step 2: Trigger a test email send and visually verify**

In the Django shell or via the UI, send a quotation to an email address you can check:

```
python manage.py shell
>>> from apps.invoices.models import Invoice
>>> from django.test import RequestFactory
>>> from apps.invoices.email import send_quotation_email
>>> q = Invoice.quotations.first()
>>> rf = RequestFactory()
>>> req = rf.get('/')
>>> req.META['SERVER_NAME'] = 'localhost'
>>> req.META['SERVER_PORT'] = '8000'
>>> send_quotation_email(q, req)
```

Check the email in your inbox. Verify:
- Letterhead banner visible at top (logo, brown/green areas visible)
- Fallback: if image blocked, red top bar and content remains readable
- "Cotización" title red, doc number in monospace
- Party boxes with red left border
- Table header dark brown `#3d2314`
- TOTAL row red `#c0392b`
- PDF still attached

- [ ] **Step 3: Commit**

```bash
git add templates/invoices/email/quotation_email.html
git commit -m "feat(invoices): redesign quotation email with Cafe Tropical letterhead and brand colors"
```

---

## Task 4: Run full test suite

- [ ] **Step 1: Run all invoice tests**

```
pytest apps/invoices/ -v
```

Expected: all pass, no regressions.

- [ ] **Step 2: Run new email test specifically**

```
pytest apps/invoices/tests/test_email.py -v
```

Expected: `PASSED`.
