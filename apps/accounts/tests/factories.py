import factory
from factory.django import DjangoModelFactory, mute_signals
from django.db.models.signals import post_save
from django.utils.text import slugify
from apps.accounts.models import User, Organization, Team, Membership


# FIX: mute post_save on all factories so the create_default_organization
# signal does not fire when factories build Users, producing phantom orgs
# that corrupt fixture state.  Tests that specifically test the signal use
# User.objects.create_user() directly — they are unaffected.

@mute_signals(post_save)
class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@sabsys.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_active = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        return model_class.objects.create_user(*args, **kwargs)


@mute_signals(post_save)
class OrganizationFactory(DjangoModelFactory):
    class Meta:
        model = Organization

    name = factory.Sequence(lambda n: f"Organization {n}")
    slug = factory.LazyAttribute(lambda o: slugify(o.name))
    owner = factory.SubFactory(UserFactory)
    is_active = True


@mute_signals(post_save)
class MembershipFactory(DjangoModelFactory):
    class Meta:
        model = Membership

    user = factory.SubFactory(UserFactory)
    organization = factory.SubFactory(OrganizationFactory)
    role = Membership.Role.MEMBER


@mute_signals(post_save)
class TeamFactory(DjangoModelFactory):
    class Meta:
        model = Team

    organization = factory.SubFactory(OrganizationFactory)
    name = factory.Sequence(lambda n: f"Team {n}")
