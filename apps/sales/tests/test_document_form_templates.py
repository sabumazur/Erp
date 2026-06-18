import pytest
from django.urls import reverse

from apps.accounts.models import Membership
from apps.accounts.tests.factories import MembershipFactory, OrganizationFactory, UserFactory

FORM_URLS = [
    ("sales:invoice_create", True),
    ("sales:quotation_create", True),
    ("sales:sale_order_create", True),
    ("purchases:po_create", False),
    ("purchases:supplier_invoice_create", False),
]


@pytest.mark.django_db
@pytest.mark.parametrize("url_name,is_sales", FORM_URLS)
def test_document_form_base_renders_all_required_markers(client, url_name, is_sales):
    org = OrganizationFactory()
    user = UserFactory()
    MembershipFactory(user=user, organization=org, role=Membership.Role.ADMIN)
    client.force_login(user)
    session = client.session
    session["active_org_slug"] = org.slug
    session.save()

    resp = client.get(reverse(url_name))
    assert resp.status_code == 200
    content = resp.content.decode()

    assert 'id="item-tbody"' in content
    assert 'id="empty-item-row"' in content
    assert 'id="grand-subtotal"' in content
    assert 'id="grand-itbis18"' in content
    assert 'id="grand-itbis16"' in content
    assert 'id="grand-total"' in content
    assert 'id="itemPickerModal"' in content
    assert "window.ITEM_QUICK_CREATE_URL" in content
    assert "csrfmiddlewaretoken" in content

    if is_sales:
        assert 'id="customerPickerModal"' in content
        assert "window.CUSTOMER_QUICK_CREATE_URL" in content
        assert "window.CUSTOMER_DEFAULTS" in content
    else:
        assert 'id="supplierPickerModal"' in content
        assert "window.SUPPLIER_QUICK_CREATE_URL" in content

    if url_name == "sales:invoice_create":
        assert 'x-data="invoiceForm()"' in content
    if url_name == "sales:sale_order_create":
        assert "refreshDepartmentOptions" in content
