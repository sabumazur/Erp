"""
0012_payment_refactor_and_payment_allocation

Changes:
  - Remove Payment.invoice FK
  - Add Payment.customer FK  (data-migrated from invoice.customer for existing rows)
  - Create PaymentAllocation table
  - PaymentMethod choices are Django-only (no schema change needed)
"""
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def forward_set_customer(apps, schema_editor):
    """Copy invoice.customer → payment.customer for every existing Payment row."""
    Payment = apps.get_model("invoices", "Payment")
    for pmt in Payment.objects.select_related("invoice__customer").all():
        if pmt.invoice_id:
            pmt.customer = pmt.invoice.customer
            pmt.save(update_fields=["customer"])


def reverse_set_invoice(apps, schema_editor):
    """Best-effort reverse: leave invoice NULL since we cannot recover the link."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0011_merge_20260503_1349"),
    ]

    operations = [
        # ── 1. Add customer FK as nullable so existing rows survive ───────────
        migrations.AddField(
            model_name="payment",
            name="customer",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="payments",
                to="invoices.customer",
                verbose_name="cliente",
            ),
        ),

        # ── 2. Data-migrate: fill customer from invoice.customer ──────────────
        migrations.RunPython(forward_set_customer, reverse_set_invoice),

        # ── 3. Make customer NOT NULL now that all rows are filled ────────────
        migrations.AlterField(
            model_name="payment",
            name="customer",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="payments",
                to="invoices.customer",
                verbose_name="cliente",
            ),
        ),

        # ── 4. Remove the old invoice FK ──────────────────────────────────────
        migrations.RemoveField(
            model_name="payment",
            name="invoice",
        ),

        # ── 5. Create PaymentAllocation ───────────────────────────────────────
        migrations.CreateModel(
            name="PaymentAllocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14, verbose_name="monto aplicado")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "invoice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="allocations",
                        to="invoices.invoice",
                        verbose_name="factura",
                    ),
                ),
                (
                    "payment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="allocations",
                        to="invoices.payment",
                        verbose_name="pago",
                    ),
                ),
            ],
            options={
                "verbose_name": "aplicación de pago",
                "verbose_name_plural": "aplicaciones de pago",
            },
        ),

        # ── 6. Unique constraint: one allocation per (payment, invoice) pair ──
        migrations.AddConstraint(
            model_name="paymentallocation",
            constraint=models.UniqueConstraint(
                fields=["payment", "invoice"],
                name="unique_payment_invoice_allocation",
            ),
        ),
    ]
