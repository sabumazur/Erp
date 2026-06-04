from datetime import date, timedelta
from decimal import Decimal

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models, transaction
from django.db.models import Case, DecimalField, F, When
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from apps.core.models import AbstractDocumentLineItem, ERPBaseModel, SoftDeleteQuerySet


# ── NCF type choices ──────────────────────────────────────────────────────────


class NCFType(models.IntegerChoices):
    # ── Físico (B-series, comprobantes tradicionales) ─────────────────────────
    B01_CREDITO_FISCAL = 1, _("01 – Crédito Fiscal")
    B02_CONSUMO = 2, _("02 – Consumo")
    B03_NOTA_DEBITO = 3, _("03 – Nota de Débito")
    B04_NOTA_CREDITO = 4, _("04 – Nota de Crédito")
    B11_PROVEEDORES = 11, _("11 – Proveedores Informales")
    B12_GASTOS_MENORES = 12, _("12 – Gastos Menores")
    B13_REG_ESPECIALES = 13, _("13 – Regímenes Especiales")
    B14_GUBERNAMENTAL = 14, _("14 – Gubernamental")
    B15_EXPORTACIONES = 15, _("15 – Exportaciones")
    B16_PAGOS_EXTERIOR = 16, _("16 – Pagos al Exterior")
    # ── Electrónico (E-series, e-CF) ──────────────────────────────────────────
    CREDITO_FISCAL = 31, _("31 – Crédito Fiscal (e-CF)")
    CONSUMO = 32, _("32 – Consumo (e-CF)")
    NOTA_DEBITO = 33, _("33 – Nota de Débito (e-CF)")
    NOTA_CREDITO = 34, _("34 – Nota de Crédito (e-CF)")
    COMPRAS = 41, _("41 – Comprobante de Compras (e-CF)")
    GASTOS_MENORES = 43, _("43 – Gastos Menores (e-CF)")
    REG_ESPECIALES = 44, _("44 – Regímenes Especiales (e-CF)")
    GUBERNAMENTAL = 45, _("45 – Gubernamental (e-CF)")
    EXPORTACIONES = 46, _("46 – Exportaciones (e-CF)")
    PAGOS_EXTERIOR = 47, _("47 – Pagos al Exterior (e-CF)")


class PaymentTerm(models.Model):
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="payment_terms",
        verbose_name=_("organización"),
        help_text=_(
            "Dejar en blanco para términos globales compartidos entre organizaciones."
        ),
    )
    name = models.CharField(max_length=100, verbose_name=_("nombre"))
    description = models.CharField(
        max_length=255, blank=True, verbose_name=_("descripción")
    )
    days_due = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(365)],
        verbose_name=_("días de vencimiento"),
        help_text=_("Número de días para este término de pago."),
    )

    class Meta:
        verbose_name = _("término de pago")
        verbose_name_plural = _("términos de pago")
        ordering = ["days_due", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                condition=models.Q(organization__isnull=False),
                name="unique_payment_term_name_per_org",
            ),
        ]

    def __str__(self):
        return self.name


class PaymentMethod(models.TextChoices):
    CASH = "CASH", _("Efectivo")
    CHECK = "CHECK", _("Cheque")
    TRANSFER = "TRANSFER", _("Transf. bancaria")


# ── Customer ──────────────────────────────────────────────────────────────────


