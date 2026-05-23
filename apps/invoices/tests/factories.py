import factory
from decimal import Decimal
from factory.django import DjangoModelFactory
from django.utils import timezone

from apps.accounts.tests.factories import OrganizationFactory, UserFactory
from apps.invoices.models import (
    Customer, SalesDocument, SalesDocumentItem, NCFSequence, Payment,
)


class CustomerFactory(DjangoModelFactory):
    class Meta:
        model = Customer

    organization = factory.SubFactory(OrganizationFactory)
    name = factory.Sequence(lambda n: f"Cliente {n} S.R.L.")
    id_type = Customer.IdType.RNC
    rnc_cedula = factory.Sequence(lambda n: f"10112345{n:01d}")
    email = factory.Sequence(lambda n: f"cliente{n}@empresa.com.do")
    phone = "809-555-0000"
    default_ncf_type = 31


class NCFSequenceFactory(DjangoModelFactory):
    class Meta:
        model = NCFSequence

    organization = factory.SubFactory(OrganizationFactory)
    ncf_type = 31
    series = "E"
    current_seq = 0
    max_seq = 9999999999
    is_active = True


class SalesDocumentFactory(DjangoModelFactory):
    class Meta:
        model = SalesDocument

    organization = factory.SubFactory(OrganizationFactory)
    customer = factory.SubFactory(CustomerFactory,
                                   organization=factory.SelfAttribute("..organization"))
    ncf_type = 31
    issue_date = factory.LazyFunction(lambda: timezone.now().date())
    payment_condition = SalesDocument.PaymentCondition.CASH
    currency = SalesDocument.Currency.DOP
    status = SalesDocument.Status.DRAFT


class SalesDocumentItemFactory(DjangoModelFactory):
    class Meta:
        model = SalesDocumentItem

    document = factory.SubFactory(SalesDocumentFactory)
    description = factory.Sequence(lambda n: f"Servicio {n}")
    quantity = Decimal("1.0000")
    unit_price = Decimal("1000.00")
    itbis_rate = SalesDocumentItem.ITBISRate.RATE_18


class PaymentFactory(DjangoModelFactory):
    class Meta:
        model = Payment

    organization = factory.SubFactory(OrganizationFactory)
    customer = factory.SubFactory(CustomerFactory,
                                   organization=factory.SelfAttribute("..organization"))
    amount = Decimal("1180.00")
    date = factory.LazyFunction(lambda: timezone.now().date())
    method = Payment.Method.TRANSFER
