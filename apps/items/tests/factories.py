import factory
from decimal import Decimal
from factory.django import DjangoModelFactory, mute_signals
from django.db.models.signals import post_save

from apps.accounts.tests.factories import OrganizationFactory
from apps.items.models import Item


@mute_signals(post_save)
class ItemFactory(DjangoModelFactory):
    class Meta:
        model = Item

    organization = factory.SubFactory(OrganizationFactory)
    code = factory.Sequence(lambda n: f"TST-{n:04d}")
    name = factory.Sequence(lambda n: f"Artículo {n}")
    item_type = Item.ItemType.BOTH
    unit = Item.Unit.UNIT
    unit_price = Decimal("100.00")
    itbis_rate = Item.ITBISRate.RATE_18
    is_active = True