class Customer(ERPBaseModel):
    class IdType(models.TextChoices):
        RNC = "RNC", _("RNC")
        CEDULA = "CED", _("Cédula")

    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="customers",
        verbose_name=_("organización"),
    )
    name = models.CharField(max_length=255, verbose_name=_("nombre / razón social"))
    id_type = models.CharField(
        max_length=3,
        choices=IdType.choices,
        default=IdType.RNC,
        verbose_name=_("tipo de identificación"),
    )
    rnc_cedula = models.CharField(
        max_length=20,
        verbose_name=_("RNC / Cédula"),
        help_text=_("RNC: 9 dígitos. Cédula: 11 dígitos."),
    )
    email = models.EmailField(blank=True, verbose_name=_("correo electrónico"))
    phone = models.CharField(max_length=20, blank=True, verbose_name=_("teléfono"))
    contact_name = models.CharField(
        max_length=150, blank=True, verbose_name=_("nombre de contacto")
    )
    contact_number = models.CharField(
        max_length=20, blank=True, verbose_name=_("número de contacto")
    )
    address = models.CharField(max_length=255, blank=True, verbose_name=_("dirección"))
    city = models.CharField(max_length=100, blank=True, verbose_name=_("ciudad"))
    province = models.CharField(max_length=100, blank=True, verbose_name=_("provincia"))
    country = models.CharField(
        max_length=100,
        blank=True,
        default="República Dominicana",
        verbose_name=_("país"),
    )
    notes = models.TextField(blank=True, verbose_name=_("notas"))
    credit_limit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("límite de crédito"),
        help_text=_("Dejar en blanco para sin límite."),
    )
    payment_term = models.ForeignKey(
        PaymentTerm,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="customers",
        verbose_name=_("término de pago"),
    )
    default_ncf_type = models.IntegerField(
        choices=NCFType.choices,
        default=NCFType.B01_CREDITO_FISCAL,
        verbose_name=_("tipo de comprobante"),
    )

    class Meta(ERPBaseModel.Meta):
        ordering = ["-created_at"]
        verbose_name = _("cliente")
        verbose_name_plural = _("clientes")
        indexes = [
            GinIndex(
                SearchVector("name", config="spanish"), name="customer_name_fts_idx"
            ),
            GinIndex(
                fields=["name"],
                opclasses=["gin_trgm_ops"],
                name="customer_name_trgm_idx",
            ),
            GinIndex(
                fields=["rnc_cedula"],
                opclasses=["gin_trgm_ops"],
                name="customer_rnc_trgm_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "rnc_cedula"],
                condition=models.Q(deleted_at__isnull=True) & ~models.Q(rnc_cedula=""),
                name="unique_active_customer_rnc_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(id_type__in=["RNC", "CED"]),
                name="customer_id_type_rnc_or_cedula",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        from .validators import validate_rnc_cedula

        if self.id_type not in (self.IdType.RNC, self.IdType.CEDULA):
            raise ValidationError(
                {"id_type": _("El tipo de identificación debe ser RNC o Cédula.")}
            )
        if self.rnc_cedula:
            validate_rnc_cedula(self.rnc_cedula, id_type=self.id_type)
        if (
            self.payment_term_id
            and self.organization_id
            and self.payment_term.organization_id not in (None, self.organization_id)
        ):
            raise ValidationError(
                {
                    "payment_term": _(
                        "El termino de pago no pertenece a esta organizacion."
                    )
                }
            )

    def delete(self, *args, **kwargs):
        if self.invoices.exists() or self.payments.exists():
            raise ValueError(
                f"No se puede eliminar «{self.name}» porque tiene documentos o pagos asociados."
            )
        return super().delete(*args, **kwargs)


# ── Customer Department ───────────────────────────────────────────────────────


class CustomerDepartment(ERPBaseModel):
    """
    A delivery department or branch of a customer.
    Each sale order is optionally assigned to a department; consolidation
    is then done per (customer, department) pair.
    """

    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="customer_departments",
        verbose_name=_("organización"),
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="departments",
        verbose_name=_("cliente"),
    )
    name = models.CharField(
        max_length=200,
        verbose_name=_("nombre del departamento"),
        help_text=_("Ej.: Almacén Central, Depósito, Oficina Gerencial"),
    )
    contact_name = models.CharField(
        max_length=150,
        blank=True,
        verbose_name=_("persona de contacto"),
    )
    phone = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("teléfono"),
    )
    address = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("dirección de entrega"),
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_("notas"),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("activo"),
    )

    class Meta(ERPBaseModel.Meta):
        verbose_name = _("departamento")
        verbose_name_plural = _("departamentos")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_dept_name_per_customer",
            )
        ]

    def __str__(self):
        return f"{self.customer.name} — {self.name}"

    def clean(self):
        super().clean()
        if (
            self.customer_id
            and self.organization_id
            and self.customer.organization_id != self.organization_id
        ):
            raise ValidationError(
                {"customer": _("El cliente no pertenece a esta organizacion.")}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


# ── NCF Sequence ──────────────────────────────────────────────────────────────


class NCFSequence(models.Model):
    """
    Manages the authorized NCF sequences issued by the DGII per organization
    and per NCF type. Only one sequence may be active per (org, ncf_type) pair.

    Supports two series:
      - B (physical / traditional): format  B{type:02d}{seq:08d}  e.g. B0100000001
      - E (electronic / e-CF):      format  E{type:02d}{seq:010d} e.g. E310000000001

    Call NCFSequence.generate(org, ncf_type) inside an atomic block to get the
    next NCF string.
    """

    # Physical NCF type codes (B-series, 01-16)
    PHYSICAL_TYPES = {1, 2, 3, 4, 11, 12, 13, 14, 15, 16}
    # Electronic NCF type codes (E-series, 31-47)
    ELECTRONIC_TYPES = {31, 32, 33, 34, 41, 43, 44, 45, 46, 47}

    class Series(models.TextChoices):
        PHYSICAL = "B", _("B – Físico (comprobante tradicional)")
        ELECTRONIC = "E", _("E – Electrónico (e-CF)")

    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="ncf_sequences",
        verbose_name=_("organización"),
    )
    ncf_type = models.IntegerField(
        choices=NCFType.choices,
        verbose_name=_("tipo de comprobante"),
    )
    series = models.CharField(
        max_length=1,
        choices=Series.choices,
        default=Series.PHYSICAL,
        verbose_name=_("serie"),
    )
    current_seq = models.PositiveIntegerField(
        default=0, verbose_name=_("secuencia actual")
    )
    max_seq = models.BigIntegerField(
        default=99999999, verbose_name=_("secuencia máxima")
    )
    is_active = models.BooleanField(default=True, verbose_name=_("activa"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("secuencia NCF")
        verbose_name_plural = _("secuencias NCF")
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "ncf_type"],
                condition=models.Q(is_active=True),
                name="unique_active_ncf_sequence_per_org_type",
            )
        ]

    def _seq_width(self) -> int:
        return 8 if self.series == self.Series.PHYSICAL else 10

    def __str__(self):
        w = self._seq_width()
        return f"{self.organization} · {self.get_ncf_type_display()} · {self.series}{self.ncf_type:02d}{self.current_seq:0{w}d}"

    def clean(self):
        super().clean()
        if (
            self.series == self.Series.PHYSICAL
            and self.ncf_type not in self.PHYSICAL_TYPES
        ):
            raise ValidationError(
                {"ncf_type": _("El tipo de NCF no corresponde a la serie B.")}
            )
        if (
            self.series == self.Series.ELECTRONIC
            and self.ncf_type not in self.ELECTRONIC_TYPES
        ):
            raise ValidationError(
                {"ncf_type": _("El tipo de NCF no corresponde a la serie E.")}
            )
        if self.current_seq > self.max_seq:
            raise ValidationError(
                {"current_seq": _("La secuencia actual no puede exceder la maxima.")}
            )
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).only("current_seq").first()
            if original and self.current_seq < original.current_seq:
                raise ValidationError(
                    {
                        "current_seq": _(
                            "La secuencia actual no puede reducirse despues de asignar NCF."
                        )
                    }
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        issued = (
            SalesDocument.all_objects.filter(
                organization=self.organization,
                doc_type=SalesDocument.DocType.INVOICE,
                ncf_type=self.ncf_type,
            )
            .exclude(encf="")
            .exists()
        )
        if issued:
            raise ValidationError(
                _(
                    "No se puede eliminar una secuencia que ya emitio comprobantes; desactivela."
                )
            )
        return super().delete(*args, **kwargs)

    @property
    def preview_next(self) -> str:
        """Display the NCF number that will be assigned next, without incrementing."""
        next_num = self.current_seq + 1
        if next_num > self.max_seq:
            return "—"
        w = self._seq_width()
        return f"{self.series}{self.ncf_type:02d}{next_num:0{w}d}"

    @property
    def remaining(self) -> int:
        return max(0, self.max_seq - self.current_seq)

    @property
    def pct_used(self) -> float:
        """Percentage of sequence already consumed (0–100), for progress bars."""
        if self.max_seq == 0:
            return 0.0
        return min(100.0, round(self.current_seq / self.max_seq * 100, 2))

    @classmethod
    def generate(cls, organization, ncf_type: int) -> str:
        """
        Atomically reserve and return the next NCF string for the given
        organization and NCF type.

        B-series: B{type:02d}{seq:08d}   e.g. B0100000001
        E-series: E{type:02d}{seq:010d}  e.g. E310000000001

        Uses SELECT FOR UPDATE to prevent race conditions.
        Raises ValueError if no active sequence exists or the sequence is exhausted.
        """
        with transaction.atomic():
            try:
                seq = cls.objects.select_for_update().get(
                    organization=organization, ncf_type=ncf_type, is_active=True
                )
            except cls.DoesNotExist:
                raise ValueError(
                    f"No hay una secuencia NCF activa para el tipo {ncf_type} "
                    f"en la organización '{organization}'."
                )

            next_num = seq.current_seq + 1
            if next_num > seq.max_seq:
                raise ValueError(
                    f"La secuencia NCF tipo {ncf_type} de '{organization}' "
                    f"está agotada (máximo: {seq.max_seq:,}). "
                    f"Solicite una nueva secuencia a la DGII."
                )

            seq.current_seq = next_num
            seq.save(update_fields=["current_seq", "updated_at"])

        w = 8 if seq.series == cls.Series.PHYSICAL else 10
        return f"{seq.series}{seq.ncf_type:02d}{next_num:0{w}d}"


# ── Document Sequence (for Quotations and Sale Orders) ────────────────────────


class DocumentSequence(models.Model):
    """
    Auto-increment sequence for non-fiscal documents (Quotations, Sale Orders).
    One row per (organization, doc_type) pair.

    Produces:
      COT-2025-0001  for QUOTATION
      OV-2025-0001   for SALE_ORDER
    """

    class DocType(models.TextChoices):
        QUOTATION = "QUOTATION", _("Cotización")
        SALE_ORDER = "SALE_ORDER", _("Orden de Venta")

    PREFIX = {
        "QUOTATION": "COT",
        "SALE_ORDER": "OV",
    }

    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="document_sequences",
        verbose_name=_("organización"),
    )
    doc_type = models.CharField(
        max_length=20,
        choices=DocType.choices,
        verbose_name=_("tipo de documento"),
    )
    current_seq = models.PositiveIntegerField(
        default=0,
        verbose_name=_("secuencia actual"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("secuencia de documento")
        verbose_name_plural = _("secuencias de documentos")
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "doc_type"],
                name="unique_doc_sequence_per_org_type",
            )
        ]

    def __str__(self):
        return f"{self.organization} · {self.get_doc_type_display()} · {self.current_seq:04d}"

    @classmethod
    def generate(cls, organization, doc_type: str) -> str:
        """
        Atomically reserve and return the next document number.
        Format: PREFIX-YYYY-NNNN  (e.g. COT-2025-0001, OV-2025-0001)
        """
        year = timezone.now().year
        with transaction.atomic():
            seq, _ = cls.objects.select_for_update().get_or_create(
                organization=organization,
                doc_type=doc_type,
            )
            seq.current_seq += 1
            seq.save(update_fields=["current_seq", "updated_at"])

        prefix = cls.PREFIX.get(doc_type, doc_type[:3].upper())
        return f"{prefix}-{year}-{seq.current_seq:04d}"


