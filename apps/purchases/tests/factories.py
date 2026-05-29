import factory
from decimal import Decimal
from factory.django import DjangoModelFactory
from django.utils import timezone

from apps.accounts.tests.factories import OrganizationFactory, UserFactory
from apps.purchases.models import (
    Supplier, PurchaseDocument, PurchaseDocumentItem, SupplierPayment,
)


class SupplierFactory(DjangoModelFactory):
    class Meta:
        model = Supplier

    organization = factory.SubFactory(OrganizationFactory)
    name = factory.Sequence(lambda n: f"Proveedor {n} S.R.L.")
    id_type = Supplier.IdType.RNC
    rnc_cedula = factory.Sequence(lambda n: f"13112345{n:01d}")
    email = factory.Sequence(lambda n: f"proveedor{n}@empresa.com.do")
    phone = "809-555-0000"
    is_active = True


class PurchaseDocumentFactory(DjangoModelFactory):
    class Meta:
        model = PurchaseDocument

    organization = factory.SubFactory(OrganizationFactory)
    supplier = factory.SubFactory(SupplierFactory,
                                   organization=factory.SelfAttribute("..organization"))
    doc_type = PurchaseDocument.DocType.PURCHASE_ORDER
    issue_date = factory.LazyFunction(lambda: timezone.now().date())
    currency = PurchaseDocument.Currency.DOP
    status = PurchaseDocument.Status.DRAFT


class PurchaseDocumentItemFactory(DjangoModelFactory):
    class Meta:
        model = PurchaseDocumentItem

    purchase_document = factory.SubFactory(PurchaseDocumentFactory)
    description = factory.Sequence(lambda n: f"Producto {n}")
    quantity = Decimal("1.0000")
    unit_price = Decimal("1000.00")
    itbis_rate = PurchaseDocumentItem.ITBISRate.RATE_18


class SupplierPaymentFactory(DjangoModelFactory):
    class Meta:
        model = SupplierPayment

    organization = factory.SubFactory(OrganizationFactory)
    supplier = factory.SubFactory(SupplierFactory,
                                   organization=factory.SelfAttribute("..organization"))
    amount = Decimal("1000.00")
    date = factory.LazyFunction(lambda: timezone.now().date())
    method = SupplierPayment.Method.TRANSFER
