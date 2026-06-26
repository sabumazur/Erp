from crispy_forms.layout import Div, Field, HTML
from django.utils.translation import gettext_lazy as _


def optional_field_wraps(*specs):
    """Return only the hidden field wrappers — chips live in the card header."""
    grid_cls = "doc-optfields-grid"
    if len(specs) == 1:
        grid_cls += " doc-optfields-grid--single"
    wraps = [
        Div(Field(name), css_id="opt-{}-wrap".format(name), css_class="doc-optfield-wrap")
        for name, _label in specs
    ]
    return Div(*wraps, css_class=grid_cls)


def optional_fields(*specs):
    """
    Build the optional document fields chips fragment for document header cards.

    Each spec is a (field_name, chip_label) tuple. The shared
    static/js/optional-fields.js file reveals the matching wrapper on click.
    """
    chips = "".join(
        '<button type="button" class="doc-optfield-chip" data-target="opt-{name}-wrap">'
        '<i class="bi bi-plus-lg"></i>{label}</button>'.format(
            name=name,
            label=str(label),
        )
        for name, label in specs
    )
    wraps = [
        Div(Field(name), css_id="opt-{}-wrap".format(name), css_class="doc-optfield-wrap")
        for name, _label in specs
    ]
    grid_cls = "doc-optfields-grid"
    if len(specs) == 1:
        grid_cls += " doc-optfields-grid--single"
    return Div(
        HTML(
            '<div class="doc-optfields-hint">'
            + str(_("Campos opcionales"))
            + '</div><div class="doc-optfields-add" id="opt-add-row">'
            + chips
            + "</div>"
        ),
        Div(*wraps, css_class=grid_cls),
        css_class="doc-optfields",
    )