# ── Custom managers ───────────────────────────────────────────────────────────


class SalesDocumentQuerySet(SoftDeleteQuerySet):
    def with_signed_totals(self):
        output_field = DecimalField(max_digits=14, decimal_places=2)
        return self.annotate(
            signed_subtotal=Case(
                When(ncf_type__in=SalesDocument.CREDIT_NOTE_TYPES, then=-F("subtotal")),
                default=F("subtotal"),
                output_field=output_field,
            ),
            signed_itbis_18=Case(
                When(ncf_type__in=SalesDocument.CREDIT_NOTE_TYPES, then=-F("itbis_18")),
                default=F("itbis_18"),
                output_field=output_field,
            ),
            signed_itbis_16=Case(
                When(ncf_type__in=SalesDocument.CREDIT_NOTE_TYPES, then=-F("itbis_16")),
                default=F("itbis_16"),
                output_field=output_field,
            ),
            signed_total=Case(
                When(ncf_type__in=SalesDocument.CREDIT_NOTE_TYPES, then=-F("total")),
                default=F("total"),
                output_field=output_field,
            ),
        )

    def with_aging(self):
        """
        Annotate each row with an `aging_bucket` field (string) based on how
        many days have elapsed since due_date.  Uses Python-computed date
        literals so it works on SQLite, PostgreSQL, and MySQL alike.

        Buckets:
            current  — not yet due or no due_date
            1_30     — 1–30 days past due
            31_60    — 31–60 days past due
            61_90    — 61–90 days past due
            90_plus  — more than 90 days past due
        """
        from django.db.models import Case, When, Value, CharField

        today = date.today()
        # NOTE: named aging_bucket_db to avoid shadowing the @property on Invoice
        return self.annotate(
            aging_bucket_db=Case(
                When(due_date__isnull=True, then=Value("current")),
                When(due_date__gte=today, then=Value("current")),
                When(due_date__gte=today - timedelta(days=30), then=Value("1_30")),
                When(due_date__gte=today - timedelta(days=60), then=Value("31_60")),
                When(due_date__gte=today - timedelta(days=90), then=Value("61_90")),
                default=Value("90_plus"),
                output_field=CharField(max_length=10),
            )
        )


