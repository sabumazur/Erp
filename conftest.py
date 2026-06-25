import pytest
from django.db import connections
from apps.accounts.tests.factories import (
    UserFactory, OrganizationFactory, MembershipFactory
)
from apps.accounts.models import Membership


@pytest.fixture(scope="session", autouse=True)
def django_db_teardown():
    """Ensure database connections are properly closed after all tests."""
    yield
    # Force close all connections after tests complete
    connections.close_all()


@pytest.fixture(autouse=True)
def reset_db_connections():
    """Reset database connections between tests to prevent connection leaks."""
    yield
    # Close any lingering connections after each test
    connections.close_all()


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
