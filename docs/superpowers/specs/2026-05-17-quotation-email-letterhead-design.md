# Quotation Email & PDF Letterhead Redesign

**Date:** 2026-05-17  
**Scope:** Replace quotation email body and PDF print template visuals with Café Tropical branded letterhead format.

---

## Goal

When a quotation is sent by email:
1. The **PDF attachment** uses the `hoja timbrada` letterhead as a full-page background (letter size).
2. The **email body** displays the letterhead image at the top followed by styled quotation content matching the same brand colors.

---

## Assets

- Letterhead image: `static/img/hoja timbrada cafe tropical mod.jpg`
  - Letter size: 8.5in × 11in (216mm × 279mm)
  - Layout: brown stripe left, green stripe right, Café Tropical logo top-right, red stripe bottom, vertical contact info right side

---

## Files Changed

### 1. `apps/invoices/email.py`

In `send_quotation_email`, add `letterhead_url` to context:

```python
from django.templatetags.static import static

def send_quotation_email(quotation, request):
    ...
    ctx = {
        ...
        "letterhead_url": request.build_absolute_uri(
            static("img/hoja timbrada cafe tropical mod.jpg")
        ),
    }
```

No other logic changes.

### 2. `templates/invoices/quotation_print.html`

Used by WeasyPrint to generate the PDF attachment.

**Changes:**
- Set `hoja timbrada` as CSS `background-image` on `body` (or `@page` via WeasyPrint margin boxes)
- `background-size: 216mm 279mm` — exact letter, no stretch/crop
- `print-color-adjust: exact` — force WeasyPrint to render background
- Adjust body padding to clear letterhead elements:
  - `padding-top: 40mm` — clear logo area
  - `padding-left: 20mm` — clear brown left stripe
  - `padding-right: 22mm` — clear green right stripe + vertical text
  - `padding-bottom: 28mm` — clear red bottom stripe
- Style "COTIZACIÓN" title: `color: #c0392b`, right-aligned
- Items table header: dark brown `#3d2314`, white text
- Totals TOTAL row: `color: #c0392b`, bold
- Remove existing monochrome `#1a1a1a` header background; match palette to image 1

### 3. `templates/invoices/email/quotation_email.html`

The HTML email body rendered inline in the message.

**Changes:**
- Add letterhead image as full-width `<img>` block at the very top of the email card (absolute URL from `letterhead_url` context var)
- Replace amber `#b45309` scheme with Café Tropical red `#c0392b` and dark brown `#3d2314`
- Keep existing table-based structure (required for email client compatibility)
- Section order (unchanged): header bar → parties → meta → items → totals → notes → footer
- Items table `thead` background: `#3d2314` (dark brown matching letterhead left stripe)
- TOTAL row color: `#c0392b`
- Footer: keep org name + RNC + timestamp

---

## Constraints

- PDF page size: **letter portrait** (`8.5in × 11in`) — already set in `@page`
- Email images must use **absolute URLs** — WeasyPrint uses `base_url` so static `{% static %}` works in PDF template; email.py must call `request.build_absolute_uri(static(...))` for the email template
- No new models, migrations, or services needed
- WeasyPrint is an optional dep — PDF generation already has `try/except ImportError` guard; no change needed

---

## Non-Goals

- Invoice email (`invoice_email.html`) — not changed
- Sale order email (`sale_order_email.html`) — not changed
- Any backend logic beyond `letterhead_url` ctx var

---

## Test Checklist

- [ ] PDF renders with letterhead background (no white-out, no stretch)
- [ ] PDF content does not overlap logo or side stripes
- [ ] Email body shows letterhead image at top in Gmail, Outlook web
- [ ] Email body falls back gracefully if image blocked (alt text + color scheme still readable)
- [ ] PDF still attaches when WeasyPrint available
- [ ] Quotation with no notes/terms: no empty section rendered
