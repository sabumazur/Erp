---
name: sabsys-test
description: >
  Use when writing, generating, or completing tests for the sabsys Django ERP
  project. Triggers include: "write tests for", "add tests to", "test this view",
  "test this service", "test this model", "generate test cases", "what should I
  test here", "is this tested correctly", or any request to produce pytest test
  files for sabsys code. Pairs with sabsys-feature (generates code) and
  sabsys-review (audits code). When in doubt, use this skill — it ensures every
  test matches sabsys's exact pytest + factory_boy conventions.
---

# sabsys Test Writing

Write complete, idiomatic pytest test files for the sabsys ERP. Given a model,
view, service, or form, generate all four test files matching sabsys conventions.

---

## Stack conventions

- Runner: `pytest` + `pytest-django`
- Factories: `factory_boy` with `DjangoModelFactory`
- All factory classes decorated with `@mute_signals(post_save)`
- Test files live in `apps/<app>/tests/` with `__init__.py`
- Files: `factories.py`, `test_models.py`, `test_views.py`, `test_services.py`
- Mark all test classes/functions with `@pytest.mark.django_db`
- Global fixtures from root `conftest.py` (no import needed):
  `user`, `org`, `owner_membership`, `admin_membership`,
  `member_membership`, `viewer_membership`
- Never use Django's `TestCase` — always pytest classes
- Use `assert`, never `assertEqual`/`assertTrue`

---

## Login helper

Always the same pattern — define `_login()` in every `test_views.py` class:

```python
def _login(self, client, membership):
    client.force_login(membership.user)
    session = client.session
    session["active_org_slug"] = membership.organization.slug
    session.save()
```

---

## 1. factories.py

```python
import factory
from factory.django import DjangoModelFactory, mute_signals
from django.db.models.signals import post_save
from apps.accounts.tests.factories import OrganizationFactory
from apps.<app>.models import MyEntity


@mute_signals(post_save)
class MyEntityFactory(DjangoModelFactory):
    class Meta:
        model = MyEntity

    organization = factory.SubFactory(OrganizationFactory)
    name = factory.Sequence(lambda n: f"Entity {n}")
    status = MyEntity.Status.DRAFT
```

Rules:
- One factory per model
- `factory.Sequence` for unique fields (`name`, `code`, etc.)
- `factory.SubFactory(OrganizationFactory)` for `organization` FK
- Set `status` to the initial/draft state
- Never hardcode PKs or strings that fail on second run

---

## 2. test_models.py

Always test:
- `__str__` returns a non-empty string
- ERPBaseModel fields: UUID PK, `created_at`/`updated_at` set on save
- Soft delete: `model.delete()` sets `deleted_at`; `.objects` excludes it; `.all_objects` includes it
- Uniqueness: duplicate in same org is rejected; soft-deleted record does **not** block reuse
- Status transitions (if model has `Status` field)
- Any custom model method or property

```python
import pytest
import uuid
from apps.<app>.tests.factories import MyEntityFactory
from apps.<app>.models import MyEntity


@pytest.mark.django_db
class TestMyEntityModel:

    def test_str(self):
        assert str(MyEntityFactory()) != ""

    def test_uuid_pk(self):
        assert isinstance(MyEntityFactory().pk, uuid.UUID)

    def test_soft_delete(self):
        entity = MyEntityFactory()
        pk = entity.pk
        entity.delete()
        assert not MyEntity.objects.filter(pk=pk).exists()
        assert MyEntity.all_objects.filter(pk=pk).exists()

    def test_soft_deleted_does_not_block_reuse(self):
        entity = MyEntityFactory(name="Test")
        entity.delete()
        duplicate = MyEntityFactory(name="Test", organization=entity.organization)
        assert duplicate.pk != entity.pk
```

---

## 3. test_views.py

Generate these cases as a minimum for every view:

### List view
- Unauthenticated → 302
- Authenticated member → 200
- Org-scoped: create one in another org, assert it's absent from response

### Detail view
- Own org record → 200
- Another org's record → 404

### Create view (POST)
- Valid data → creates record, redirect or HTMX table refresh
- Invalid data → 200, no redirect, form errors present
- Non-admin → 403

### Update view
- GET returns form with instance data
- POST with valid data → record updated
- POST to another org's record → 404

### Delete view (POST)
- Non-admin → 403
- Admin → soft-deletes (`deleted_at` is not None)
- GET → 405

