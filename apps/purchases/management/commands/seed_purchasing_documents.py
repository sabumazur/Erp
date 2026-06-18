"""
Management command: seed_purchasing_documents
==============================================
Populates an organization with realistic Dominican purchasing data for
performance testing and demo purposes.

Usage:
    python manage.py seed_purchasing_documents --org <slug>
    python manage.py seed_purchasing_documents --org <slug> --clear
    python manage.py seed_purchasing_documents --org <slug> --skip-payments

Creates inside a single org:
  - 50 purchase items  (PURCHASE type, used as catalog items)
  - 50 suppliers  (full Dominican profile with RNCs)
  - 500 purchase orders (CONFIRMED, 3-5 line items each)
  - 500 supplier invoices (CONFIRMED, one per PO via receive_and_invoice)
  - payments for half of confirmed invoices (full-invoice amount)

Line items use the 50 seeded catalog items (PURCHASE type).
"""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Organization
from apps.core.models import DocumentSequence
from apps.items.models import Item
from apps.purchases.models import (
    PurchaseDocument,
    PurchaseDocumentItem,
    Supplier,
    SupplierPayment,
)
from apps.purchases.services import (
    PurchaseOrderService,
    SupplierInvoiceService,
    SupplierPaymentService,
)
from apps.sales.models import PaymentMethod, PaymentTerm

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

DR_SUFFIXES = ["S.R.L.", "S.A.", "S.A.S.", "E.I.R.L.", "CIA. LTDA."]

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

DR_PRODUCTS = [
    "Resmas de Papel Bond 8.5×11",
    "Cartuchos de Tóner para Impresora",
    "Cables de Red Cat-6 (100m)",
    "Sillas de Oficina Ergonómicas",
    "Computadoras Portátiles",
    "Discos Duros Externos 1TB",
    "Memorias USB 64GB",
    "Switches de Red 24 Puertos",
    "UPS de 1500VA",
    "Monitores LED 24 pulgadas",
    "Teclados y Ratones Inalámbricos",
    "Papel Térmico para Cajeras",
    "Etiquetas Adhesivas A4",
    "Cajas de Archivo Tamaño Carta",
    "Bolígrafos BIC Punta Media",
    "Engrapadoras Metálicas",
    "Calculadoras de Escritorio",
    "Pizarras Acrílicas 120×80cm",
    "Proyectores HDMI 3000 Lúmenes",
    "Teléfonos IP Multifunción",
    "Aire Acondicionado 12,000 BTU",
    "Filtros de Agua para Enfriador",
    "Botellones de Agua 18.9L",
    "Detergente Industrial 5kg",
    "Servilletas de Papel (paquete)",
    "Combustible Gasoil (galón)",
    "Lubricante Industrial WD-40",
    "Cemento Portland (saco 42.5kg)",
    "Varillas de Acero 3/8 (quintal)",
    "Pinturas Interiores (galón)",
]

UNIT_PRICES = [
    Decimal("250.00"),  Decimal("500.00"),  Decimal("750.00"),
    Decimal("1000.00"), Decimal("1500.00"), Decimal("2000.00"),
    Decimal("3500.00"), Decimal("5000.00"), Decimal("7500.00"),
    Decimal("10000.00"), Decimal("15000.00"), Decimal("20000.00"),
    Decimal("25000.00"), Decimal("50000.00"),
]

ITBIS_RATES_WEIGHTED = (
    [PurchaseDocumentItem.ITBISRate.RATE_18] * 6
    + [PurchaseDocumentItem.ITBISRate.EXEMPT] * 3
    + [PurchaseDocumentItem.ITBISRate.RATE_16] * 1
)

NCF_TYPES = ["B01", "B14", "B15", "B11"]

CHUNK = 100


# ── Utilities ─────────────────────────────────────────────────────────────────

def _progress(stdout, current, total, label):
    if current % CHUNK == 0 or current == total:
        stdout.write(f"  {label}: {current}/{total}")


def _rand_date(max_days_back=365):
    return date.today() - timedelta(days=random.randint(0, max_days_back))


def _rand_rnc(used: set) -> str:
    """Generate a unique 9-digit RNC not in `used`."""
    for _ in range(10_000):
        candidate = f"{random.randint(100_000_000, 999_999_999)}"
        if candidate not in used:
            used.add(candidate)
            return candidate
    raise RuntimeError("Could not generate a unique RNC after 10,000 attempts.")


def _rand_company_name(used: set) -> str:
    for _ in range(1_000):
        name = (
            f"{random.choice(DR_COMPANY_PREFIXES)} "
            f"{random.choice(DR_COMPANY_MIDS)} "
            f"{random.choice(DR_SUFFIXES)}"
        )
        if name not in used:
            used.add(name)
            return name
    # Fall back to a numbered name to guarantee uniqueness
    n = len(used) + 1
    return f"Proveedor Seed {n} S.R.L."


