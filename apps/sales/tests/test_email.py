from unittest.mock import patch, MagicMock
import pytest
from apps.sales.tests.factories import (
    SalesDocumentFactory,
    SalesDocumentItemFactory,
    CustomerFactory,
)
from apps.accounts.tests.factories import OrganizationFactory
from apps.sales.email import send_invoice_email, send_quotation_email, send_sale_order_email
from apps.sales.models import SalesDocument


@pytest.mark.django_db
def test_send_quotation_email_context_includes_logo():
    org = OrganizationFactory()
    customer = CustomerFactory(organization=org, email="test@example.com")
    quotation = SalesDocumentFactory(
        organization=org,
        customer=customer,
        doc_type="QUOTATION",
        status="SENT",
    )

    request = MagicMock()
    fake_data_uri = "data:image/png;base64,AAAA"

    captured_ctx = {}

    def capture_render(template_name, ctx, **kwargs):
        captured_ctx.update(ctx)
        return "<html></html>"

    with patch("apps.sales.email._logo_data_uri", return_value=fake_data_uri), \
         patch("apps.sales.email.render_to_string", side_effect=capture_render), \
         patch("apps.sales.email._quotation_pdf_bytes", return_value=None), \
         patch("django.core.mail.EmailMultiAlternatives.send"):
        send_quotation_email(quotation, request)

    assert captured_ctx.get("logo_url") == fake_data_uri


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("doc_type", "status", "send_func", "pdf_patch"),
    [
        (
            SalesDocument.DocType.INVOICE,
            SalesDocument.Status.CONFIRMED,
            send_invoice_email,
            "apps.sales.email._invoice_pdf_bytes",
        ),
        (
            SalesDocument.DocType.QUOTATION,
            SalesDocument.Status.SENT,
            send_quotation_email,
            "apps.sales.email._quotation_pdf_bytes",
        ),
        (
            SalesDocument.DocType.SALE_ORDER,
            SalesDocument.Status.CONFIRMED,
            send_sale_order_email,
            "apps.sales.email._sale_order_pdf_bytes",
        ),
    ],
)
def test_sales_document_email_templates_render_with_shared_partials(
    doc_type, status, send_func, pdf_patch, mailoutbox
):
    org = OrganizationFactory()
    customer = CustomerFactory(organization=org, email="test@example.com")
    document = SalesDocumentFactory(
        organization=org,
        customer=customer,
        doc_type=doc_type,
        status=status,
    )
    SalesDocumentItemFactory(document=document)
    request = MagicMock()

    with patch(pdf_patch, return_value=None):
        assert send_func(document, request) is True

    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["test@example.com"]


@pytest.mark.django_db
def test_send_sale_order_email_returns_false_when_no_items(mailoutbox):
    org = OrganizationFactory()
    customer = CustomerFactory(organization=org, email="test@example.com")
    order = SalesDocumentFactory(
        organization=org,
        customer=customer,
        doc_type=SalesDocument.DocType.SALE_ORDER,
        status=SalesDocument.Status.DRAFT,
    )
    request = MagicMock()

    with patch("apps.sales.email._sale_order_pdf_bytes", return_value=None):
        assert send_sale_order_email(order, request) is False

    assert len(mailoutbox) == 0
