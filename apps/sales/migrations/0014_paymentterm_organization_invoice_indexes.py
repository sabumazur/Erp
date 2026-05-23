from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_alter_invitation_options_alter_membership_options_and_more"),
        ("invoices", "0013_customer_credit_limit"),
    ]

    operations = [
        # ── PaymentTerm: add nullable organization FK ─────────────────────────
        migrations.AddField(
            model_name="paymentterm",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="payment_terms",
                to="accounts.organization",
                verbose_name="organización",
                help_text="Dejar en blanco para términos globales compartidos.",
            ),
        ),
        # Remove the old global unique constraint on name (now handled per-org)
        migrations.AlterField(
            model_name="paymentterm",
            name="name",
            field=models.CharField(max_length=100, verbose_name="nombre"),
        ),
        migrations.AddConstraint(
            model_name="paymentterm",
            constraint=models.UniqueConstraint(
                condition=models.Q(organization__isnull=False),
                fields=["organization", "name"],
                name="unique_payment_term_name_per_org",
            ),
        ),
        # ── Invoice: composite indexes ────────────────────────────────────────
        migrations.AddIndex(
            model_name="invoice",
            index=models.Index(
                fields=["organization", "doc_type", "status"],
                name="invoice_org_doctype_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="invoice",
            index=models.Index(
                fields=["organization", "customer", "status"],
                name="inv_org_customer_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="invoice",
            index=models.Index(
                fields=["organization", "due_date", "status"],
                name="invoice_org_duedate_status_idx",
            ),
        ),
    ]
