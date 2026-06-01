# ─────────────────────────────────────────────────────────────────────────────
# balance_class — purchases mirror
# apps/purchases/models.py  (class PurchaseDocument)
#
# Same idea as the sales SalesDocument property, but the purchase side has NO
# OVERDUE status (supplier-invoice outstanding lists filter on CONFIRMED / PAID
# only — see apps/purchases/views/payments.py::OutstandingSupplierInvoicesView).
# The OVERDUE check is therefore written defensively so it still works if you
# later add that status, and is simply skipped today.
# ─────────────────────────────────────────────────────────────────────────────

class PurchaseDocument(models.Model):
    # … existing fields / Status TextChoices / managers (supplier_invoices, …) …

    @property
    def outstanding(self):
        """Amount still owed to the supplier. Prefers a view-supplied
        `line_balance` (the allocation view sets it after annotating
        paid_amount); otherwise computes from total - paid_amount."""
        bal = getattr(self, "line_balance", None)
        if bal is not None:
            return bal
        return self.total - (getattr(self, "paid_amount", None) or 0)

    @property
    def balance_class(self):
        """CSS class for an outstanding-balance amount cell."""
        overdue = getattr(self.Status, "OVERDUE", None)
        if overdue is not None and self.status == overdue:
            return "num-neg"
        if self.outstanding <= 0:
            return "num-muted"
        return "num-warn"


# ── Optional unit test — tests/purchases/test_balance_class.py ──────────────
#
# from decimal import Decimal
#
# def _doc(status, total, paid):
#     d = PurchaseDocument(status=status, total=Decimal(total))
#     d.paid_amount = Decimal(paid)
#     return d
#
# def test_supplier_balance_class():
#     S = PurchaseDocument.Status
#     assert _doc(S.CONFIRMED, "100", "100").balance_class == "num-muted"
#     assert _doc(S.CONFIRMED, "100", "40").balance_class  == "num-warn"
