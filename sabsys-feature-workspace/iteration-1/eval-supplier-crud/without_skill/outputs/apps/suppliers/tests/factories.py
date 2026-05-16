import factory
from factory.django import DjangoModelFactory, mute_signals
from django.db.models.signals import post_save

from apps.accounts.tests.factories import OrganizationFactory
from apps.suppliers.models import Supplier


@mute_signals(post_save)
class SupplierFactory(DjangoModelFactory):
    class Meta:
        model = Supplier

    organization = factory.SubFactory(OrganizationFactory)
    name   = factory.Sequence(lambda n: f"Proveedor {n} S.R.L.")
    rnc    = factory.Sequence(lambda n: f"1011234{n:02d}0")
    phone  = "809-555-0100"
    email  = factory.Sequence(lambda n: f"proveedor{n}@empresa.com.do")
    status = Supplier.Status.ACTIVE
