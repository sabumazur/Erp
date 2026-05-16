import factory
from factory.django import DjangoModelFactory, mute_signals
from django.db.models.signals import post_save

from apps.accounts.tests.factories import OrganizationFactory, UserFactory
from apps.expenses.models import Expense, ExpenseCategory


@mute_signals(post_save)
class ExpenseCategoryFactory(DjangoModelFactory):
    class Meta:
        model = ExpenseCategory

    organization = factory.SubFactory(OrganizationFactory)
    name = factory.Sequence(lambda n: f"Categoría {n}")


@mute_signals(post_save)
class ExpenseFactory(DjangoModelFactory):
    class Meta:
        model = Expense

    organization = factory.SubFactory(OrganizationFactory)
    category = factory.SubFactory(ExpenseCategoryFactory, organization=factory.SelfAttribute("..organization"))
    amount = factory.Faker("pydecimal", left_digits=5, right_digits=2, positive=True)
    date = factory.Faker("date_object")
    description = factory.Faker("sentence")
    status = Expense.Status.PENDING
    approved_by = None
