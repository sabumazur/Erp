# Purchase Order Email — Design Spec

**Date:** 2026-06-28  
**Scope:** Send confirmed purchase order to supplier by email.

---

## 1. Goal

Allow users to email a confirmed purchase order (PO) to the supplier directly from the PO detail page. PDF attached when WeasyPrint is available.

---

## 2. Trigger

- Button visible on PO detail page **only when `status == CONFIRMED`**.
- POST to `purchases:po_email`.
- No auto-send on confirm — user controls timing and can resend.

---

## 3. Email function — `apps/purchases/email.py`

New file. Imports `_logo_url`, `_signature_url`, `_pdf_bytes` from `apps.sales.email`.

```python
def _po_pdf_bytes(po, request) -> bytes | None:
    return _pdf_bytes(
        "purchases/purchase_order_print.html",
        {"po": po, "items": po.items.all(), "org": po.organization},
        request,
    )

def send_purchase_order_email(po, request) -> bool:
    """Send PO to supplier. Returns True if sent, False if no supplier email."""
    to_email = po.supplier.email
    if not to_email:
        return False
    org = po.organization
    ctx = {
        "po": po,
        "items": po.items.all(),
        "org": org,
        "logo_url": _logo_url(org, request),
        "sender": request.user,
        "sender_signature_url": _signature_url(request.user, request),
    }
    html_body = render_to_string("purchases/email/purchase_order_email.html", ctx, request=request)
    doc_ref = po.number or _("Borrador")
    subject = f"Orden de Compra {doc_ref} – {org.name}"
    plain = f"Orden de Compra {doc_ref}\nTotal: {po.total}\n\nRevise este correo en un cliente compatible con HTML."
    msg = EmailMultiAlternatives(subject, plain, settings.DEFAULT_FROM_EMAIL, [to_email])
    msg.attach_alternative(html_body, "text/html")
    pdf = _po_pdf_bytes(po, request)
    if pdf:
        msg.attach(f"orden_{doc_ref}.pdf", pdf, "application/pdf")
    msg.send(fail_silently=False)
    return True
```

---

## 4. Email template — `templates/purchases/email/purchase_order_email.html`

### Design (ui-ux-pro-max "Trust & Authority")
- Background: `#f4f4f4` / card `#ffffff`
- Brand accent bar: `#1e2130` (matches app brand)
- Primary text: `#1a1a1a` / muted: `#6b7280`
- Expected date highlight: `#0369A1` (blue accent from design system)
- Typography: system font stack (`-apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif`)
- Card: `border-radius: 8px`, `box-shadow: 0 2px 12px rgba(0,0,0,0.08)`, max-width 620px

### Reused sales partials (unchanged)
| Partial | Purpose |
|---------|---------|
| `sales/partials/_email_head.html` | Meta + CSS reset |
| `sales/partials/_topbar.html` | Brand navy accent bar |
| `sales/partials/_org_header.html` | Org identity + doc title/number + logo |
| `sales/partials/_items_table.html` | Line items (same field names as sales) |
| `sales/partials/_totals.html` | Subtotal / ITBIS 18% / ITBIS 16% / Total |
| `sales/partials/_notes.html` | Notes block (conditional) |
| `sales/partials/_footer.html` | Org name + timestamp |

### New inline blocks (no new partials — single use)
- **Greeting:** `"Estimado(a) {contact_name or supplier.name},"`
- **Body copy:** `"Adjunto encontrará la orden de compra correspondiente a los artículos indicados. Quedo a su disposición para cualquier consulta."`
- **Parties row (2-column):**
  - Left — **Proveedor** box: supplier name, RNC/Cédula, address
  - Right — **Comprador** box: org name, org tax_id, org address
- **Meta row:** `Fecha emisión` · `Fecha esperada` (conditional, blue when set) · `Moneda` (conditional, only if not DOP)
- **Sender signature block:** same pattern as `quotation_email.html`
- **No CTA button** — suppliers have no portal access

---

## 5. View — `PurchaseOrderEmailView`

**Location:** `apps/purchases/views/purchase_orders.py`

```python
class PurchaseOrderEmailView(ERPBaseViewMixin, View):
    required_module = "purchasing"

    def post(self, request, pk):
        po = get_object_or_404(
            PurchaseDocument.purchase_orders, pk=pk, organization=request.organization
        )
        if po.status != PurchaseDocument.Status.CONFIRMED:
            messages.warning(request, _("Solo se puede enviar una orden confirmada."))
            return redirect("purchases:po_detail", pk=po.pk)
        try:
            sent = send_purchase_order_email(po, request)
            if sent:
                messages.success(
                    request,
                    _("Correo enviado a %(email)s.") % {"email": po.supplier.email},
                )
            else:
                messages.warning(request, _("El proveedor no tiene correo registrado."))
        except Exception as exc:
            messages.error(
                request,
                _("No se pudo enviar el correo: %(error)s") % {"error": str(exc)},
            )
        return redirect("purchases:po_detail", pk=po.pk)
```

---

## 6. URL

**File:** `apps/purchases/urls.py`

```python
path("purchase-orders/<uuid:pk>/email/", PurchaseOrderEmailView.as_view(), name="po_email"),
```

---

## 7. PO detail template changes

**File:** `templates/purchases/purchase_order_detail.html`

Add in **overflow section** (after Imprimir, before Clonar), CONFIRMED-only:

```html
{% if po.status == "CONFIRMED" %}
<form method="post" action="{% url 'purchases:po_email' po.pk %}">
  {% csrf_token %}
  <button type="submit" class="btn btn-outline-secondary btn-sm">
    <i class="bi bi-envelope me-1"></i>{% trans "Enviar al proveedor" %}
  </button>
</form>
{% endif %}
```

Add same item in **"Más" dropdown**, also CONFIRMED-only:

```html
{% if po.status == "CONFIRMED" %}
<li>
  <form method="post" action="{% url 'purchases:po_email' po.pk %}">
    {% csrf_token %}
    <button type="submit" class="dropdown-item">
      <i class="bi bi-envelope me-2"></i>{% trans "Enviar al proveedor" %}
    </button>
  </form>
</li>
{% endif %}
```

---

## 8. Tests — `apps/purchases/tests/test_email.py`

Three test cases mirroring `apps/sales/tests/test_email.py`:

1. **`test_send_po_email_sends_when_supplier_has_email`** — supplier has email; mock `EmailMultiAlternatives.send`; assert returns `True`, send called once, subject contains PO number.

2. **`test_send_po_email_returns_false_when_no_email`** — supplier email blank; assert returns `False`, no send call.

3. **`test_send_po_email_attaches_pdf_when_weasyprint_available`** — mock WeasyPrint; assert PDF attachment with correct filename `orden_{number}.pdf`.

---

## 9. Files changed

| File | Action |
|------|--------|
| `apps/purchases/email.py` | **New** |
| `templates/purchases/email/purchase_order_email.html` | **New** |
| `apps/purchases/views/purchase_orders.py` | Add `PurchaseOrderEmailView` |
| `apps/purchases/views/__init__.py` | Export `PurchaseOrderEmailView` |
| `apps/purchases/urls.py` | Add `po_email` URL |
| `templates/purchases/purchase_order_detail.html` | Add email button (overflow + dropdown) |
| `apps/purchases/tests/test_email.py` | **New** |

---

## 10. Out of scope

- Supplier portal / supplier-facing PO acceptance
- Email tracking / delivery receipts
- Auto-send on confirm
- Sending from DRAFT or RECEIVED status
