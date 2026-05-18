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
    letterhead_url = captured_ctx["letterhead_url"]
    assert letterhead_url.startswith("http://testserver")
    # The filename may be URL-encoded (spaces → %20) or literal
    assert "hoja" in letterhead_url and "timbrada" in letterhead_url and "cafe" in letterhead_url
