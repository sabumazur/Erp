import pytest
from apps.accounts.tests.factories import (
    UserFactory, OrganizationFactory, MembershipFactory
)
from apps.accounts.models import Membership


@pytest.fixture
def user(db):
    return UserFactory()

@pytest.fixture
def org(db):
    return OrganizationFactory()

@pytest.fixture
def owner_membership(db, org):
    return MembershipFactory(organization=org, role=Membership.Role.OWNER)

@pytest.fixture
def admin_membership(db, org):
    return MembershipFactory(organization=org, role=Membership.Role.ADMIN)

@pytest.fixture
def member_membership(db, org):
    return MembershipFactory(organization=org, role=Membership.Role.MEMBER)

@pytest.fixture
def viewer_membership(db, org):
    return MembershipFactory(organization=org, role=Membership.Role.VIEWER)
