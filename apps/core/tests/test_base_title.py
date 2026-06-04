from django.template import Context, Template


def test_base_title_puts_sabsys_before_page_title():
    html = Template('{% extends "base.html" %}{% block title %}Clientes{% endblock %}').render(
        Context({})
    )

    assert "<title>SabSys — Clientes</title>" in html
