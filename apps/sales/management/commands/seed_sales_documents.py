"""
Management command: seed_sales_documents
=========================================
Populates an organization with realistic Dominican sales data for performance
testing and demo purposes.

Usage:
    python manage.py seed_sales_documents --org <slug>
    python manage.py seed_sales_documents --org <slug> --clear

Creates inside a single org:
  - 50 customers
  - 500 quotations  (250 CONFIRMED/SENT mix + 250 ACCEPTED for conversion)
  - 500 sale orders (CONFIRMED with doc_number)
  - 500 standalone invoices (CONFIRMED with NCF)
  - 33 consolidated invoices, each covering 15 DRAFT sale orders
  - 250 invoices converted from the ACCEPTED quotations

Line items use existing catalog Items from the org (SALE/BOTH types).
"""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Organization
from apps.items.models import Item
from apps.sales.models import (
    Customer,
    DocumentSequence,
    NCFSequence,
    NCFType,
    SalesDocument,
    SalesDocumentItem,
)
from apps.sales.models import Payment, PaymentMethod
from apps.sales.services import NCFService, PaymentService, QuotationService, SaleOrderService

# ── Dominican reference data ──────────────────────────────────────────────────

DR_COMPANY_PREFIXES = [
    "Distribuidora", "Comercial", "Grupo", "Corporación", "Servicios",
    "Importaciones", "Constructora", "Farmacéutica", "Industrias", "Tecnologías",
    "Alimentos", "Telecomunicaciones", "Transportes", "Almacenes", "Inversiones",
    "Soluciones", "Suministros", "Productos", "Materiales", "Equipos",
]

DR_COMPANY_MIDS = [
    "del Caribe", "Quisqueya", "Hispaniola", "del Este", "del Cibao",
    "Nacional", "Dominicana", "Santo Domingo", "Santiago", "del Sur",
    "del Norte", "Central", "Regional", "Global", "Continental",
    "Americana", "Caribeña", "Antillana", "Tropical", "Universal",
]

DR_SUFFIXES = ["S.R.L.", "S.A.", "S.A.S.", "E.I.R.L.", "CIA. LTDA.", "S.A."]

DR_PROVINCES = [
    "Distrito Nacional", "Santo Domingo", "Santiago", "La Vega",
    "San Pedro de Macorís", "San Cristóbal", "La Romana", "Puerto Plata",
    "Duarte", "Espaillat", "Monte Plata", "Peravia", "El Seibo",
    "Azua", "Barahona", "Bahoruco", "Independencia", "La Altagracia",
]

DR_CITIES = [
    "Santo Domingo", "Santiago de los Caballeros", "San Cristóbal",
    "Concepción de La Vega", "San Pedro de Macorís", "Puerto Plata",
    "La Romana", "San Francisco de Macorís", "Moca", "Baní",
    "Barahona", "Azua de Compostela", "Higüey", "Bonao", "Nagua",
]

DR_FIRST_NAMES = [
    "Juan", "Carlos", "María", "José", "Carmen", "Rafael", "Ana",
    "Antonio", "Rosa", "Manuel", "Patricia", "Francisco", "Luisa",
    "Luis", "Isabel", "Pablo", "Sandra", "Pedro", "Gloria", "Ramón",
]

DR_LAST_NAMES = [
    "García", "Rodríguez", "Martínez", "López", "González", "Pérez",
    "Sánchez", "Ramírez", "Torres", "Flores", "Rivera", "Vargas",
    "Herrera", "Jiménez", "Morales", "Guzmán", "Reyes", "Cruz",
]

DR_SERVICES = [
    "Consultoría de Sistemas Informáticos",
    "Mantenimiento Preventivo de Equipos",
    "Suministros de Oficina y Papelería",
    "Servicio Mensual de Limpieza",
    "Transporte de Carga Especializado",
    "Asesoría Contable y Fiscal",
    "Desarrollo de Software a Medida",
    "Publicidad y Marketing Digital",
    "Servicio Técnico Especializado",
    "Materiales de Construcción y Ferretería",
    "Alquiler de Equipos de Cómputo",
    "Capacitación y Formación Empresarial",
    "Seguridad Física y Electrónica",
    "Diseño Gráfico y Multimedia",
    "Hosting, Dominios y Correos Corporativos",
    "Instalación de Red Eléctrica Industrial",
    "Servicio de Aire Acondicionado",
    "Logística y Distribución Regional",
    "Impresión y Reproducción de Documentos",
    "Pintura y Acabados Industriales",
]

