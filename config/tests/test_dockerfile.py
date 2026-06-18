from pathlib import Path


def test_dockerfile_prepares_writable_media_dirs_before_non_root_user():
    dockerfile = Path("Dockerfile").read_text()
    user_app_index = dockerfile.index("USER app")
    before_user = dockerfile[:user_app_index]

    assert "mkdir -p media/avatars media/signatures media/org_logos logs" in before_user
    assert "chown -R app:app /app/media /app/logs" in before_user