class SalesDocumentManager(models.Manager):
    def get_queryset(self):
        return SalesDocumentQuerySet(self.model, using=self._db).alive()

    def for_org(self, organization):
        return self.get_queryset().for_org(organization)


class DocTypeManager(SalesDocumentManager):
    def __init__(self, doc_type):
        super().__init__()
        self._doc_type = doc_type

    def get_queryset(self):
        return super().get_queryset().filter(doc_type=self._doc_type)


# ── Invoice (unified document model) ─────────────────────────────────────────


class SalesDocument(ERPBaseModel):
    CREDIT_NOTE_TYPES = (NCFType.B04_NOTA_CREDITO, NCFType.NOTA_CREDITO)
    DEBIT_NOTE_TYPES = (NCFType.B03_NOTA_DEBITO, NCFType.NOTA_DEBITO)
    NOTE_TYPES = CREDIT_NOTE_TYPES + DEBIT_NOTE_TYPES

    class DocType(models.TextChoices):
        INVOICE = "INVOICE", _("Factura")
        QUOTATION = "QUOTATION", _("Cotización")
        SALE_ORDER = "SALE_ORDER", _("Orden de Venta")

    class Status(models.TextChoices):
        # ── Shared ───────────────────────────────────────────────
        DRAFT = "DRAFT", _("Borrador")
        CONFIRMED = "CONFIRMED", _("Confirmada")
        CANCELLED = "CANCELLED", _("Anulada")
        # ── Invoice ──────────────────────────────────────────────
        SENT = "SENT", _("Enviada")
        PAID = "PAID", _("Pagada")
        OVERDUE = "OVERDUE", _("Vencida")
        # ── Quotation ────────────────────────────────────────────
        ACCEPTED = "ACCEPTED", _("Aceptada")
        REJECTED = "REJECTED", _("Rechazada")
        EXPIRED = "EXPIRED", _("Expirada")
        CONVERTED = "CONVERTED", _("Convertida")
        # ── Sale Order ───────────────────────────────────────────
        DELIVERED = "DELIVERED", _("Entregada")
        INVOICED = "INVOICED", _("Facturada")

    class PaymentCondition(models.TextChoices):
        CASH = "CASH", _("Contado")
        CREDIT = "CREDIT", _("Crédito")
        FREE = "FREE", _("Gratuito")
        OTHER = "OTHER", _("Otro")

    class AgingBucket(models.TextChoices):
        CURRENT = "current", _("Corriente")
        DAYS_1_30 = "1_30", _("1–30 días")
        DAYS_31_60 = "31_60", _("31–60 días")
        DAYS_61_90 = "61_90", _("61–90 días")
        DAYS_90_PLUS = "90_plus", _("Más de 90 días")

    class Currency(models.TextChoices):
        DOP = "DOP", _("Peso Dominicano (DOP)")
        USD = "USD", _("Dólar Americano (USD)")
        EUR = "EUR", _("Euro (EUR)")

    class DGIIStatus(models.TextChoices):
        PENDING = "PENDING", _("Pendiente")
        ACCEPTED = "ACCEPTED", _("Aceptada")
        REJECTED = "REJECTED", _("Rechazada")

    # ── Document type discriminator ───────────────────────────────────────────
    doc_type = models.CharField(
        max_length=20,
        choices=DocType.choices,
        default=DocType.INVOICE,
        verbose_name=_("tipo de documento"),
        db_index=True,
    )

    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="invoices",
        verbose_name=_("organización"),
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="invoices",
        verbose_name=_("cliente"),
    )

    # ── NCF (INVOICE only) ────────────────────────────────────────────────────
    encf = models.CharField(
        max_length=13,
        blank=True,
        verbose_name=_("NCF"),
        help_text=_(
            "Número de Comprobante Fiscal asignado al confirmar la factura. "
            "Se genera automáticamente desde la secuencia activa."
        ),
    )
    ncf_type = models.IntegerField(
        choices=NCFType.choices,
        default=NCFType.B01_CREDITO_FISCAL,
        verbose_name=_("tipo de comprobante"),
    )
    encf_modified = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="credit_debit_notes",
        verbose_name=_("NCF afectado"),
        help_text=_("Obligatorio para Notas de Crédito (34) y Débito (33)."),
    )

    # ── Non-fiscal document number (QUOTATION / SALE_ORDER) ───────────────────
    doc_number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_("número de documento"),
        help_text=_(
            "Asignado automáticamente al confirmar (COT-YYYY-NNNN / OV-YYYY-NNNN)."
        ),
        db_index=True,
    )

    # ── Dates & conditions ────────────────────────────────────────────────────
    issue_date = models.DateField(
        default=timezone.now, verbose_name=_("fecha de emisión")
    )
    due_date = models.DateField(
        null=True, blank=True, verbose_name=_("fecha de vencimiento")
    )
    payment_condition = models.CharField(
        max_length=10,
        choices=PaymentCondition.choices,
        default=PaymentCondition.CASH,
        verbose_name=_("condición de pago"),
    )

    # ── Quotation-specific ────────────────────────────────────────────────────
    valid_until = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("válida hasta"),
        help_text=_("Fecha de vencimiento de la cotización."),
    )

    # ── Sale Order-specific ───────────────────────────────────────────────────
    department = models.ForeignKey(
        "CustomerDepartment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sale_orders",
        verbose_name=_("departamento de entrega"),
        help_text=_(
            "Departamento o sucursal del cliente al que se entrega esta orden."
        ),
    )
    delivery_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("fecha de entrega"),
    )
    signed_by = models.CharField(
        max_length=150,
        blank=True,
        verbose_name=_("recibido por"),
        help_text=_("Nombre de la persona que recibió y firmó la entrega."),
    )
    consolidated_into = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consolidated_orders",
        verbose_name=_("consolidada en"),
        help_text=_("Factura que consolidó esta orden de venta."),
    )

    # ── Currency ──────────────────────────────────────────────────────────────
    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.DOP,
        verbose_name=_("moneda"),
    )
    exchange_rate = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=Decimal("1.0000"),
        verbose_name=_("tasa de cambio"),
        help_text=_("Tasa BCR si la moneda no es DOP."),
    )

    # ── Totals (computed, stored for query performance) ───────────────────────
    subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("subtotal (sin ITBIS)"),
    )
    itbis_18 = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("ITBIS 18%"),
    )
    itbis_16 = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("ITBIS 16%"),
    )
    total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("total"),
    )

    # ── Status ────────────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name=_("estado"),
        db_index=True,
    )

    # ── Notes ─────────────────────────────────────────────────────────────────
    notes = models.TextField(blank=True, verbose_name=_("notas internas"))
    terms = models.TextField(blank=True, verbose_name=_("términos y condiciones"))

    # ── DGII e-CF submission (Phase 2) ────────────────────────────────────────
    xml_content = models.TextField(blank=True, verbose_name=_("XML e-CF"))
    dgii_status = models.CharField(
        max_length=10,
        choices=DGIIStatus.choices,
        default=DGIIStatus.PENDING,
        verbose_name=_("estado DGII"),
    )
    dgii_track_id = models.CharField(
        max_length=100, blank=True, verbose_name=_("track ID DGII")
    )

    # ── Managers ──────────────────────────────────────────────────────────────
    objects = SalesDocumentManager()
    all_objects = models.Manager()
    invoices = DocTypeManager("INVOICE")
    quotations = DocTypeManager("QUOTATION")
    sale_orders = DocTypeManager("SALE_ORDER")

    class Meta(ERPBaseModel.Meta):
        ordering = ["-created_at"]
        verbose_name = _("documento")
        verbose_name_plural = _("documentos")
        indexes = [
            models.Index(
                fields=["organization", "doc_type", "status"],
                name="invoice_org_doctype_status_idx",
            ),
            models.Index(
                fields=["organization", "customer", "status"],
                name="inv_org_customer_status_idx",
            ),
            models.Index(
                fields=["organization", "due_date", "status"],
                name="invoice_org_duedate_status_idx",
            ),
            GinIndex(
                fields=["encf"],
                opclasses=["gin_trgm_ops"],
                name="invoice_encf_trgm_idx",
            ),
            GinIndex(
                fields=["doc_number"],
                opclasses=["gin_trgm_ops"],
                name="invoice_doc_number_trgm_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "encf"],
                condition=models.Q(deleted_at__isnull=True) & ~models.Q(encf=""),
                name="unique_encf_per_org",
            ),
            models.UniqueConstraint(
                fields=["organization", "doc_number"],
                condition=models.Q(deleted_at__isnull=True) & ~models.Q(doc_number=""),
                name="unique_doc_number_per_org",
            ),
        ]

    def __str__(self):
        if self.doc_type == self.DocType.INVOICE:
            return self.encf or f"BORRADOR-{str(self.pk)[:8]}"
        return self.doc_number or f"{self.get_doc_type_display()}-{str(self.pk)[:8]}"

    @property
    def is_editable(self):
        return self.status == self.Status.DRAFT

    @property
    def is_invoice(self):
        return self.doc_type == self.DocType.INVOICE

    @property
    def is_quotation(self):
        return self.doc_type == self.DocType.QUOTATION

    @property
    def is_sale_order(self):
        return self.doc_type == self.DocType.SALE_ORDER

    @property
    def days_overdue(self) -> int:
        """
        How many calendar days past due_date this invoice is.
        Returns 0 when not yet due, already paid/cancelled, or has no due_date.
        """
        terminal = (self.Status.DRAFT, self.Status.CANCELLED, self.Status.PAID)
        if self.status in terminal or not self.due_date:
            return 0
        delta = (date.today() - self.due_date).days
        return max(0, delta)

    @property
    def aging_bucket(self) -> str:
        """Return the AgingBucket value for this invoice."""
        d = self.days_overdue
        if d == 0:
            return self.AgingBucket.CURRENT
        elif d <= 30:
            return self.AgingBucket.DAYS_1_30
        elif d <= 60:
            return self.AgingBucket.DAYS_31_60
        elif d <= 90:
            return self.AgingBucket.DAYS_61_90
        return self.AgingBucket.DAYS_90_PLUS

    @property
    def aging_bucket_label(self) -> str:
        return self.AgingBucket(self.aging_bucket).label

    @property
    def display_number(self):
        """Human-readable document reference regardless of type."""
        if self.doc_type == self.DocType.INVOICE:
            return self.encf or f"BORRADOR-{str(self.pk)[:8]}"
        return self.doc_number or f"{self.get_doc_type_display()}-{str(self.pk)[:8]}"

    @property
    def itbis_total(self):
        return self.itbis_18 + self.itbis_16

    @property
    def is_credit_note(self):
        return self.ncf_type in self.CREDIT_NOTE_TYPES

    def signed_value(self, value):
        return -value if self.is_credit_note else value

    def recompute_totals(self):
        """Recompute subtotal, itbis_18, itbis_16 and total from line items."""
        items = self.items.all()
        subtotal = sum(i.line_total for i in items)
        itbis_18 = sum(
            i.itbis_amount
            for i in items
            if i.itbis_rate == SalesDocumentItem.ITBISRate.RATE_18
        )
        itbis_16 = sum(
            i.itbis_amount
            for i in items
            if i.itbis_rate == SalesDocumentItem.ITBISRate.RATE_16
        )
        self.subtotal = subtotal
        self.itbis_18 = itbis_18
        self.itbis_16 = itbis_16
        self.total = subtotal + itbis_18 + itbis_16
        self.save(
            update_fields=["subtotal", "itbis_18", "itbis_16", "total", "updated_at"]
        )

    def clean(self):
        super().clean()
        if (
            self.customer_id
            and self.organization_id
            and self.customer.organization_id != self.organization_id
        ):
            raise ValidationError(
                {"customer": _("El cliente no pertenece a esta organizacion.")}
            )
        if self.department_id:
            if self.doc_type != self.DocType.SALE_ORDER:
                raise ValidationError(
                    {
                        "department": _(
                            "Solo una orden de venta puede tener departamento."
                        )
                    }
                )
            if (
                self.department.organization_id != self.organization_id
                or self.department.customer_id != self.customer_id
            ):
                raise ValidationError(
                    {
                        "department": _(
                            "El departamento no pertenece al cliente y organizacion del documento."
                        )
                    }
                )
        if self.consolidated_into_id:
            if self.doc_type != self.DocType.SALE_ORDER:
                raise ValidationError(
                    {
                        "consolidated_into": _(
                            "Solo una orden de venta puede consolidarse."
                        )
                    }
                )
            if (
                self.consolidated_into.organization_id != self.organization_id
                or self.consolidated_into.doc_type != self.DocType.INVOICE
            ):
                raise ValidationError(
                    {
                        "consolidated_into": _(
                            "La factura consolidada no pertenece a esta organizacion."
                        )
                    }
                )

        # NCF rules only apply to invoices
        if self.doc_type != self.DocType.INVOICE:
            if self.encf_modified_id:
                raise ValidationError(
                    {
                        "encf_modified": _(
                            "Solo una factura fiscal puede afectar un NCF."
                        )
                    }
                )
            return

        _credito_fiscal_types = (NCFType.B01_CREDITO_FISCAL, NCFType.CREDITO_FISCAL)

        # Nota de Crédito / Débito must reference another invoice
        if self.ncf_type in self.NOTE_TYPES:
            if not self.encf_modified_id:
                raise ValidationError(
                    _(
                        "Las Notas de Crédito y Débito deben referenciar el NCF afectado."
                    )
                )
            if (
                self.encf_modified_id == self.pk
                or self.encf_modified.organization_id != self.organization_id
                or self.encf_modified.doc_type != self.DocType.INVOICE
                or self.encf_modified.ncf_type in self.NOTE_TYPES
                or not self.encf_modified.encf
                or self.encf_modified.status
                not in (
                    self.Status.CONFIRMED,
                    self.Status.SENT,
                    self.Status.PAID,
                    self.Status.OVERDUE,
                )
            ):
                raise ValidationError(
                    {
                        "encf_modified": _(
                            "El NCF afectado debe ser una factura emitida de esta organizacion."
                        )
                    }
                )
        elif self.encf_modified_id:
            raise ValidationError(
                {
                    "encf_modified": _(
                        "Solo una nota de credito o debito puede afectar otro NCF."
                    )
                }
            )
        # Crédito Fiscal requires buyer RNC
        if self.ncf_type in _credito_fiscal_types:
            if self.customer_id and not self.customer.rnc_cedula:
                raise ValidationError(
                    _("La Factura de Crédito Fiscal requiere el RNC del comprador.")
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


# ── SalesDocumentItem ─────────────────────────────────────────────────────────


class SalesDocumentItem(AbstractDocumentLineItem):
    document = models.ForeignKey(
        SalesDocument,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("documento"),
    )
    # Optional reference to the items catalog.
    # Referenced entries are deactivated rather than deleted.
    item = models.ForeignKey(
        "items.Item",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="line_items",
        verbose_name=_("artículo"),
    )

    class Meta:
        verbose_name = _("línea de documento")
        verbose_name_plural = _("líneas de documento")
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="sales_line_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="sales_line_unit_price_nonnegative",
            ),
        ]

    def clean(self):
        super().clean()
        if (
            self.item_id
            and self.document_id
            and self.item.organization_id != self.document.organization_id
        ):
            raise ValidationError(
                {"item": _("El articulo no pertenece a esta organizacion.")}
            )


