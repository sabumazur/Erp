"""
0001_initial

Creates the items_item table.
"""
import uuid
from decimal import Decimal
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Item",
            fields=[
                ("id",           models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at",   models.DateTimeField(auto_now_add=True)),
                ("updated_at",   models.DateTimeField(auto_now=True)),
                ("deleted_at",   models.DateTimeField(blank=True, db_index=True, null=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="items",
                    to="accounts.organization",
                    verbose_name="organización",
                )),
                ("code", models.CharField(
                    blank=True, max_length=20, verbose_name="código",
                    help_text="Código interno / SKU. Debe ser único por organización si se proporciona.",
                )),
                ("name", models.CharField(max_length=150, verbose_name="nombre")),
                ("description", models.TextField(
                    blank=True, verbose_name="descripción",
                    help_text="Se usará como descripción de la línea en el documento.",
                )),
                ("item_type", models.CharField(
                    choices=[("SALE", "Venta"), ("PURCHASE", "Compra"), ("BOTH", "Venta y Compra")],
                    db_index=True, default="BOTH", max_length=10, verbose_name="tipo",
                )),
                ("unit", models.CharField(
                    choices=[
                        ("UNIT", "Unidad"), ("HOUR", "Hora"), ("KG", "Kilogramo"),
                        ("BOX", "Caja"), ("SERVICE", "Servicio"), ("METER", "Metro"),
                        ("LITER", "Litro"), ("OTHER", "Otro"),
                    ],
                    default="UNIT", max_length=10, verbose_name="unidad de medida",
                )),
                ("unit_price", models.DecimalField(
                    decimal_places=2, default=Decimal("0.00"), max_digits=14, verbose_name="precio de venta",
                )),
                ("cost_price", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=14, null=True, verbose_name="precio de costo",
                    help_text="Opcional. Utilizado para el cálculo de márgenes y futuras órdenes de compra.",
                )),
                ("itbis_rate", models.CharField(
                    choices=[
                        ("EXEMPT", "Exento (0%)"), ("RATE_0", "Tasa 0% (exportación)"),
                        ("RATE_16", "ITBIS 16%"), ("RATE_18", "ITBIS 18%"),
                    ],
                    default="RATE_18", max_length=8, verbose_name="tasa ITBIS",
                )),
                ("is_active", models.BooleanField(default=True, verbose_name="activo")),
                ("notes", models.TextField(blank=True, verbose_name="notas internas")),
            ],
            options={
                "verbose_name": "artículo",
                "verbose_name_plural": "artículos",
                "ordering": ["name"],
                "abstract": False,
            },
        ),
        migrations.AddConstraint(
            model_name="item",
            constraint=models.UniqueConstraint(
                condition=models.Q(deleted_at__isnull=True) & ~models.Q(code=""),
                fields=["organization", "code"],
                name="unique_active_item_code_per_org",
            ),
        ),
    ]
