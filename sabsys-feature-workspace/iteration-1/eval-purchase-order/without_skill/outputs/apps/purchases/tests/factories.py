import factory
from factory.django import DjangoModelFactory, mute_signals
from django.db.models.signals import post_save
from django.utils import timezone

from apps.accounts.tests.factories import OrganizationFactory
from apps.purchases.models import PurchaseOrder, Supplier


@mute_signals(post_save)
class SupplierFactory(DjangoModelFactory):
    class Meta:
        model = Supplier

    organization = factory.SubFactory(OrganizationFactory)
    name = factory.Sequence(lambda n: f"Proveedor {n} S.R.L.")
    rnc = factory.Sequence(lambda n: f"10112345{n:01d}")
    email = factory.Sequence(lambda n: f"proveedor{n}@empresa.com.do")
    phone = "809-555-1111"
    is_active = True


@mute_signals(post_save)
class PurchaseOrderFactory(DjangoModelFactory):
    class Meta:
        model = PurchaseOrder

    organization = factory.SubFactory(OrganizationFactory)
    supplier = factory.SubFactory(
        SupplierFactory,
        organization=factory.SelfAttribute("..organization"),
    )
    issue_date = factory.LazyFunction(lambda: timezone.now().date())
    expected_date = None
    status = PurchaseOrder.Status.DRAFT
    notes = ""