# ── Payment ───────────────────────────────────────────────────────────────────


class Payment(ERPBaseModel):
    """
    A single payment receipt from a customer.  One payment can cover one or
    more invoices; the split is recorded in PaymentAllocation.

    Accepted methods: bank transfer or cheque only.
    """

    Method = PaymentMethod

    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name=_("organización"),
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name=_("cliente"),
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name=_("monto total recibido"),
    )
    date = models.DateField(default=timezone.now, verbose_name=_("fecha de pago"))
    method = models.CharField(
        max_length=10,
        choices=Method.choices,
        default=Method.TRANSFER,
        verbose_name=_("forma de pago"),
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("referencia"),
    )
    notes = models.TextField(blank=True, verbose_name=_("notas"))

    class Meta(ERPBaseModel.Meta):
        verbose_name = _("pago")
        verbose_name_plural = _("pagos")
        ordering = ["-date", "-created_at"]
        indexes = [
            GinIndex(
                fields=["reference"],
                opclasses=["gin_trgm_ops"],
                name="payment_reference_trgm_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="payment_amount_positive",
            ),
        ]

    def __str__(self):
        return f"Pago {self.amount} – {self.customer} ({self.date})"

    @property
    def allocated_total(self) -> Decimal:
        """Sum of all allocations. Should equal self.amount when fully applied."""
        from django.db.models import Sum

        result = self.allocations.aggregate(t=Sum("amount"))["t"]
        return result or Decimal("0.00")

    @property
    def unallocated(self) -> Decimal:
        return self.amount - self.allocated_total

    def delete(self, *args, **kwargs):
        raise ValueError(
            "Use PaymentService.delete() para eliminar pagos y revertir sus efectos."
        )

    def clean(self):
        super().clean()
        if (
            self.customer_id
            and self.organization_id
            and self.customer.organization_id != self.organization_id
        ):
            raise ValidationError(
                {"customer": _("El cliente no pertenece a esta organizacion.")}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


# ── PaymentAllocation ─────────────────────────────────────────────────────────


class PaymentAllocation(models.Model):
    """
    Records how much of a Payment is applied to a specific Invoice.

    Invariant: sum(allocations.amount) for a payment == payment.amount
    Invariant: allocation.amount <= invoice.outstanding_balance at time of creation
    """

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="allocations",
        verbose_name=_("pago"),
    )
    invoice = models.ForeignKey(
        SalesDocument,
        on_delete=models.PROTECT,
        related_name="allocations",
        verbose_name=_("factura"),
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name=_("monto aplicado"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("aplicación de pago")
        verbose_name_plural = _("aplicaciones de pago")
        constraints = [
            models.UniqueConstraint(
                fields=["payment", "invoice"],
                name="unique_payment_invoice_allocation",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="allocation_amount_positive",
            ),
        ]

    def __str__(self):
        return f"{self.payment} → {self.invoice}: {self.amount}"

    def clean(self):
        super().clean()
        if self.payment_id and self.invoice_id:
            if self.payment.organization_id != self.invoice.organization_id:
                raise ValidationError(
                    _("El pago y la factura deben pertenecer a la misma organizacion.")
                )
            if self.payment.customer_id != self.invoice.customer_id:
                raise ValidationError(
                    _("El pago y la factura deben pertenecer al mismo cliente.")
                )
            if self.invoice.doc_type != SalesDocument.DocType.INVOICE:
                raise ValidationError(_("Los pagos solo pueden aplicarse a facturas."))

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
