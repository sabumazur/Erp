# ─────────────────────────────────────────────────────────────────────────────
# balance_class — add to the SalesDocument model
# apps/sales/models.py  (class SalesDocument)
#
# Moves the "what color is this outstanding amount?" decision out of the
# templates (where it was an inline {% if %}…{% elif %} chain choosing a raw hex)
# into one testable place. Templates then just print the class name:
#
#     <td class="text-end font-monospace {{ inv.balance_class }}">{{ inv.line_balance }}</td>
#
# Returns one of the semantic classes already defined in static/css/components.css:
#     num-neg    (overdue)        num-muted  (settled / zero)        num-warn  (open balance)
# ─────────────────────────────────────────────────────────────────────────────

class SalesDocument(models.Model):
    # … existing fields / Status TextChoices / managers …

    @property
    def outstanding(self):
        """Amount still owed. Prefers a view-supplied `line_balance`
        (the list / detail / allocation views set it after annotating
        paid_amount); otherwise computes from total - paid_amount."""
        bal = getattr(self, "line_balance", None)
        if bal is not None:
            return bal
        return self.total - (getattr(self, "paid_amount", None) or 0)

    @property
    def balance_class(self):
        """CSS class for an outstanding-balance amount cell."""
        if self.status == self.Status.OVERDUE:
            return "num-neg"
        if self.outstanding <= 0:
            return "num-muted"
        return "num-warn"

    @property
    def aging_class(self):
        """CSS class for an amount colored by AGING BUCKET rather than status.
        Used by the payment-allocation rows, whose invoices are pre-filtered to
        an open balance — so the overdue/paid/open distinction of balance_class
        doesn't apply; what matters there is how old the balance is.
        Reads the existing `aging_bucket`: current → positive, 1–30 → warn,
        anything older → negative."""
        bucket = getattr(self, "aging_bucket", None)
        if bucket == "current":
            return "num-pos"
        if bucket == "1_30":
            return "num-warn"
        return "num-neg"


# ─────────────────────────────────────────────────────────────────────────────
# Notes
#
# • Do NOT also turn `line_balance` into a property. The payment views set it as
#   an instance attribute (`inv.line_balance = inv.total - inv.paid_amount`);
#   a read-only property would raise AttributeError on that assignment.
#   `outstanding` above reads line_balance when present and is safe everywhere.
#
# • `Status.OVERDUE` assumes the existing TextChoices (referenced as
#   SalesDocument.Status.OVERDUE in apps/sales/views/payments.py). If overdue is
#   derived rather than stored, swap the first check for your own predicate
#   (e.g. `if self.is_overdue:`).
#
# • The same property applies verbatim to the purchases SupplierInvoice model.
# ─────────────────────────────────────────────────────────────────────────────


# ── Optional unit test — tests/sales/test_balance_class.py ──────────────────
#
# from decimal import Decimal
#
# def _doc(status, total, paid):
#     d = SalesDocument(status=status, total=Decimal(total))
#     d.paid_amount = Decimal(paid)
#     return d
#
# def test_balance_class():
#     S = SalesDocument.Status
#     assert _doc(S.OVERDUE,  "100", "0").balance_class   == "num-neg"
#     assert _doc(S.CONFIRMED,"100", "100").balance_class == "num-muted"
#     assert _doc(S.CONFIRMED,"100", "40").balance_class  == "num-warn"
