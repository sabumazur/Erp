import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0009_invoiceitem_item_fk"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomerDepartment",
            fields=[
                ("id",          models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at",  models.DateTimeField(auto_now_add=True)),
                ("updated_at",  models.DateTimeField(auto_now=True)),
                ("deleted_at",  models.DateTimeField(blank=True, null=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="customer_departments",
                    to="accounts.organization",
                    verbose_name="organización",
                )),
                ("customer", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="departments",
                    to="invoices.customer",
                    verbose_name="cliente",
                )),
                ("name",         models.CharField(max_length=200, verbose_name="nombre del departamento")),
                ("contact_name", models.CharField(blank=True, max_length=150, verbose_name="persona de contacto")),
                ("phone",        models.CharField(blank=True, max_length=50, verbose_name="teléfono")),
                ("address",      models.CharField(blank=True, max_length=255, verbose_name="dirección de entrega")),
                ("notes",        models.TextField(blank=True, verbose_name="notas")),
                ("is_active",    models.BooleanField(default=True, verbose_name="activo")),
            ],
            options={
                "verbose_name": "departamento",
                "verbose_name_plural": "departamentos",
                "ordering": ["name"],
                "abstract": False,
            },
        ),
        migrations.AddConstraint(
            model_name="customerdepartment",
            constraint=models.UniqueConstraint(
                condition=models.Q(deleted_at__isnull=True),
                fields=["customer", "name"],
                name="unique_active_dept_name_per_customer",
            ),
        ),
        migrations.AddField(
            model_name="invoice",
            name="department",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sale_orders",
                to="invoices.customerdepartment",
                verbose_name="departamento de entrega",
            ),
        ),
    ]
