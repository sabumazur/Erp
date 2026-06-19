"""Test QuotationForm default initial values."""
import pytest
from datetime import date

from apps.accounts.tests.factories import OrganizationFactory
from apps.accounts.tests.factories import UserFactory, MembershipFactory
from apps.accounts.models import Membership
from apps.sales.forms import QuotationForm
from apps.sales.models import SalesDocument, Customer


@pytest.mark.django_db
class TestQuotationFormDefaults:
    def test_valid_until_initial_is_today_on_new_form(self):
        org = OrganizationFactory()
        form = QuotationForm(organization=org)
        # BoundField.value() is what gets rendered into the HTML input value attr
        value = form["valid_until"].value()
        assert value == date.today(), (
            f"Expected {date.today()!r}, got {value!r}. "
            f"field.initial={form.fields['valid_until'].initial!r}, "
            f"form.initial={form.initial!r}"
        )

    def test_valid_until_initial_not_overridden_on_existing_instance(self):
        """Editing an existing quotation must keep its own valid_until."""
        org = OrganizationFactory()
        user = UserFactory()
        MembershipFactory(user=user, organization=org, role=Membership.Role.OWNER)
        customer = Customer.objects.create(
            organization=org,
            name="Test SA",
            id_type=Customer.IdType.RNC,
            rnc_cedula="101123456",
        )
        q = SalesDocument.objects.create(
            organization=org,
            doc_type=SalesDocument.DocType.QUOTATION,
            status=SalesDocument.Status.DRAFT,
            customer=customer,
            issue_date=date.today(),
            valid_until=date(2030, 1, 1),
            payment_condition=SalesDocument.PaymentCondition.CASH,
        )
        form = QuotationForm(organization=org, instance=q)
        value = form["valid_until"].value()
        assert value == date(2030, 1, 1), f"Got {value!r}, expected 2030-01-01"
