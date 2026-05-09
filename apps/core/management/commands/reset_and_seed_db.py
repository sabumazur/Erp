"""
Wipes ALL database records (preserving the superuser account) and seeds
exactly 25 sample records per model for Invoice App and Items App.

Usage:
    python manage.py reset_and_seed_db
    python manage.py reset_and_seed_db --no-input
"""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models.signals import post_save
from django.utils import timezone
from django.utils.text import slugify


# ── Dominican Republic sample data ────────────────────────────────────────────

DR_COMPANY_NAMES = [
    "Supermercados Nacional, S.A.",
    "Distribuidora del Caribe, S.R.L.",
    "Importaciones Quisqueya, S.A.",
    "Constructora Santo Domingo, S.R.L.",
    "Farmacéutica Nacional, S.A.",
    "Grupo Comercial del Este, S.R.L.",
    "Transporte Ejecutivo Dominicano, S.R.L.",
    "Alimentos del Cibao, S.R.L.",
    "Telecomunicaciones Unidas, S.A.",
    "Servicios Tecnológicos Hispaniola, S.A.S.",
    "Banco Popular Dominicano, S.A.",
    "Ferretería Americana, S.R.L.",
    "Hotel Barceló Bávaro, S.A.",
    "Industrias San Miguel, S.A.",
    "Almacén El Ahorro, S.R.L.",
    "Claro RD, S.A.",
    "Cemento Paname, S.A.",
    "Muebles D'Classe, S.R.L.",
    "Constructora OHSA, S.A.",
    "Punta Cana Resort and Club, S.A.",
    "Laboratorios Sanofi, S.A.",
    "AES Dominicana, S.A.",
    "CAP (Cervecería Nacional Dominicana), S.A.",
    "Almacenes Corripio, S.A.",
    "Corporación Zona Franca Santiago, S.A.",
]

DR_FIRST_NAMES = [
    "Juan", "Carlos", "María", "José", "Carmen", "Rafael", "Ana",
    "Antonio", "Rosa", "Manuel", "Patricia", "Francisco", "Luisa",
    "Luis", "Isabel", "Pablo", "Sandra", "Pedro", "Gloria", "Ramón",
    "Margarita", "Miguel", "Beatriz", "Elena", "Jorge",
]

DR_LAST_NAMES = [
    "García", "Rodríguez", "Martínez", "López", "González", "Pérez",
    "Sánchez", "Ramírez", "Torres", "Flores", "Rivera", "Vargas",
    "Herrera", "Jiménez", "Morales", "Guzmán", "Reyes", "Cruz",
    "Castillo", "Núñez", "Medina", "Ortiz", "Mendoza", "Rivas",
    "Álvarez",
]

DR_PROVINCES = [
    "Santo Domingo", "Santiago", "San Cristóbal", "La Vega",
    "San Pedro de Macorís", "Puerto Plata", "La Romana", "Duarte",
    "Espaillat", "Peravia", "Barahona", "Azua",
]

DR_CITIES = [
    "Santo Domingo", "Santiago de los Caballeros", "San Cristóbal",
    "Concepción de La Vega", "San Pedro de Macorís", "Puerto Plata",
    "La Romana", "San Francisco de Macorís", "Moca", "Baní",
    "Barahona", "Azua de Compostela",
]

DEPT_NAMES = [
    "Almacén Central", "Depósito Norte", "Oficina Gerencial",
    "Sucursal Este", "Bodega Principal", "Departamento Compras",
    "Recepción de Mercancías", "Distribución", "Área de Producción",
    "Depósito Sur", "Logística y Despacho", "Centro de Distribución",
    "Planta Industrial", "Sucursal Oeste", "Almacén Refrigerado",
    "Oficina Central", "Depósito de Materias Primas", "Ventas Corporativas",
    "Servicio al Cliente", "Departamento Técnico", "Área Administrativa",
    "Depósito de Equipos", "Zona de Carga", "Recepción Principal",
    "Área de Calidad",
]

