from unittest.mock import patch, MagicMock
import pytest
from apps.sales.tests.factories import SalesDocumentFactory, CustomerFactory
from apps.accounts.tests.factories import OrganizationFactory
from apps.sales.email import send_quotation_email


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
