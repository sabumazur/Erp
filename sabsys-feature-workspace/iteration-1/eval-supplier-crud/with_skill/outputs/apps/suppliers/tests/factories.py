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
    name = factory.Sequence(lambda n: f"Proveedor {n}")
    rnc = factory.Sequence(lambda n: f"{n:09d}")
    phone = factory.Sequence(lambda n: f"809-555-{n:04d}")
    email = factory.Sequence(lambda n: f"proveedor{n}@ejemplo.com")
    status = Supplier.Status.ACTIVE