# (name, item_type, unit, unit_price, itbis_rate)  — all SALE or BOTH
ITEM_CATALOG = [
    ("Resma de Papel 8.5×11",          "SALE", "UNIT",    Decimal("250.00"),    "RATE_18"),
    ("Cartucho de Tinta HP",            "BOTH", "UNIT",    Decimal("1200.00"),   "RATE_18"),
    ("Servicio de Consultoría IT",      "SALE", "SERVICE", Decimal("5000.00"),   "RATE_18"),
    ("Laptop Dell Inspiron 15",         "BOTH", "UNIT",    Decimal("45000.00"),  "RATE_18"),
    ("Silla Ergonómica Ejecutiva",      "SALE", "UNIT",    Decimal("6500.00"),   "RATE_18"),
    ("Cable UTP Cat6 (100m)",           "SALE", "METER",   Decimal("1800.00"),   "RATE_18"),
    ("Monitor LG 24 pulgadas",          "BOTH", "UNIT",    Decimal("12000.00"),  "RATE_18"),
    ("Caja de Guantes Nitrilo",         "SALE", "BOX",     Decimal("450.00"),    "RATE_18"),
    ("Licencia Microsoft 365 Anual",    "SALE", "SERVICE", Decimal("3600.00"),   "RATE_18"),
    ("Impresora Epson L3250",           "BOTH", "UNIT",    Decimal("18000.00"),  "RATE_18"),
    ("Teclado Mecánico USB",            "SALE", "UNIT",    Decimal("2200.00"),   "RATE_18"),
    ("Software ERP (suscripción anual)","SALE", "SERVICE", Decimal("120000.00"), "RATE_18"),
    ("Mesa de Reuniones",               "SALE", "UNIT",    Decimal("22000.00"),  "RATE_18"),
    ("Alambres Eléctricos (rollo)",     "BOTH", "METER",   Decimal("650.00"),    "RATE_18"),
    ("Servicio de Contabilidad",        "SALE", "SERVICE", Decimal("8000.00"),   "RATE_18"),
    ("Aire Acondicionado 12BTU",        "BOTH", "UNIT",    Decimal("28000.00"),  "RATE_18"),
    ("Disco Duro Externo 1TB",          "SALE", "UNIT",    Decimal("3500.00"),   "RATE_18"),
    ("Servicio de Limpieza Oficina",    "SALE", "SERVICE", Decimal("4500.00"),   "RATE_18"),
    ("Router Wifi Tp-Link",             "BOTH", "UNIT",    Decimal("2800.00"),   "RATE_18"),
    ("UPS APC 1000VA",                  "BOTH", "UNIT",    Decimal("8500.00"),   "RATE_18"),
    ("Cámara de Seguridad IP",          "SALE", "UNIT",    Decimal("4200.00"),   "RATE_18"),
    ("Teléfono IP Corporativo",         "BOTH", "UNIT",    Decimal("5800.00"),   "RATE_18"),
    ("Servicio de Diseño Gráfico",      "SALE", "SERVICE", Decimal("6000.00"),   "RATE_18"),
    ("Escritorio Ejecutivo",            "SALE", "UNIT",    Decimal("15000.00"),  "RATE_18"),
    ("Mouse Inalámbrico Logitech",      "BOTH", "UNIT",    Decimal("800.00"),    "RATE_18"),
]


def _dr_phone(i: int) -> str:
    area = ["809", "829", "849"][i % 3]
    return f"{area}-555-{i:04d}"


def _rnc(i: int) -> str:
    return f"1{i + 1:08d}"


