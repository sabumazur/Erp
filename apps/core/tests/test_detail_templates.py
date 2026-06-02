from pathlib import Path

from django.template.loader import get_template


DETAIL_TEMPLATES = [
    "templates/core/module_detail.html",
]

LEGACY_DETAIL_PATTERNS = [
    "detail-key",
    "app-panel-hd",
    "app-card-head",
    "app-table-wrap",
    "app-metric-card",
    "app-metric-value",
    "app-metric-label",
    "table-detail",
]


def test_model_detail_templates_use_kv_card():
    for template_path in DETAIL_TEMPLATES:
        html = Path(template_path).read_text(encoding="utf-8")

        assert "kv-card" in html, template_path


def test_model_detail_templates_do_not_use_legacy_detail_components():
    for template_path in DETAIL_TEMPLATES:
        html = Path(template_path).read_text(encoding="utf-8")

        for pattern in LEGACY_DETAIL_PATTERNS:
            assert pattern not in html, f"{template_path} still contains {pattern}"


def test_model_detail_templates_compile():
    for template_path in DETAIL_TEMPLATES:
        get_template(template_path.removeprefix("templates/"))
