from django.core.paginator import Paginator
from django.template.loader import render_to_string


def test_pagination_renders_segmented_toolbar_buttons():
    page_obj = Paginator(range(60), 10).page(3)

    html = render_to_string(
        "components/datatable/pagination.html",
        {
            "dt_page_obj": page_obj,
            "dt_page_range": [1, 2, 3, 4, 5, None, 6],
        },
    )

    assert 'class="dt-pagination d-inline-flex align-items-center gap-1"' in html
    assert "dt-page-btn" in html
    assert "dt-page-btn-active" in html
    assert 'onclick="dtPage(2)"' in html
    assert 'onclick="dtPage(4)"' in html
    assert "page-link" not in html


def test_pagination_renders_on_single_page():
    page_obj = Paginator(range(5), 10).page(1)

    html = render_to_string(
        "components/datatable/pagination.html",
        {
            "dt_page_obj": page_obj,
            "dt_page_range": [1],
        },
    )

    assert 'class="dt-pagination d-inline-flex align-items-center gap-1"' in html
    assert "dt-page-btn-active" in html
    assert html.count("disabled") == 2