UNIT_PRICES = [
    Decimal("500.00"),   Decimal("750.00"),   Decimal("1000.00"),
    Decimal("1500.00"),  Decimal("2000.00"),  Decimal("3500.00"),
    Decimal("5000.00"),  Decimal("7500.00"),  Decimal("10000.00"),
    Decimal("15000.00"), Decimal("20000.00"),
]

ITBIS_RATES_WEIGHTED = (
    [SalesDocumentItem.ITBISRate.RATE_18] * 6
    + [SalesDocumentItem.ITBISRate.EXEMPT] * 3
    + [SalesDocumentItem.ITBISRate.RATE_16] * 1
)

# The single NCF type used for all seeded invoices (e-CF Crédito Fiscal).
SEED_NCF_TYPE = NCFType.CREDITO_FISCAL  # 31

CHUNK = 100  # records per atomic transaction


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rnc(i: int) -> str:
    """Generate a unique 9-digit Dominican RNC for seed index i."""
    return str(100_000_000 + i)


def _phone(i: int) -> str:
    area = ["809", "829", "849"][i % 3]
    return f"{area}-{555 + (i // 10000):03d}-{i % 10000:04d}"


def _company_name(i: int) -> str:
    prefix = DR_COMPANY_PREFIXES[i % len(DR_COMPANY_PREFIXES)]
    mid    = DR_COMPANY_MIDS[(i // len(DR_COMPANY_PREFIXES)) % len(DR_COMPANY_MIDS)]
    suffix = DR_SUFFIXES[i % len(DR_SUFFIXES)]
    return f"{prefix} {mid}, {suffix}"


def _rand_date(days_back: int = 365) -> date:
    return date.today() - timedelta(days=random.randint(0, days_back))


def _rand_price() -> Decimal:
    return random.choice(UNIT_PRICES)


def _add_items(document: SalesDocument, catalog_items: list, count: int = 2) -> None:
    """
    Bulk-create `count` line items for `document` using existing catalog items.
    Uses bulk_create to avoid N signal firings; calls recompute_totals manually.
    """
    lines = []
    for _ in range(count):
        cat = random.choice(catalog_items)
        line = SalesDocumentItem(
            document=document,
            item=cat,
            description=cat.name,
            quantity=Decimal(str(random.randint(1, 10))),
            unit_price=cat.unit_price,
            itbis_rate=cat.itbis_rate,
        )
        line.compute()
        lines.append(line)
    SalesDocumentItem.objects.bulk_create(lines)
    document.recompute_totals()
    document.refresh_from_db()


def _progress(stdout, current: int, total: int, label: str = "") -> None:
    bar_len = 30
    filled  = int(bar_len * current / total)
    bar     = "#" * filled + "-" * (bar_len - filled)
    stdout.write(f"\r  [{bar}] {current:>5}/{total}  {label}", ending="")
    stdout.flush()


# ── Command ───────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        "Seed an organization with 50 customers, 500 quotations, "
        "500 sale orders, 500 standalone invoices, ~33 consolidated invoices, "
        "and 250 invoices converted from accepted quotations. "
        "Line items use existing SALE/BOTH catalog items."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--org",
            required=True,
            help="Organization slug to seed data into.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            default=False,
            help="Hard-delete all existing sales data for this org before seeding.",
        )
        parser.add_argument(
            "--skip-payments",
            action="store_true",
            default=False,
            help="Skip the payment seeding step (for backward compatibility).",
        )

    def handle(self, *args, **options):
        slug = options["org"]
        try:
            org = Organization.objects.get(slug=slug)
        except Organization.DoesNotExist:
            raise CommandError(f"Organization '{slug}' not found.")

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\nSeeding sales data into org: {org.name} ({org.slug})"
            )
        )

        if options["clear"]:
            self._clear(org)

        self._ensure_ncf_sequence(org)

        catalog_items = list(
            Item.objects.filter(
                organization=org,
                item_type__in=[Item.ItemType.SALE, Item.ItemType.BOTH],
                deleted_at__isnull=True,
            )
        )
        if not catalog_items:
            raise CommandError(
                "No SALE/BOTH items found for this org. Create at least one item first."
            )
        self.stdout.write(f"  Using {len(catalog_items)} catalog item(s) for line items.")

        customers   = self._seed_customers(org, 50)
        quotations  = self._seed_quotations(org, customers, catalog_items, 500)
        self._seed_sale_orders(org, customers, catalog_items, 500)
        self._seed_standalone_invoices(org, customers, catalog_items, 500)
        self._seed_consolidated_invoices(org, customers, catalog_items, 33)
        self._convert_quotations(org, quotations, 250)

        if not options["skip_payments"]:
            self._seed_payments(org)

        self.stdout.write(self.style.SUCCESS("\n\nSeeding complete!\n"))
        self._print_summary(org)

    # ── Setup helpers ─────────────────────────────────────────────────────────

    def _clear(self, org) -> None:
        self.stdout.write("  Clearing existing sales data...", ending="")
        from apps.sales.models import PaymentAllocation
        with transaction.atomic():
            # Must delete allocations -> payments before documents (PROTECT FK).
            PaymentAllocation.objects.filter(invoice__organization=org).delete()
            Payment.all_objects.filter(organization=org).delete()
            SalesDocument.all_objects.filter(organization=org).delete()
            Customer.all_objects.filter(organization=org).delete()
            DocumentSequence.objects.filter(organization=org).delete()
            NCFSequence.objects.filter(organization=org).delete()
        self.stdout.write(self.style.SUCCESS(" done.\n"))

    def _ensure_ncf_sequence(self, org) -> NCFSequence:
        """Get-or-create an active NCF sequence for the seed NCF type (31 e-CF)."""
        seq, created = NCFSequence.objects.get_or_create(
            organization=org,
            ncf_type=SEED_NCF_TYPE,
            defaults={
                "series":      NCFSequence.Series.ELECTRONIC,
                "current_seq": 0,
                "max_seq":     9_999_999_999,
                "is_active":   True,
            },
        )
        if not seq.is_active:
            seq.is_active = True
            NCFSequence.objects.filter(pk=seq.pk).update(is_active=True)
        if created:
            self.stdout.write(f"  Created NCF sequence (type={SEED_NCF_TYPE}).")
        return seq

    # ── Section: customers ────────────────────────────────────────────────────

    def _seed_customers(self, org, count: int) -> list:
        self.stdout.write(f"\nCreating {count} customers...")
        customers = []

        for chunk_start in range(0, count, CHUNK):
            chunk_end = min(chunk_start + CHUNK, count)
            with transaction.atomic():
                for i in range(chunk_start, chunk_end):
                    # Customer.save() is not overridden -> no full_clean() fired.
                    # RNCs are 9-digit sequential integers, always valid.
                    c = Customer.objects.create(
                        organization=org,
                        name=_company_name(i),
                        id_type=Customer.IdType.RNC,
                        rnc_cedula=_rnc(i),
                        email=f"facturacion{i}@empresa{i}.com.do",
                        phone=_phone(i),
                        contact_name=(
                            f"{DR_FIRST_NAMES[i % len(DR_FIRST_NAMES)]} "
                            f"{DR_LAST_NAMES[i % len(DR_LAST_NAMES)]}"
                        ),
                        address=f"Calle Principal #{i + 1}, Zona Industrial",
                        city=DR_CITIES[i % len(DR_CITIES)],
                        province=DR_PROVINCES[i % len(DR_PROVINCES)],
                        country="República Dominicana",
                        default_ncf_type=SEED_NCF_TYPE,
                        credit_limit=Decimal(
                            str(random.choice([50_000, 100_000, 200_000, 500_000]))
                        ),
                    )
                    customers.append(c)
            _progress(self.stdout, chunk_end, count, "customers")

        self.stdout.write(f"\n  {count} customers created.")
        return customers

    # ── Section: quotations ───────────────────────────────────────────────────

    def _seed_quotations(self, org, customers: list, catalog_items: list, count: int) -> list:
        """
        Create `count` quotations:
          - First half  -> CONFIRMED or SENT (mix)
          - Second half -> ACCEPTED (will be converted to invoices later)
        Returns all quotation objects.
        """
        self.stdout.write(f"\nCreating {count} quotations...")
        quotations = []
        half = count // 2

        for chunk_start in range(0, count, CHUNK):
            chunk_end = min(chunk_start + CHUNK, count)
            with transaction.atomic():
                for i in range(chunk_start, chunk_end):
                    customer = random.choice(customers)
                    issue    = _rand_date(180)

                    q = SalesDocument.objects.create(
                        doc_type=SalesDocument.DocType.QUOTATION,
                        organization=org,
                        customer=customer,
                        ncf_type=SEED_NCF_TYPE,
                        issue_date=issue,
                        valid_until=issue + timedelta(days=30),
                        payment_condition=SalesDocument.PaymentCondition.CREDIT,
                        currency=SalesDocument.Currency.DOP,
                        status=SalesDocument.Status.DRAFT,
                    )
                    _add_items(q, catalog_items, count=random.randint(1, 3))

                    if i < half:
                        # First 500: CONFIRMED (odd) or SENT (even)
                        QuotationService.confirm(q)
                        if i % 2 == 0:
                            QuotationService.send(q)
                    else:
                        # Second 500: advance all the way to ACCEPTED
                        QuotationService.confirm(q)
                        QuotationService.send(q)
                        QuotationService.accept(q)

                    q.refresh_from_db()
                    quotations.append(q)
            _progress(self.stdout, chunk_end, count, "quotations")

        self.stdout.write(f"\n  {count} quotations created.")
        return quotations

    # ── Section: sale orders ──────────────────────────────────────────────────

    def _seed_sale_orders(self, org, customers: list, catalog_items: list, count: int) -> list:
        """Create `count` CONFIRMED sale orders."""
        self.stdout.write(f"\nCreating {count} sale orders (CONFIRMED)...")
        orders = []

        for chunk_start in range(0, count, CHUNK):
            chunk_end = min(chunk_start + CHUNK, count)
            with transaction.atomic():
                for i in range(chunk_start, chunk_end):
                    customer = random.choice(customers)

                    order = SalesDocument.objects.create(
                        doc_type=SalesDocument.DocType.SALE_ORDER,
                        organization=org,
                        customer=customer,
                        ncf_type=SEED_NCF_TYPE,
                        issue_date=_rand_date(270),
                        delivery_date=_rand_date(180),
                        payment_condition=SalesDocument.PaymentCondition.CREDIT,
                        currency=SalesDocument.Currency.DOP,
                        status=SalesDocument.Status.DRAFT,
                    )
                    _add_items(order, catalog_items, count=random.randint(1, 4))
                    SaleOrderService.confirm(order)
                    orders.append(order)
            _progress(self.stdout, chunk_end, count, "sale orders")

        self.stdout.write(f"\n  {count} sale orders created.")
        return orders

    # ── Section: standalone invoices ──────────────────────────────────────────

    def _seed_standalone_invoices(self, org, customers: list, catalog_items: list, count: int) -> list:
        """
        Create `count` CONFIRMED standalone invoices, each with a real NCF
        assigned by NCFService.confirm().
        """
        self.stdout.write(f"\nCreating {count} standalone invoices...")
        invoices = []

        for chunk_start in range(0, count, CHUNK):
            chunk_end = min(chunk_start + CHUNK, count)
            with transaction.atomic():
                for i in range(chunk_start, chunk_end):
                    customer = random.choice(customers)
                    issue    = _rand_date(180)

                    inv = SalesDocument.objects.create(
                        doc_type=SalesDocument.DocType.INVOICE,
                        organization=org,
                        customer=customer,
                        ncf_type=SEED_NCF_TYPE,
                        issue_date=issue,
                        due_date=issue + timedelta(days=random.choice([0, 15, 30, 60])),
                        payment_condition=random.choice([
                            SalesDocument.PaymentCondition.CASH,
                            SalesDocument.PaymentCondition.CREDIT,
                        ]),
                        currency=SalesDocument.Currency.DOP,
                        status=SalesDocument.Status.DRAFT,
                    )
                    _add_items(inv, catalog_items, count=random.randint(1, 4))
                    NCFService.confirm(inv)
                    invoices.append(inv)
            _progress(self.stdout, chunk_end, count, "invoices")

        self.stdout.write(f"\n  {count} invoices created.")
        return invoices

    # ── Section: consolidated invoices ───────────────────────────────────────

    def _seed_consolidated_invoices(self, org, customers: list, catalog_items: list, num_groups: int) -> None:
        """
        Create `num_groups` × 15 DRAFT sale orders and consolidate each group
        into one invoice via SaleOrderService.consolidate_and_invoice().

        Each group uses a different customer (cycled through `customers`).
        """
        orders_total = num_groups * 15
        self.stdout.write(
            f"\nCreating {orders_total} orders -> {num_groups} consolidated invoices..."
        )

        # Wide date window covering all seed orders we're about to create.
        period_start = date.today() - timedelta(days=400)
        period_end   = date.today()

        consolidated_count = 0
        for group_idx in range(num_groups):
            customer = customers[group_idx % len(customers)]

            with transaction.atomic():
                # 1. Create 15 DRAFT sale orders for this customer.
                for _ in range(15):
                    order = SalesDocument.objects.create(
                        doc_type=SalesDocument.DocType.SALE_ORDER,
                        organization=org,
                        customer=customer,
                        ncf_type=SEED_NCF_TYPE,
                        issue_date=_rand_date(90),
                        delivery_date=_rand_date(60),
                        payment_condition=SalesDocument.PaymentCondition.CREDIT,
                        currency=SalesDocument.Currency.DOP,
                        status=SalesDocument.Status.DRAFT,
                    )
                    _add_items(order, catalog_items, count=1)

                # 2. Consolidate all 15 DRAFT orders into one invoice.
                try:
                    inv = SaleOrderService.consolidate_and_invoice(
                        organization=org,
                        customer=customer,
                        period_start=period_start,
                        period_end=period_end,
                        ncf_type=SEED_NCF_TYPE,
                    )
                    # Assign e-NCF to the consolidated invoice.
                    NCFService.confirm(inv)
                    consolidated_count += 1
                except ValueError as exc:
                    self.stdout.write(
                        self.style.WARNING(
                            f"\n  [WARN] group {group_idx}: {exc}"
                        )
                    )

            if (group_idx + 1) % 10 == 0 or group_idx == num_groups - 1:
                _progress(
                    self.stdout,
                    group_idx + 1,
                    num_groups,
                    "consolidated groups",
                )

        self.stdout.write(
            f"\n  {consolidated_count} consolidated invoices created "
            f"(covering {consolidated_count * 15} orders)."
        )

    # ── Section: convert quotations -> invoices ────────────────────────────────

    def _convert_quotations(self, org, all_quotations: list, count: int) -> None:
        """
        Take `count` ACCEPTED quotations and convert each to a DRAFT invoice
        using QuotationService.convert_to_invoice(), then confirm with NCFService.
        """
        accepted = [
            q for q in all_quotations
            if q.status == SalesDocument.Status.ACCEPTED
        ]
        to_convert = accepted[:count]
        actual     = len(to_convert)

        if actual == 0:
            self.stdout.write(self.style.WARNING("\n  No ACCEPTED quotations found to convert."))
            return

        self.stdout.write(f"\nConverting {actual} accepted quotations to invoices...")
        converted = 0
        failed    = 0

        for chunk_start in range(0, actual, CHUNK):
            chunk_end = min(chunk_start + CHUNK, actual)
            with transaction.atomic():
                for q in to_convert[chunk_start:chunk_end]:
                    try:
                        inv = QuotationService.convert_to_invoice(q, ncf_type=SEED_NCF_TYPE)
                        NCFService.confirm(inv)
                        converted += 1
                    except ValueError as exc:
                        failed += 1
                        self.stdout.write(
                            self.style.WARNING(f"\n  [WARN] conversion failed: {exc}")
                        )
            _progress(self.stdout, chunk_end, actual, "conversions")

        self.stdout.write(
            f"\n  {converted} invoices created from quotations"
            + (f" ({failed} skipped)" if failed else "") + "."
        )

    # ── Section: payments ─────────────────────────────────────────────────────

    def _seed_payments(self, org) -> None:
        """
        Pay a random half of all CONFIRMED invoices in the org.

        For each selected invoice, registers a single Payment equal to
        invoice.total via PaymentService.register(), which handles allocation
        and marks the invoice as PAID.
        """
        payable_statuses = [
            SalesDocument.Status.CONFIRMED,
            SalesDocument.Status.SENT,
            SalesDocument.Status.OVERDUE,
        ]
        all_invoices = list(
            SalesDocument.invoices
            .filter(organization=org, status__in=payable_statuses)
            .select_related("customer")
            .order_by("pk")
        )

        if not all_invoices:
            self.stdout.write(self.style.WARNING("\n  No payable invoices found; skipping payment seeding."))
            return

        selected = random.sample(all_invoices, len(all_invoices) // 2)
        total_count = len(selected)
        self.stdout.write(f"\nSeeding payments for {total_count} invoices...")

        methods = [m.value for m in PaymentMethod]
        paid_count = 0
        total_paid = Decimal("0.00")
        failed = 0

        for chunk_start in range(0, total_count, CHUNK):
            chunk_slice = selected[chunk_start: chunk_start + CHUNK]
            with transaction.atomic():
                for inv in chunk_slice:
                    try:
                        amount = inv.total
                        if amount <= Decimal("0.00"):
                            failed += 1
                            continue
                        PaymentService.register(
                            organization=org,
                            customer=inv.customer,
                            payment_date=inv.issue_date + timedelta(days=random.randint(0, 30)),
                            method=random.choice(methods),
                            reference=f"SEED-{inv.pk}",
                            notes="",
                            allocations=[{"invoice": inv, "amount": amount}],
                        )
                        total_paid += amount
                        paid_count += 1
                    except Exception as exc:
                        failed += 1
                        self.stdout.write(
                            self.style.WARNING(f"\n  [WARN] payment for invoice {inv.pk}: {exc}")
                        )
            _progress(self.stdout, min(chunk_start + CHUNK, total_count), total_count, "payments")

        self.stdout.write(
            f"\n  {paid_count} payments created"
            + (f" ({failed} skipped)" if failed else "")
            + f"; total paid: DOP {total_paid:,.2f}."
        )

    # -- Summary ----------------------------------------------------------

    def _print_summary(self, org) -> None:
        invoices   = SalesDocument.invoices.filter(organization=org).count()
        quotations = SalesDocument.quotations.filter(organization=org).count()
        orders     = SalesDocument.sale_orders.filter(organization=org).count()
        customers  = Customer.objects.filter(organization=org).count()
        items      = SalesDocumentItem.objects.filter(document__organization=org).count()
        consolidated = (
            SalesDocument.invoices
            .filter(organization=org, consolidated_orders__isnull=False)
            .distinct()
            .count()
        )
        payments = Payment.objects.filter(organization=org).count()

        col_w = 38
        self.stdout.write(self.style.SUCCESS("Summary:"))
        self.stdout.write(f"  {'Customers':<{col_w}} {customers:>8,}")
        self.stdout.write(f"  {'Quotations (all statuses)':<{col_w}} {quotations:>8,}")
        self.stdout.write(f"  {'Sale Orders (all statuses)':<{col_w}} {orders:>8,}")
        self.stdout.write(f"  {'Invoices (standalone)':<{col_w}} {invoices - consolidated:>8,}")
        self.stdout.write(f"  {'Invoices (consolidated)':<{col_w}} {consolidated:>8,}")
        self.stdout.write(f"  {'Total Invoices':<{col_w}} {invoices:>8,}")
        self.stdout.write(f"  {'Total Line Items':<{col_w}} {items:>8,}")
        self.stdout.write(f"  {'Payments seeded':<{col_w}} {payments:>8,}")
        ncf_seq = NCFSequence.objects.filter(
            organization=org, ncf_type=SEED_NCF_TYPE, is_active=True
        ).first()
        if ncf_seq:
            self.stdout.write(
                f"  {'NCF sequence consumed':<{col_w}} {ncf_seq.current_seq:>8,}"
            )
