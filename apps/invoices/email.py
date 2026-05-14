from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

from .models import Invoice


def _logo_url(org, request):
    if org.logo:
        return request.build_absolute_uri(org.logo.url)
    return None


def send_invoice_email(invoice: Invoice, request) -> bool:
    """Render invoice_email.html and send to customer. Returns True if sent."""
    to_email = invoice.customer.email
    if not to_email:
        return False
    org = invoice.organization
    ctx = {
        "invoice": invoice,
        "items": invoice.items.all(),
        "org": org,
        "logo_url": _logo_url(org, request),
    }
    html_body = render_to_string("invoices/email/invoice_email.html", ctx, request=request)
    doc_ref = invoice.encf or invoice.doc_number or _("Borrador")
    subject = f"Factura {doc_ref} – {org.name}"
    plain = f"Factura {doc_ref}\nTotal: {invoice.total}\n\nRevise este correo en un cliente compatible con HTML."
    msg = EmailMultiAlternatives(subject, plain, settings.DEFAULT_FROM_EMAIL, [to_email])
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)
    return True


def _quotation_pdf_bytes(quotation: Invoice, request) -> bytes | None:
    """Generate PDF from quotation_print.html via WeasyPrint. Returns None if unavailable."""
    try:
        from weasyprint import HTML as WeasyprintHTML
    except ImportError:
        return None
    org = quotation.organization
    html_string = render_to_string(
        "invoices/quotation_print.html",
        {"quotation": quotation, "items": quotation.items.all(), "org": org},
        request=request,
    )
    return WeasyprintHTML(string=html_string, base_url=request.build_absolute_uri("/")).write_pdf()


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


def send_sale_order_email(order: Invoice, request) -> bool:
    """Render sale_order_email.html and send to customer. Returns True if sent."""
    to_email = order.customer.email
    if not to_email:
        return False
    org = order.organization
    ctx = {
        "order": order,
        "items": order.items.all(),
        "org": org,
        "logo_url": _logo_url(org, request),
    }
    html_body = render_to_string("invoices/email/sale_order_email.html", ctx, request=request)
    doc_ref = order.doc_number or _("Borrador")
    subject = f"Orden de Venta {doc_ref} – {org.name}"
    plain = f"Orden de Venta {doc_ref}\nTotal: {order.total}\n\nRevise este correo en un cliente compatible con HTML."
    msg = EmailMultiAlternatives(subject, plain, settings.DEFAULT_FROM_EMAIL, [to_email])
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)
    return True
