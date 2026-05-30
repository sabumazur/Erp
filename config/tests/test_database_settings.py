from django.conf import settings


def test_server_side_cursors_are_disabled_for_postgres():
    assert settings.DATABASES["default"].get("DISABLE_SERVER_SIDE_CURSORS") is True
