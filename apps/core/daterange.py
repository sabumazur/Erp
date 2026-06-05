"""Shared date-range parsing for report filters.

Used by all date-range report views (sales + purchases) so the
"Desde > Hasta" validation lives in one place. Pair with the client-side
wiring in ``static/js/date-range.js`` and the ``and not error`` template
gate on result blocks.
"""

from datetime import datetime

from django.utils.translation import gettext_lazy as _

DATE_RANGE_ERROR_MSG = _("La fecha «Desde» no puede ser posterior a la fecha «Hasta».")
DATE_INVALID_MSG = _("Fechas inválidas.")


class DateRangeError(ValueError):
    """Raised when the start date is later than the end date.

    Subclasses ``ValueError`` so existing ``except (ValueError, TypeError)``
    blocks still catch it — always list ``except DateRangeError`` *first*.
    """


def parse_date_range(date_from_str, date_to_str, fmt="%Y-%m-%d"):
    """Parse two date strings, enforcing ``date_from <= date_to``.

    Returns ``(d_from, d_to)`` as ``date`` objects.
    Raises ``DateRangeError`` if start is after end, or ``ValueError`` /
    ``TypeError`` on malformed input.
    """
    d_from = datetime.strptime(date_from_str, fmt).date()
    d_to = datetime.strptime(date_to_str, fmt).date()
    if d_from > d_to:
        raise DateRangeError
    return d_from, d_to
