from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

from apps.sales.email import _logo_url, _signature_url, _pdf_bytes

from .models import PurchaseDocument


def _po_pdf_bytes(po: PurchaseDocument, request) -> bytes | None:
    return _pdf_bytes(
        "purchases/purchase_order_print.html",
        {
            "po": po,
            "items": po.items.all(),
            "org": po.organization,
        },
        request,
    )


def send_purchase_order_email(po: PurchaseDocument, request) -> bool:
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
    html_body = render_to_string(
        "purchases/email/purchase_order_email.html", ctx, request=request
    )
    doc_ref = po.number or _("Borrador")
    subject = f"Orden de Compra {doc_ref} – {org.name}"
    plain = (
        f"Orden de Compra {doc_ref}\n"
        f"Total: {po.total}\n\n"
        "Revise este correo en un cliente compatible con HTML."
    )
    msg = EmailMultiAlternatives(
        subject, plain, settings.DEFAULT_FROM_EMAIL, [to_email]
    )
    msg.attach_alternative(html_body, "text/html")
    pdf = _po_pdf_bytes(po, request)
    if pdf:
        msg.attach(f"orden_{doc_ref}.pdf", pdf, "application/pdf")
    msg.send(fail_silently=False)
    return True