class Command(BaseCommand):
    help = "Wipe all data and seed 25 sample records per model (Invoice + Items apps)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-input",
            action="store_true",
            dest="no_input",
            help="Skip the confirmation prompt.",
        )

    def handle(self, *args, **options):
        if not options["no_input"]:
            self.stdout.write(
                "\nThis will DELETE all database records and reseed with sample data.\n"
            )
            confirm = input("Type 'yes' to continue: ")
            if confirm.strip().lower() != "yes":
                self.stdout.write(self.style.WARNING("Aborted."))
                return

        # Capture superuser credentials before wiping
        from apps.accounts.models import User as _User

        sv_email = sv_fn = sv_ln = sv_pw_hash = None
        try:
            su = _User.all_objects.filter(is_superuser=True).first()
            if su:
                sv_email   = su.email
                sv_fn      = su.first_name
                sv_ln      = su.last_name
                sv_pw_hash = su.password
        except Exception:
            pass

        if not sv_email:
            sv_email   = "admin@sabsys.com"
            sv_fn      = "Admin"
            sv_ln      = "SabSys"
            sv_pw_hash = make_password("Admin1234!")

        # Set a DB-level default for the orphaned 'default_payment_method' column
        # (exists in the DB from migration 0005 but removed from the model).
        # Must happen outside the main transaction — ALTER TABLE disallowed with
        # pending trigger events in PostgreSQL.
        self._patch_orphaned_columns()

        with transaction.atomic():
            self._wipe()
            superuser, org = self._restore_superuser(sv_email, sv_fn, sv_ln, sv_pw_hash)
            counts = self._seed(superuser, org)

        self._print_summary(counts)

    # ── Schema patch ─────────────────────────────────────────────────────────

    def _patch_orphaned_columns(self):
        """
        Some DB columns exist from old migrations but were removed from models.
        Set defaults on them so ORM inserts work without specifying those columns.
        """
        from django.db import connection

        with connection.cursor() as cur:
            cur.execute(
                "ALTER TABLE invoices_customer "
                "ALTER COLUMN default_payment_method SET DEFAULT 'TRANSFER'"
            )

    # ── Phase 1: Wipe ─────────────────────────────────────────────────────────

    def _wipe(self):
        from apps.invoices.models import (
            Customer, Invoice, InvoiceItem, Payment, PaymentAllocation,
            PaymentTerm, NCFSequence, DocumentSequence, CustomerDepartment,
        )
        from apps.items.models import Item, ItemCodeSequence
        from apps.core.models import Module, Notification
        from apps.accounts.models import User, Organization, Team, Membership, Invitation

        self.stdout.write("Wiping database...")

        # Historical records (django-simple-history)
        Customer.history.model.objects.all().delete()
        Invoice.history.model.objects.all().delete()
        Payment.history.model.objects.all().delete()

        PaymentAllocation.objects.all().delete()
        Payment.all_objects.all().delete()
        InvoiceItem.objects.all().delete()

        # Clear self-referential PROTECT FKs before deleting Invoice rows
        Invoice.objects.all().update(encf_modified=None, consolidated_into=None)
        Invoice.objects.all().delete()

        CustomerDepartment.all_objects.all().delete()
        Customer.all_objects.all().delete()
        NCFSequence.objects.all().delete()
        DocumentSequence.objects.all().delete()
        ItemCodeSequence.objects.all().delete()
        Item.all_objects.all().delete()
        PaymentTerm.objects.all().delete()
        Notification.all_objects.all().delete()
        Invitation.all_objects.all().delete()
        Membership.all_objects.all().delete()
        Team.all_objects.all().delete()
        Organization.all_objects.all().delete()  # before User — owner FK is PROTECT
        User.all_objects.all().delete()
        Module.objects.all().delete()

        self.stdout.write(self.style.SUCCESS("  Wipe complete."))

    # ── Phase 2: Restore superuser ────────────────────────────────────────────

    def _restore_superuser(self, email, first_name, last_name, pw_hash):
        from apps.accounts.models import User, Organization

        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )
        user.password = pw_hash
        user.save()  # fires post_save → auto-creates default Org + OWNER Membership

        org = Organization.objects.get(owner=user)
        self.stdout.write(
            self.style.SUCCESS(f"  Superuser '{email}' restored. Org: '{org.name}'")
        )
        return user, org

    # ── Phase 3: Seed ────────────────────────────────────────────────────────

    def _seed(self, superuser, org):
        from apps.accounts.models import User
        from apps.accounts.signals import create_default_organization

        counts = {}

        # Disconnect auto-org signal so new User objects don't create phantom orgs
        post_save.disconnect(create_default_organization, sender=User)
        try:
            items         = self._seed_items(org)
            counts["Item"] = len(items)

            from apps.items.models import ItemCodeSequence
            counts["ItemCodeSequence"] = ItemCodeSequence.objects.filter(organization=org).count()

            payment_terms = self._seed_payment_terms(org)
            counts["PaymentTerm"] = len(payment_terms)

            customers     = self._seed_customers(org, payment_terms)
            counts["Customer"] = len(customers)

            departments   = self._seed_customer_departments(org, customers)
            counts["CustomerDepartment"] = len(departments)

            ncf_seqs      = self._seed_ncf_sequences(org)
            counts["NCFSequence"] = len(ncf_seqs)

            doc_seqs      = self._seed_document_sequences(org)
            counts["DocumentSequence"] = len(doc_seqs)

            invoices, inv_items = self._seed_invoices(org, customers, items, departments)
            counts["Invoice (INVOICE)"]    = sum(1 for i in invoices if i.doc_type == "INVOICE")
            counts["Invoice (QUOTATION)"]  = sum(1 for i in invoices if i.doc_type == "QUOTATION")
            counts["Invoice (SALE_ORDER)"] = sum(1 for i in invoices if i.doc_type == "SALE_ORDER")
            counts["InvoiceItem"] = len(inv_items)

            payments, allocs = self._seed_payments(org, customers, invoices)
            counts["Payment"] = len(payments)
            counts["PaymentAllocation"] = len(allocs)

        finally:
            post_save.connect(create_default_organization, sender=User)

        return counts

    # ── Seed helpers ──────────────────────────────────────────────────────────

    def _seed_items(self, org):
        from apps.items.models import Item

        items = []
        for name, item_type, unit, unit_price, itbis_rate in ITEM_CATALOG:
            item = Item.objects.create(
                organization=org,
                name=name,
                item_type=item_type,
                unit=unit,
                unit_price=unit_price,
                itbis_rate=itbis_rate,
                is_active=True,
            )
            items.append(item)
        return items  # 25

    def _seed_payment_terms(self, org):
        from apps.invoices.models import PaymentTerm

        TERMS = [
            # (name, days_due, org_specific)
            ("Contado",          0,   False),
            ("15 días",          15,  False),
            ("30 días",          30,  False),
            ("60 días",          60,  False),
            ("90 días",          90,  False),
            ("Neto 7",           7,   True),
            ("Neto 21",          21,  True),
            ("Neto 45",          45,  True),
            ("Neto 120",         120, True),
            ("2/10 Neto 30",     30,  True),
            ("1/15 Neto 45",     45,  True),
            ("COD",              0,   True),
            ("CIA",              0,   True),
            ("Fin de Mes",       30,  True),
            ("45 días neto",     45,  True),
            ("Semanal",          7,   True),
            ("Quincenal",        15,  True),
            ("Mensual",          30,  True),
            ("Bimestral",        60,  True),
            ("Trimestral",       90,  True),
            ("Semestral",        180, True),
            ("Prepago",          0,   True),
            ("Anticipo 50%",     30,  True),
            ("Crédito Especial", 45,  True),
            ("120 días",         120, False),
        ]

        terms = []
        for name, days_due, org_specific in TERMS:
            pt = PaymentTerm.objects.create(
                organization=org if org_specific else None,
                name=name,
                days_due=days_due,
            )
            terms.append(pt)
        return terms  # 25

    def _seed_customers(self, org, payment_terms):
        from apps.invoices.models import Customer, NCFType

        # Alternate between B01 and E31 as default NCF type — realistic mix
        ncf_type_cycle = [
            NCFType.B01_CREDITO_FISCAL, NCFType.CONSUMO,
            NCFType.B02_CONSUMO, NCFType.CREDITO_FISCAL,
            NCFType.B01_CREDITO_FISCAL,
        ]

        customers = []
        for i, name in enumerate(DR_COMPANY_NAMES):
            customers.append(
                Customer.objects.create(
                    organization=org,
                    name=name,
                    id_type=Customer.IdType.RNC,
                    rnc_cedula=_rnc(i),
                    email=f"facturacion{i + 1}@cliente{i + 1}.com.do",
                    phone=_dr_phone(i + 200),
                    contact_name=f"{DR_FIRST_NAMES[i % len(DR_FIRST_NAMES)]} {DR_LAST_NAMES[i % len(DR_LAST_NAMES)]}",
                    address=f"Calle Principal #{i + 1}",
                    city=DR_CITIES[i % len(DR_CITIES)],
                    province=DR_PROVINCES[i % len(DR_PROVINCES)],
                    country="República Dominicana",
                    default_ncf_type=ncf_type_cycle[i % len(ncf_type_cycle)],
                    payment_term=payment_terms[i % len(payment_terms)],
                    credit_limit=Decimal(str(random.choice([50000, 100000, 200000, 500000]))),
                )
            )
        return customers  # 25

    def _seed_customer_departments(self, org, customers):
        from apps.invoices.models import CustomerDepartment

        departments = []
        for i, customer in enumerate(customers):
            departments.append(
                CustomerDepartment.objects.create(
                    organization=org,
                    customer=customer,
                    name=DEPT_NAMES[i],
                    contact_name=f"{DR_FIRST_NAMES[i % len(DR_FIRST_NAMES)]} {DR_LAST_NAMES[i % len(DR_LAST_NAMES)]}",
                    phone=_dr_phone(i + 300),
                    address=f"Zona Industrial #{i + 1}, {DR_CITIES[i % len(DR_CITIES)]}",
                )
            )
        return departments  # 25

    def _seed_ncf_sequences(self, org):
        from apps.invoices.models import NCFSequence

        # 20 active sequences — one per NCF type (all B-series + all E-series)
        B_TYPES = sorted(NCFSequence.PHYSICAL_TYPES)   # 10 types: 1,2,3,4,11,12,13,14,15,16
        E_TYPES = sorted(NCFSequence.ELECTRONIC_TYPES) # 10 types: 31,32,33,34,41,43,44,45,46,47

        seqs = []

        # 10 active B-series sequences
        for ncf_type in B_TYPES:
            seqs.append(
                NCFSequence.objects.create(
                    organization=org,
                    ncf_type=ncf_type,
                    series=NCFSequence.Series.PHYSICAL,
                    current_seq=random.randint(0, 100),
                    max_seq=99_999_999,
                    is_active=True,
                )
            )

        # 10 active E-series sequences
        for ncf_type in E_TYPES:
            seqs.append(
                NCFSequence.objects.create(
                    organization=org,
                    ncf_type=ncf_type,
                    series=NCFSequence.Series.ELECTRONIC,
                    current_seq=random.randint(0, 100),
                    max_seq=99_999_999,  # PositiveIntegerField max fits this value
                    is_active=True,
                )
            )

        # 5 inactive (exhausted) B-series sequences for the first 5 types
        # — simulates sequences that were used and replaced
        for ncf_type in B_TYPES[:5]:
            seqs.append(
                NCFSequence.objects.create(
                    organization=org,
                    ncf_type=ncf_type,
                    series=NCFSequence.Series.PHYSICAL,
                    current_seq=99_999_999,
                    max_seq=99_999_999,
                    is_active=False,  # exhausted / replaced
                )
            )

        return seqs  # 25: 20 active + 5 inactive

    def _seed_document_sequences(self, org):
        from apps.invoices.models import DocumentSequence

        seqs = []
        for doc_type in [DocumentSequence.DocType.QUOTATION, DocumentSequence.DocType.SALE_ORDER]:
            seqs.append(
                DocumentSequence.objects.create(
                    organization=org,
                    doc_type=doc_type,
                    current_seq=0,
                )
            )
        return seqs  # 2 (hard cap: 2 doc_types per org)

    def _seed_invoices(self, org, customers, items, departments):
        from apps.invoices.models import Invoice, InvoiceItem

        today = date.today()
        all_invoices = []
        all_items = []
        encf_counter = 1

        # ── 25 INVOICE records ────────────────────────────────────────────────
        inv_statuses = (
            [Invoice.Status.DRAFT]     * 5 +
            [Invoice.Status.CONFIRMED] * 8 +
            [Invoice.Status.SENT]      * 5 +
            [Invoice.Status.PAID]      * 5 +
            [Invoice.Status.CANCELLED] * 2
        )
        for i in range(25):
            customer = customers[i % len(customers)]
            status   = inv_statuses[i]
            encf     = ""
            ncf_type = 1  # B01 Crédito Fiscal

            if status in (Invoice.Status.CONFIRMED, Invoice.Status.SENT,
                          Invoice.Status.PAID, Invoice.Status.CANCELLED):
                encf = f"B01{encf_counter:08d}"
                encf_counter += 1

            issue    = today - timedelta(days=random.randint(0, 90))
            due      = issue + timedelta(days=30)

            inv = Invoice.objects.create(
                doc_type=Invoice.DocType.INVOICE,
                organization=org,
                customer=customer,
                ncf_type=ncf_type,
                encf=encf,
                status=status,
                issue_date=issue,
                due_date=due,
                payment_condition=random.choice([
                    Invoice.PaymentCondition.CASH,
                    Invoice.PaymentCondition.CREDIT,
                ]),
                currency=Invoice.Currency.DOP,
                notes=f"Factura de muestra #{i + 1}",
            )
            all_invoices.append(inv)
            all_items += self._add_line_items(inv, items, count=random.randint(2, 3))

        # ── 25 QUOTATION records ──────────────────────────────────────────────
        quot_statuses = (
            [Invoice.Status.DRAFT]     * 5 +
            [Invoice.Status.CONFIRMED] * 8 +
            [Invoice.Status.SENT]      * 5 +
            [Invoice.Status.ACCEPTED]  * 4 +
            [Invoice.Status.EXPIRED]   * 3
        )
        quot_counter = 1
        for i in range(25):
            customer = customers[i % len(customers)]
            status   = quot_statuses[i]
            issue    = today - timedelta(days=random.randint(0, 60))
            doc_num  = ""
            if status != Invoice.Status.DRAFT:
                doc_num = f"COT-{today.year}-{quot_counter:04d}"
                quot_counter += 1

            q = Invoice.objects.create(
                doc_type=Invoice.DocType.QUOTATION,
                organization=org,
                customer=customer,
                status=status,
                issue_date=issue,
                valid_until=issue + timedelta(days=30),
                payment_condition=Invoice.PaymentCondition.CREDIT,
                currency=Invoice.Currency.DOP,
                doc_number=doc_num,
                notes=f"Cotización de muestra #{i + 1}",
            )
            all_invoices.append(q)
            all_items += self._add_line_items(q, items, count=random.randint(1, 3))

        # ── 25 SALE_ORDER records ─────────────────────────────────────────────
        so_statuses = (
            [Invoice.Status.DRAFT]     * 5 +
            [Invoice.Status.CONFIRMED] * 8 +
            [Invoice.Status.DELIVERED] * 7 +
            [Invoice.Status.INVOICED]  * 5
        )
        so_counter = 1
        for i in range(25):
            customer = customers[i % len(customers)]
            dept     = departments[i % len(departments)]
            status   = so_statuses[i]
            issue    = today - timedelta(days=random.randint(0, 45))
            doc_num  = ""
            if status != Invoice.Status.DRAFT:
                doc_num = f"OV-{today.year}-{so_counter:04d}"
                so_counter += 1

            so = Invoice.objects.create(
                doc_type=Invoice.DocType.SALE_ORDER,
                organization=org,
                customer=customer,
                department=dept if dept.customer == customer else None,
                status=status,
                issue_date=issue,
                delivery_date=issue + timedelta(days=7),
                payment_condition=Invoice.PaymentCondition.CREDIT,
                currency=Invoice.Currency.DOP,
                doc_number=doc_num,
                notes=f"Orden de venta de muestra #{i + 1}",
            )
            all_invoices.append(so)
            all_items += self._add_line_items(so, items, count=random.randint(2, 4))

        return all_invoices, all_items

    def _add_line_items(self, invoice, items, count=2):
        from apps.invoices.models import InvoiceItem

        added = []
        catalog_items = random.sample(items, min(count, len(items)))
        for cat in catalog_items:
            ii = InvoiceItem.objects.create(
                invoice=invoice,
                item=cat,
                description=cat.name,
                quantity=Decimal(str(random.randint(1, 10))),
                unit_price=cat.unit_price,
                itbis_rate=cat.itbis_rate,
            )
            added.append(ii)
        return added

    def _seed_payments(self, org, customers, invoices):
        from apps.invoices.models import Payment, PaymentAllocation, Invoice

        # Target invoices that can be paid: CONFIRMED, SENT, or PAID
        payable = [
            inv for inv in invoices
            if inv.doc_type == Invoice.DocType.INVOICE
            and inv.status in (
                Invoice.Status.CONFIRMED,
                Invoice.Status.SENT,
                Invoice.Status.PAID,
            )
        ]

        payments    = []
        allocations = []
        methods     = [Payment.Method.CASH, Payment.Method.CHECK, Payment.Method.TRANSFER]

        for i in range(25):
            inv      = payable[i % len(payable)]
            customer = inv.customer
            amount   = inv.total if inv.total else Decimal("1180.00")

            pmt = Payment.objects.create(
                organization=org,
                customer=customer,
                amount=amount,
                date=inv.issue_date + timedelta(days=random.randint(0, 15)),
                method=methods[i % len(methods)],
                reference=f"REF-{today_str()}-{i + 1:04d}",
                notes=f"Pago de muestra #{i + 1}",
            )
            payments.append(pmt)

            alloc = PaymentAllocation.objects.create(
                payment=pmt,
                invoice=inv,
                amount=amount,
            )
            allocations.append(alloc)

        return payments, allocations  # 25 each

    # ── Summary ───────────────────────────────────────────────────────────────

    def _print_summary(self, counts):
        self.stdout.write("\n" + self.style.SUCCESS("Seed complete. Records created:"))
        self.stdout.write(f"  {'Model':<30} {'Records':>8}")
        self.stdout.write(f"  {'-'*30} {'-'*8}")
        for model, n in counts.items():
            self.stdout.write(f"  {model:<30} {n:>8}")
        total = sum(counts.values())
        self.stdout.write(f"  {'-'*30} {'-'*8}")
        self.stdout.write(f"  {'TOTAL':<30} {total:>8}")


def today_str() -> str:
    return date.today().strftime("%Y%m%d")
