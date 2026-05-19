from unittest.mock import patch, MagicMock
import pytest
from apps.invoices.tests.factories import InvoiceFactory, CustomerFactory
from apps.accounts.tests.factories import OrganizationFactory
from apps.invoices.email import send_quotation_email


@pytest.mark.django_db
def test_send_quotation_email_context_includes_letterhead_url():
    org = OrganizationFactory()
    customer = CustomerFactory(organization=org, email="test@example.com")
    quotation = InvoiceFactory(
        organization=org,
        customer=customer,
        doc_type="QUOTATION",
        status="SENT",
    )

    request = MagicMock()
    expected_logo_url = "http://testserver/media/hoja%20timbrada%20cafe%20tropical%20mod.jpg"

    captured_ctx = {}

    def capture_render(template_name, ctx, **kwargs):
        captured_ctx.update(ctx)
        return "<html></html>"

    with patch("apps.invoices.email._logo_url", return_value=expected_logo_url), \
         patch("apps.invoices.email.render_to_string", side_effect=capture_render), \
         patch("apps.invoices.email._quotation_pdf_bytes", return_value=None), \
         patch("django.core.mail.EmailMultiAlternatives.send"):
        send_quotation_email(quotation, request)

    assert "logo_url" in captured_ctx
    logo_url = captured_ctx["logo_url"]
    assert logo_url.startswith("http://testserver")
    assert "hoja%20timbrada%20cafe%20tropical%20mod.jpg" in logo_url
