import base64
import mimetypes

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

from .models import SalesDocument


def _logo_data_uri(org):
    """Return a base64 data URI for the org logo so email clients need no external fetch."""
    if not org.logo:
        return None
    try:
        path = org.logo.path
        mime = mimetypes.guess_type(path)[0] or "image/png"
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
        return f"data:{mime};base64,{encoded}"
    except (FileNotFoundError, ValueError):
        return None


def _logo_url(org, request):
    if org.logo:
        return request.build_absolute_uri(org.logo.url)
    return None


def _signature_url(user, request):
    if user and user.signature:
        return request.build_absolute_uri(user.signature.url)
    return None


def send_invoice_email(invoice: SalesDocument, request) -> bool:
    """Render invoice_email.html and send to customer. Returns True if sent."""
    to_email = invoice.customer.email
    if not to_email:
        return False
    org = invoice.organization
    ctx = {
        "invoice": invoice,
        "items": invoice.items.all(),
        "org": org,
        "logo_url": _logo_data_uri(org),
    }
    html_body = render_to_string("invoices/email/invoice_email.html", ctx, request=request)
    doc_ref = invoice.encf or invoice.doc_number or _("Borrador")
    subject = f"Factura {doc_ref} – {org.name}"
    plain = f"Factura {doc_ref}\nTotal: {invoice.total}\n\nRevise este correo en un cliente compatible con HTML."
    msg = EmailMultiAlternatives(subject, plain, settings.DEFAULT_FROM_EMAIL, [to_email])
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)
    return True


def _quotation_pdf_bytes(quotation: SalesDocument, request) -> bytes | None:
    """Generate PDF from quotation_print.html via WeasyPrint. Returns None if unavailable."""
    try:
        from weasyprint import HTML as WeasyprintHTML
    except ImportError:
        return None
    org = quotation.organization
    html_string = render_to_string(
        "invoices/quotation_print.html",
        {
            "quotation": quotation,
            "items": quotation.items.all(),
            "org": org,
            "sender_signature_url": _signature_url(request.user, request),
        },
        request=request,
    )
    return WeasyprintHTML(string=html_string, base_url=request.build_absolute_uri("/")).write_pdf()


def send_quotation_email(quotation: SalesDocument, request) -> bool:
    """Render quotation_email.html and send to customer with PDF attachment. Returns True if sent."""
    to_email = quotation.customer.email
    if not to_email:
        return False
    org = quotation.organization
    ctx = {
        "quotation": quotation,
        "items": quotation.items.all(),
        "org": org,
        "logo_url": _logo_data_uri(org),
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


def send_sale_order_email(order: SalesDocument, request) -> bool:
    """Render sale_order_email.html and send to customer. Returns True if sent."""
    to_email = order.customer.email
    if not to_email:
        return False
    org = order.organization
    ctx = {
        "order": order,
        "items": order.items.all(),
        "org": org,
        "logo_url": _logo_data_uri(org),
    }
    html_body = render_to_string("invoices/email/sale_order_email.html", ctx, request=request)
    doc_ref = order.doc_number or _("Borrador")
    subject = f"Orden de Venta {doc_ref} – {org.name}"
    plain = f"Orden de Venta {doc_ref}\nTotal: {order.total}\n\nRevise este correo en un cliente compatible con HTML."
    msg = EmailMultiAlternatives(subject, plain, settings.DEFAULT_FROM_EMAIL, [to_email])
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)
    return True
