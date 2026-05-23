from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0012_payment_refactor_and_payment_allocation"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="credit_limit",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Monto máximo de crédito autorizado. Dejar en blanco para sin límite.",
                max_digits=14,
                null=True,
                verbose_name="límite de crédito",
            ),
        ),
    ]
