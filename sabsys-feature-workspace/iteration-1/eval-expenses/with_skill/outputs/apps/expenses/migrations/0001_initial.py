import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ExpenseCategory",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("name", models.CharField(max_length=150, verbose_name="nombre")),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="expense_categories",
                        to="accounts.organization",
                        verbose_name="organización",
                    ),
                ),
            ],
            options={
                "verbose_name": "categoría de gasto",
                "verbose_name_plural": "categorías de gasto",
                "ordering": ["-created_at"],
                "abstract": False,
            },
        ),
        migrations.AddConstraint(
            model_name="expensecategory",
            constraint=models.UniqueConstraint(
                fields=["organization", "name"],
                name="unique_expense_category_name_per_org",
            ),
        ),
        migrations.CreateModel(
            name="Expense",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12, verbose_name="monto")),
                ("date", models.DateField(verbose_name="fecha")),
                ("description", models.TextField(blank=True, verbose_name="descripción")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pendiente"),
                            ("APPROVED", "Aprobado"),
                            ("REJECTED", "Rechazado"),
                        ],
                        default="PENDING",
                        max_length=20,
                        verbose_name="estado",
                    ),
                ),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="approved_expenses",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="aprobado por",
                    ),
                ),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="expenses",
                        to="expenses.expensecategory",
                        verbose_name="categoría",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="expenses",
                        to="accounts.organization",
                        verbose_name="organización",
                    ),
                ),
            ],
            options={
                "verbose_name": "gasto",
                "verbose_name_plural": "gastos",
                "ordering": ["-created_at"],
                "abstract": False,
            },
        ),
    ]
