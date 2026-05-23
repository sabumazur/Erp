"""
Seeds 25 sample records per model for Invoice App and Items App into the
superuser's organization. Run after reset_db (or against any clean org).

Usage:
    python manage.py seed_db
    python manage.py seed_db --no-input
"""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db.models.signals import post_save


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


def _today_str() -> str:
    return date.today().strftime("%Y%m%d")


class Command(BaseCommand):
    help = "Seed 25 sample records per model into the superuser's organization."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-input",
            action="store_true",
            dest="no_input",
            help="Skip the confirmation prompt.",
        )

    def handle(self, *args, **options):
        from apps.accounts.models import Organization

        # Find the superuser's org to seed into
        org = Organization.objects.filter(owner__is_superuser=True).first()
        if not org:
            raise CommandError(
                "No superuser org found. Run reset_db first or create a superuser."
            )

        if not options["no_input"]:
            self.stdout.write(
                f"\nThis will seed 25 sample records per model into org '{org.name}'.\n"
            )
            confirm = input("Type 'yes' to continue: ")
            if confirm.strip().lower() != "yes":
                self.stdout.write(self.style.WARNING("Aborted."))
                return

        counts = self._seed(org)
        self._print_summary(counts)

    # ── Seed orchestration ────────────────────────────────────────────────────

    def _seed(self, org):
        from apps.accounts.models import User
        from apps.accounts.signals import create_default_organization

        counts = {}

        post_save.disconnect(create_default_organization, sender=User)
        try:
            items = self._seed_items(org)
            counts["Item"] = len(items)

            from apps.items.models import ItemCodeSequence
            counts["ItemCodeSequence"] = ItemCodeSequence.objects.filter(organization=org).count()

            payment_terms = self._seed_payment_terms(org)
            counts["PaymentTerm"] = len(payment_terms)

            customers = self._seed_customers(org, payment_terms)
            counts["Customer"] = len(customers)

            departments = self._seed_customer_departments(org, customers)
            counts["CustomerDepartment"] = len(departments)

            ncf_seqs = self._seed_ncf_sequences(org)
            counts["NCFSequence"] = len(ncf_seqs)

            doc_seqs = self._seed_document_sequences(org)
            counts["DocumentSequence"] = len(doc_seqs)

            invoices, inv_items = self._seed_invoices(org, customers, items, departments)
            counts["Invoice (INVOICE)"]    = sum(1 for i in invoices if i.doc_type == "INVOICE")
            counts["Invoice (QUOTATION)"]  = sum(1 for i in invoices if i.doc_type == "QUOTATION")
            counts["Invoice (SALE_ORDER)"] = sum(1 for i in invoices if i.doc_type == "SALE_ORDER")
            counts["SalesDocumentItem"] = len(inv_items)

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
        from apps.sales.models import PaymentTerm

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
        from apps.sales.models import Customer, NCFType

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
        from apps.sales.models import CustomerDepartment

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
        from apps.sales.models import NCFSequence

        B_TYPES = sorted(NCFSequence.PHYSICAL_TYPES)
        E_TYPES = sorted(NCFSequence.ELECTRONIC_TYPES)

        seqs = []

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

        for ncf_type in E_TYPES:
            seqs.append(
                NCFSequence.objects.create(
                    organization=org,
                    ncf_type=ncf_type,
                    series=NCFSequence.Series.ELECTRONIC,
                    current_seq=random.randint(0, 100),
                    max_seq=99_999_999,
                    is_active=True,
                )
            )

        for ncf_type in B_TYPES[:5]:
            seqs.append(
                NCFSequence.objects.create(
                    organization=org,
                    ncf_type=ncf_type,
                    series=NCFSequence.Series.PHYSICAL,
                    current_seq=99_999_999,
                    max_seq=99_999_999,
                    is_active=False,
                )
            )

        return seqs  # 25: 20 active + 5 inactive

    def _seed_document_sequences(self, org):
        from apps.sales.models import DocumentSequence

        seqs = []
        for doc_type in [DocumentSequence.DocType.QUOTATION, DocumentSequence.DocType.SALE_ORDER]:
            seqs.append(
                DocumentSequence.objects.create(
                    organization=org,
                    doc_type=doc_type,
                    current_seq=0,
                )
            )
        return seqs  # 2

    def _seed_invoices(self, org, customers, items, departments):
        from apps.sales.models import SalesDocument, SalesDocumentItem

        today = date.today()
        all_invoices = []
        all_items = []
        encf_counter = 1

        # ── 25 INVOICE records ────────────────────────────────────────────────
        inv_statuses = (
            [SalesDocument.Status.DRAFT]     * 5 +
            [SalesDocument.Status.CONFIRMED] * 8 +
            [SalesDocument.Status.SENT]      * 5 +
            [SalesDocument.Status.PAID]      * 5 +
            [SalesDocument.Status.CANCELLED] * 2
        )
        for i in range(25):
            customer = customers[i % len(customers)]
            status   = inv_statuses[i]
            encf     = ""
            ncf_type = 1  # B01 Crédito Fiscal

            if status in (SalesDocument.Status.CONFIRMED, SalesDocument.Status.SENT,
                          SalesDocument.Status.PAID, SalesDocument.Status.CANCELLED):
                encf = f"B01{encf_counter:08d}"
                encf_counter += 1

            issue = today - timedelta(days=random.randint(0, 90))
            due   = issue + timedelta(days=30)

            inv = SalesDocument.objects.create(
                doc_type=SalesDocument.DocType.INVOICE,
                organization=org,
                customer=customer,
                ncf_type=ncf_type,
                encf=encf,
                status=status,
                issue_date=issue,
                due_date=due,
                payment_condition=random.choice([
                    SalesDocument.PaymentCondition.CASH,
                    SalesDocument.PaymentCondition.CREDIT,
                ]),
                currency=SalesDocument.Currency.DOP,
                notes=f"Factura de muestra #{i + 1}",
            )
            all_invoices.append(inv)
            all_items += self._add_line_items(inv, items, count=random.randint(2, 3))

        # ── 25 QUOTATION records ──────────────────────────────────────────────
        quot_statuses = (
            [SalesDocument.Status.DRAFT]     * 5 +
            [SalesDocument.Status.CONFIRMED] * 8 +
            [SalesDocument.Status.SENT]      * 5 +
            [SalesDocument.Status.ACCEPTED]  * 4 +
            [SalesDocument.Status.EXPIRED]   * 3
        )
        quot_counter = 1
        for i in range(25):
            customer = customers[i % len(customers)]
            status   = quot_statuses[i]
            issue    = today - timedelta(days=random.randint(0, 60))
            doc_num  = ""
            if status != SalesDocument.Status.DRAFT:
                doc_num = f"COT-{today.year}-{quot_counter:04d}"
                quot_counter += 1

            q = SalesDocument.objects.create(
                doc_type=SalesDocument.DocType.QUOTATION,
                organization=org,
                customer=customer,
                status=status,
                issue_date=issue,
                valid_until=issue + timedelta(days=30),
                payment_condition=SalesDocument.PaymentCondition.CREDIT,
                currency=SalesDocument.Currency.DOP,
                doc_number=doc_num,
                notes=f"Cotización de muestra #{i + 1}",
            )
            all_invoices.append(q)
            all_items += self._add_line_items(q, items, count=random.randint(1, 3))

        # ── 25 SALE_ORDER records ─────────────────────────────────────────────
        so_statuses = (
            [SalesDocument.Status.DRAFT]     * 5 +
            [SalesDocument.Status.CONFIRMED] * 8 +
            [SalesDocument.Status.DELIVERED] * 7 +
            [SalesDocument.Status.INVOICED]  * 5
        )
        so_counter = 1
        for i in range(25):
            customer = customers[i % len(customers)]
            dept     = departments[i % len(departments)]
            status   = so_statuses[i]
            issue    = today - timedelta(days=random.randint(0, 45))
            doc_num  = ""
            if status != SalesDocument.Status.DRAFT:
                doc_num = f"OV-{today.year}-{so_counter:04d}"
                so_counter += 1

            so = SalesDocument.objects.create(
                doc_type=SalesDocument.DocType.SALE_ORDER,
                organization=org,
                customer=customer,
                department=dept if dept.customer == customer else None,
                status=status,
                issue_date=issue,
                delivery_date=issue + timedelta(days=7),
                payment_condition=SalesDocument.PaymentCondition.CREDIT,
                currency=SalesDocument.Currency.DOP,
                doc_number=doc_num,
                notes=f"Orden de venta de muestra #{i + 1}",
            )
            all_invoices.append(so)
            all_items += self._add_line_items(so, items, count=random.randint(2, 4))

        return all_invoices, all_items

    def _add_line_items(self, invoice, items, count=2):
        from apps.sales.models import SalesDocumentItem

        added = []
        catalog_items = random.sample(items, min(count, len(items)))
        for cat in catalog_items:
            ii = SalesDocumentItem.objects.create(
                document=invoice,
                item=cat,
                description=cat.name,
                quantity=Decimal(str(random.randint(1, 10))),
                unit_price=cat.unit_price,
                itbis_rate=cat.itbis_rate,
            )
            added.append(ii)
        return added

    def _seed_payments(self, org, customers, invoices):
        from apps.sales.models import Payment, PaymentAllocation, SalesDocument

        payable = [
            inv for inv in invoices
            if inv.doc_type == SalesDocument.DocType.INVOICE
            and inv.status in (
                SalesDocument.Status.CONFIRMED,
                SalesDocument.Status.SENT,
                SalesDocument.Status.PAID,
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
                reference=f"REF-{_today_str()}-{i + 1:04d}",
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