def _rand_phone():
    area = random.choice(["809", "829", "849"])
    return f"{area}-{random.randint(200, 999)}-{random.randint(1000, 9999)}"


def _rand_contact():
    return f"{random.choice(DR_FIRST_NAMES)} {random.choice(DR_LAST_NAMES)}"


def _add_lines(doc, catalog_items: list, count=None):
    """Add 3-5 random line items to a PurchaseDocument using catalog items."""
    if count is None:
        count = random.randint(3, 5)
    lines = []
    for _ in range(count):
        cat = random.choice(catalog_items)
        line = PurchaseDocumentItem(
            purchase_document=doc,
            item=cat,
            description=cat.name,
            quantity=Decimal(str(random.randint(1, 20))),
            unit_price=cat.unit_price,
            itbis_rate=cat.itbis_rate,
        )
        line.compute()
        lines.append(line)
    PurchaseDocumentItem.objects.bulk_create(lines)
    doc.recompute_totals()
    doc.refresh_from_db()


# ── Command ───────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        "Seed an organization with 50 purchase items, 50 suppliers, 500 purchase orders, "
        "500 supplier invoices, and payments for half the invoices."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--org",
            required=True,
            help="Organization slug.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all seeded purchasing records for the org before seeding.",
        )
        parser.add_argument(
            "--skip-payments",
            action="store_true",
            help="Skip seeding supplier payments.",
        )

    def handle(self, *args, **options):
        slug = options["org"]
        try:
            org = Organization.objects.get(slug=slug)
        except Organization.DoesNotExist:
            raise CommandError(f"Organization '{slug}' not found.")

        self.stdout.write(
            self.style.MIGRATE_HEADING(f"\nSeeding purchasing data for org: {org.name}\n")
        )

        if options["clear"]:
            self._clear(org)

        # Ensure DocumentSequence row exists for PURCHASE_ORDER so confirm() works
        DocumentSequence.objects.get_or_create(
            organization=org,
            doc_type="PURCHASE_ORDER",
            defaults={"prefix": "OC", "current_seq": 0, "padding": 5, "include_year": False},
        )

        payment_terms = list(PaymentTerm.objects.all())

        catalog_items = self._seed_purchase_items(org, 50)
        suppliers = self._seed_suppliers(org, 50, payment_terms)
        purchase_orders = self._seed_purchase_orders(org, suppliers, catalog_items, 500)
        invoices = self._seed_supplier_invoices(org, purchase_orders)

        if not options["skip_payments"]:
            self._seed_payments(org, invoices)

        self._print_summary(org)

    # ── Clear ─────────────────────────────────────────────────────────────────

    def _clear(self, org):
        self.stdout.write(self.style.WARNING("Clearing existing purchasing records..."))
        from apps.purchases.models import SupplierPaymentAllocation
        SupplierPaymentAllocation.objects.filter(
            payment__organization=org
        ).delete()
        SupplierPayment.all_objects.filter(organization=org).delete()
        PurchaseDocumentItem.objects.filter(
            purchase_document__organization=org
        ).delete()
        PurchaseDocument.all_objects.filter(organization=org).delete()
        Supplier.all_objects.filter(organization=org).delete()
        # Remove purchase items seeded previously
        Item.objects.filter(
            organization=org,
            item_type=Item.ItemType.PURCHASE,
        ).delete()
        DocumentSequence.objects.filter(organization=org, doc_type="PURCHASE_ORDER").delete()
        self.stdout.write("  Done.\n")

    # ── Purchase Items ────────────────────────────────────────────────────────

    def _seed_purchase_items(self, org, count: int) -> list:
        self.stdout.write(f"\nSeeding {count} purchase items (PURCHASE type)...")
        itbis_choices = [
            Item.ITBISRate.RATE_18, Item.ITBISRate.RATE_18, Item.ITBISRate.RATE_18,
            Item.ITBISRate.RATE_16, Item.ITBISRate.EXEMPT,
        ]
        items = []
        for i, product in enumerate(DR_PRODUCTS[:count]):
            item = Item(
                organization=org,
                name=product,
                item_type=Item.ItemType.PURCHASE,
                unit_price=random.choice(UNIT_PRICES),
                cost_price=random.choice(UNIT_PRICES),
                itbis_rate=random.choice(itbis_choices),
                is_active=True,
            )
            items.append(item)
        # If DR_PRODUCTS has fewer than count, pad with numbered extras
        for j in range(len(DR_PRODUCTS), count):
            item = Item(
                organization=org,
                name=f"Producto de Compra {j + 1}",
                item_type=Item.ItemType.PURCHASE,
                unit_price=random.choice(UNIT_PRICES),
                cost_price=random.choice(UNIT_PRICES),
                itbis_rate=random.choice(itbis_choices),
                is_active=True,
            )
            items.append(item)
        created = Item.objects.bulk_create(items)
        self.stdout.write(f"  {len(created)} purchase items created.")
        return list(created)

    # ── Suppliers ─────────────────────────────────────────────────────────────

    def _seed_suppliers(self, org, count: int, payment_terms: list) -> list:
        self.stdout.write(f"\nSeeding {count} suppliers...")
        used_rncs = set(
            Supplier.objects.filter(organization=org)
            .values_list("rnc_cedula", flat=True)
        )
        used_names = set(
            Supplier.objects.filter(organization=org)
            .values_list("name", flat=True)
        )
        suppliers = []

        for chunk_start in range(0, count, CHUNK):
            chunk_end = min(chunk_start + CHUNK, count)
            with transaction.atomic():
                batch = []
                for _ in range(chunk_start, chunk_end):
                    rnc = _rand_rnc(used_rncs)
                    name = _rand_company_name(used_names)
                    s = Supplier(
                        organization=org,
                        name=name,
                        id_type=Supplier.IdType.RNC,
                        rnc_cedula=rnc,
                        email=f"compras@{rnc}.com.do",
                        phone=_rand_phone(),
                        contact_name=_rand_contact(),
                        address=f"Calle Principal #{random.randint(1, 999)}, "
                                f"{random.choice(DR_CITIES)}",
                        city=random.choice(DR_CITIES),
                        credit_limit=Decimal(str(random.choice([
                            50_000, 100_000, 200_000, 500_000, 1_000_000
                        ]))),
                        payment_term=random.choice(payment_terms) if payment_terms else None,
                        is_active=True,
                    )
                    batch.append(s)
                created = Supplier.objects.bulk_create(batch)
                suppliers.extend(created)
            _progress(self.stdout, chunk_end, count, "suppliers")

        self.stdout.write(f"\n  {len(suppliers)} suppliers created.")
        return suppliers

    # ── Purchase Orders ───────────────────────────────────────────────────────

    def _seed_purchase_orders(self, org, suppliers: list, catalog_items: list, count: int) -> list:
        self.stdout.write(f"\nSeeding {count} purchase orders (CONFIRMED)...")
        purchase_orders = []

        for chunk_start in range(0, count, CHUNK):
            chunk_end = min(chunk_start + CHUNK, count)
            with transaction.atomic():
                for _ in range(chunk_start, chunk_end):
                    supplier = random.choice(suppliers)
                    issue = _rand_date(270)
                    po = PurchaseDocument.objects.create(
                        doc_type=PurchaseDocument.DocType.PURCHASE_ORDER,
                        organization=org,
                        supplier=supplier,
                        status=PurchaseDocument.Status.DRAFT,
                        issue_date=issue,
                        expected_date=issue + timedelta(days=random.randint(7, 45)),
                        currency=PurchaseDocument.Currency.DOP,
                        exchange_rate=Decimal("1.0000"),
                        notes="",
                    )
                    _add_lines(po, catalog_items, count=random.randint(3, 5))
                    try:
                        PurchaseOrderService.confirm(po)
                        purchase_orders.append(po)
                    except ValueError as exc:
                        self.stdout.write(
                            self.style.WARNING(f"\n  [WARN] PO confirm failed: {exc}")
                        )
            _progress(self.stdout, chunk_end, count, "purchase orders")

        self.stdout.write(f"\n  {len(purchase_orders)} purchase orders created.")
        return purchase_orders

    # ── Supplier Invoices ─────────────────────────────────────────────────────

    def _seed_supplier_invoices(self, org, purchase_orders: list) -> list:
        """
        Convert each CONFIRMED PO -> RECEIVED + DRAFT SI via receive_and_invoice(),
        then confirm the SI with a unique supplier NCF.
        """
        count = len(purchase_orders)
        self.stdout.write(f"\nSeeding {count} supplier invoices (via receive_and_invoice)...")

        confirmed_invoices = []
        ncf_counter = 1   # monotonically increasing per-org NCF suffix
        failed = 0

        # Reload to get fresh status
        po_pks = [po.pk for po in purchase_orders]
        po_map = {
            p.pk: p
            for p in PurchaseDocument.purchase_orders.filter(pk__in=po_pks)
        }

        for chunk_start in range(0, count, CHUNK):
            chunk_slice = po_pks[chunk_start: chunk_start + CHUNK]
            with transaction.atomic():
                for pk in chunk_slice:
                    po = po_map.get(pk)
                    if po is None or po.status != PurchaseDocument.Status.CONFIRMED:
                        failed += 1
                        continue
                    try:
                        _po, si = PurchaseOrderService.receive_and_invoice(po)
                        # si is DRAFT — assign NCF and confirm
                        si.supplier_ncf = f"B01{ncf_counter:010d}"
                        si.supplier_ncf_type = random.choice(NCF_TYPES)
                        si.save(update_fields=["supplier_ncf", "supplier_ncf_type", "updated_at"])
                        ncf_counter += 1
                        SupplierInvoiceService.confirm(si)
                        si.refresh_from_db()
                        confirmed_invoices.append(si)
                    except ValueError as exc:
                        failed += 1
                        self.stdout.write(
                            self.style.WARNING(f"\n  [WARN] Invoice failed: {exc}")
                        )
            _progress(self.stdout, min(chunk_start + CHUNK, count), count, "invoices")

        self.stdout.write(
            f"\n  {len(confirmed_invoices)} supplier invoices confirmed"
            + (f" ({failed} skipped)" if failed else "")
            + "."
        )
        return confirmed_invoices

    # ── Payments ──────────────────────────────────────────────────────────────

    def _seed_payments(self, org, invoices: list) -> None:
        """
        Pay a random half of the confirmed invoices for the full invoice total.
        """
        payable = [
            inv for inv in invoices
            if inv.status in (
                PurchaseDocument.Status.CONFIRMED,
                PurchaseDocument.Status.PAID,
            ) and inv.total > Decimal("0.00")
        ]
        if not payable:
            self.stdout.write(
                self.style.WARNING("\n  No payable invoices found; skipping payment seeding.")
            )
            return

        target = len(payable) // 2
        selected = random.sample(payable, target)
        total_count = len(selected)
        methods = [m.value for m in PaymentMethod]

        self.stdout.write(f"\nSeeding payments for {total_count} invoices...")

        paid_count = 0
        total_paid = Decimal("0.00")
        failed = 0

        for chunk_start in range(0, total_count, CHUNK):
            chunk_slice = selected[chunk_start: chunk_start + CHUNK]
            with transaction.atomic():
                for inv in chunk_slice:
                    # Reload to get current status/total
                    try:
                        inv.refresh_from_db()
                    except PurchaseDocument.DoesNotExist:
                        failed += 1
                        continue
                    if inv.total <= Decimal("0.00"):
                        failed += 1
                        continue
                    try:
                        SupplierPaymentService.create_payment(
                            supplier=inv.supplier,
                            org=org,
                            payment_date=inv.issue_date + timedelta(days=random.randint(0, 30)),
                            method=random.choice(methods),
                            reference=f"SEED-{inv.pk.hex[:8].upper()}",
                            notes="",
                            allocations=[{"invoice": inv, "amount": inv.total}],
                        )
                        total_paid += inv.total
                        paid_count += 1
                    except ValueError as exc:
                        failed += 1
                        self.stdout.write(
                            self.style.WARNING(f"\n  [WARN] Payment for invoice {inv.pk}: {exc}")
                        )
            _progress(
                self.stdout,
                min(chunk_start + CHUNK, total_count),
                total_count,
                "payments",
            )

        self.stdout.write(
            f"\n  {paid_count} payments created"
            + (f" ({failed} skipped)" if failed else "")
            + f"; total paid: DOP {total_paid:,.2f}."
        )

    # ── Summary ───────────────────────────────────────────────────────────────

    def _print_summary(self, org) -> None:
        suppliers  = Supplier.objects.filter(organization=org).count()
        pos        = PurchaseDocument.purchase_orders.filter(organization=org).count()
        invoices   = PurchaseDocument.supplier_invoices.filter(organization=org).count()
        paid_invs  = PurchaseDocument.supplier_invoices.filter(
            organization=org, status=PurchaseDocument.Status.PAID
        ).count()
        payments   = SupplierPayment.objects.filter(organization=org).count()
        items      = PurchaseDocumentItem.objects.filter(
            purchase_document__organization=org
        ).count()

        col_w = 40
        self.stdout.write("\n")
        self.stdout.write(self.style.SUCCESS("Summary:"))
        self.stdout.write(f"  {'Suppliers':<{col_w}} {suppliers:>8,}")
        self.stdout.write(f"  {'Purchase Orders (CONFIRMED)':<{col_w}} {pos:>8,}")
        self.stdout.write(f"  {'Supplier Invoices (CONFIRMED)':<{col_w}} {invoices - paid_invs:>8,}")
        self.stdout.write(f"  {'Supplier Invoices (PAID)':<{col_w}} {paid_invs:>8,}")
        self.stdout.write(f"  {'Total Supplier Invoices':<{col_w}} {invoices:>8,}")
        self.stdout.write(f"  {'Total Line Items':<{col_w}} {items:>8,}")
        self.stdout.write(f"  {'Supplier Payments':<{col_w}} {payments:>8,}")
