from unittest.mock import patch, MagicMock
import pytest
from apps.purchases.tests.factories import (
    PurchaseDocumentFactory,
    PurchaseDocumentItemFactory,
    SupplierFactory,
)
from apps.accounts.tests.factories import OrganizationFactory


@pytest.mark.django_db
def test_send_po_email_returns_true_when_supplier_has_email(mailoutbox):
    org = OrganizationFactory()
    supplier = SupplierFactory(organization=org, email="proveedor@empresa.com")
    po = PurchaseDocumentFactory(
        organization=org,
        supplier=supplier,
        doc_type="PURCHASE_ORDER",
        status="CONFIRMED",
        number="OC-00001",
    )
    PurchaseDocumentItemFactory(purchase_document=po)
    request = MagicMock()

    from apps.purchases.email import send_purchase_order_email
    with patch("apps.purchases.email._po_pdf_bytes", return_value=None):
        result = send_purchase_order_email(po, request)

    assert result is True
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["proveedor@empresa.com"]
    assert "OC-00001" in mailoutbox[0].subject


@pytest.mark.django_db
def test_send_po_email_returns_false_when_no_supplier_email(mailoutbox):
    org = OrganizationFactory()
    supplier = SupplierFactory(organization=org, email="")
    po = PurchaseDocumentFactory(
        organization=org,
        supplier=supplier,
        doc_type="PURCHASE_ORDER",
        status="CONFIRMED",
    )
    request = MagicMock()

    from apps.purchases.email import send_purchase_order_email
    result = send_purchase_order_email(po, request)

    assert result is False
    assert len(mailoutbox) == 0


@pytest.mark.django_db
def test_send_po_email_attaches_pdf_when_weasyprint_available(mailoutbox):
    org = OrganizationFactory()
    supplier = SupplierFactory(organization=org, email="proveedor@empresa.com")
    po = PurchaseDocumentFactory(
        organization=org,
        supplier=supplier,
        doc_type="PURCHASE_ORDER",
        status="CONFIRMED",
        number="OC-00042",
    )
    PurchaseDocumentItemFactory(purchase_document=po)
    request = MagicMock()

    fake_pdf = b"%PDF-1.4 fake"
    from apps.purchases.email import send_purchase_order_email
    with patch("apps.purchases.email._po_pdf_bytes", return_value=fake_pdf):
        send_purchase_order_email(po, request)

    assert len(mailoutbox) == 1
    attachments = mailoutbox[0].attachments
    assert len(attachments) == 1
    name, content, mime = attachments[0]
    assert name == "orden_OC-00042.pdf"
    assert content == fake_pdf
    assert mime == "application/pdf"