```python
import pytest
from django.urls import reverse
from apps.<app>.tests.factories import MyEntityFactory


@pytest.mark.django_db
class TestMyEntityViews:

    def _login(self, client, membership):
        client.force_login(membership.user)
        session = client.session
        session["active_org_slug"] = membership.organization.slug
        session.save()

    # ── List ──────────────────────────────────────────────────────────────

    def test_list_requires_login(self, client):
        response = client.get(reverse("my_app:entity_list"))
        assert response.status_code == 302

    def test_list_accessible(self, client, member_membership):
        self._login(client, member_membership)
        response = client.get(reverse("my_app:entity_list"))
        assert response.status_code == 200

    def test_list_org_scoped(self, client, member_membership):
        own = MyEntityFactory(organization=member_membership.organization)
        other = MyEntityFactory()  # different org
        self._login(client, member_membership)
        response = client.get(reverse("my_app:entity_list"))
        content = response.content.decode()
        assert str(own.name) in content
        assert str(other.name) not in content

    # ── Detail ────────────────────────────────────────────────────────────

    def test_detail_own_org(self, client, member_membership):
        entity = MyEntityFactory(organization=member_membership.organization)
        self._login(client, member_membership)
        response = client.get(reverse("my_app:entity_detail", args=[entity.pk]))
        assert response.status_code == 200

    def test_detail_other_org_returns_404(self, client, member_membership):
        entity = MyEntityFactory()  # different org
        self._login(client, member_membership)
        response = client.get(reverse("my_app:entity_detail", args=[entity.pk]))
        assert response.status_code == 404

    # ── Create ────────────────────────────────────────────────────────────

    def test_create_requires_admin(self, client, member_membership):
        self._login(client, member_membership)
        response = client.post(reverse("my_app:entity_create"), data={})
        assert response.status_code == 403

    # ── Delete ────────────────────────────────────────────────────────────

    def test_delete_requires_admin(self, client, member_membership):
        entity = MyEntityFactory(organization=member_membership.organization)
        self._login(client, member_membership)
        response = client.post(reverse("my_app:entity_delete", args=[entity.pk]))
        assert response.status_code == 403

    def test_delete_soft_deletes(self, client, admin_membership):
        entity = MyEntityFactory(organization=admin_membership.organization)
        self._login(client, admin_membership)
        client.post(reverse("my_app:entity_delete", args=[entity.pk]))
        entity.refresh_from_db()
        assert entity.deleted_at is not None

    def test_delete_get_not_allowed(self, client, admin_membership):
        entity = MyEntityFactory(organization=admin_membership.organization)
        self._login(client, admin_membership)
        response = client.get(reverse("my_app:entity_delete", args=[entity.pk]))
        assert response.status_code == 405
```

---

## 4. test_services.py

For every service method:
- Happy path: correct state transition occurs
- Guard: wrong initial state raises `ValueError`
- Atomicity: if a downstream step fails, earlier step is rolled back
- Side effects: expected related records created/updated

```python
import pytest
from apps.<app>.tests.factories import MyEntityFactory
from apps.<app>.services import MyEntityService


@pytest.mark.django_db
class TestMyEntityService:

    def test_activate_success(self):
        entity = MyEntityFactory(status="DRAFT")
        MyEntityService.activate(entity)
        entity.refresh_from_db()
        assert entity.status == "ACTIVE"

    def test_activate_wrong_status_raises(self):
        entity = MyEntityFactory(status="ACTIVE")
        with pytest.raises(ValueError):
            MyEntityService.activate(entity)

    def test_activate_is_atomic(self, mocker):
        entity = MyEntityFactory(status="DRAFT")
        mocker.patch("apps.<app>.services.some_side_effect", side_effect=Exception)
        with pytest.raises(Exception):
            MyEntityService.activate(entity)
        entity.refresh_from_db()
        assert entity.status == "DRAFT"  # rolled back
```

---

## Output rules

1. Generate all four files unless told otherwise
2. Include `_login()` helper in every `test_views.py` class that tests authenticated views
3. Cover every view registered in `urls.py` — don't skip any
4. Name methods: `test_<what>_<expected_outcome>`
5. Never test Django internals (don't test that ForeignKey works)
6. Add `# ── Section name ──` comments to group related tests inside a class
7. After generating, list any cases needing project-specific knowledge to complete,
   e.g. `"test_create_with_invalid_data needs the required form fields — please fill in"`

---

## Quick-reference conventions

| Topic | Expected pattern |
|-------|-----------------|
| Test runner | `pytest` — never `unittest.TestCase` |
| DB access | `@pytest.mark.django_db` on class or function |
| Factories | `@mute_signals(post_save)` on every factory |
| Unique fields | `factory.Sequence(lambda n: f"Name {n}")` |
| Org FK | `factory.SubFactory(OrganizationFactory)` |
| Login | `force_login` + `session["active_org_slug"]` |
| Global fixtures | `user`, `org`, `owner_membership`, `admin_membership`, `member_membership`, `viewer_membership` |
| Soft-delete check | `assert entity.deleted_at is not None` |
| Org-scope check | create record in second org, assert absent from response content |
| Service guard | `with pytest.raises(ValueError):` |
| Assertions | `assert x == y` — never `assertEqual` |
