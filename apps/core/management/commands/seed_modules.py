from django.core.management.base import BaseCommand
from apps.core.models import Module

MODULES = [
    {
        "slug": "invoices",
        "name": "Facturación",
        "icon": "bi-receipt-cutoff",
        "description": "Facturas, clientes y reportes DGII (606/607/608)",
    },
    {
        "slug": "sales",
        "name": "Sales",
        "icon": "bi-bag-fill",
        "description": "Customers, quotes and orders",
    },
    {
        "slug": "inventory",
        "name": "Inventory",
        "icon": "bi-boxes",
        "description": "Products, stock and warehouses",
    },
    {
        "slug": "purchasing",
        "name": "Purchasing",
        "icon": "bi-cart-fill",
        "description": "Suppliers and purchase orders",
    },
    {
        "slug": "accounting",
        "name": "Accounting",
        "icon": "bi-calculator-fill",
        "description": "Invoices, payments and reports",
    },
    {
        "slug": "hr",
        "name": "HR",
        "icon": "bi-person-vcard-fill",
        "description": "Employees, payroll and leave",
    },
    {
        "slug": "projects",
        "name": "Projects",
        "icon": "bi-kanban-fill",
        "description": "Tasks, milestones and time tracking",
    },
]


class Command(BaseCommand):
    help = "Seed initial ERP module definitions"

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0
        for data in MODULES:
            _, created = Module.objects.update_or_create(
                slug=data["slug"],
                defaults=data,
            )
            if created:
                created_count += 1
            else:
                updated_count += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {created_count} module(s) created, {updated_count} updated."
            )
        )
