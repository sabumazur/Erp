from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import ERPBaseModel


# ── NCF type choices ──────────────────────────────────────────────────────────


class NCFType(models.IntegerChoices):
    CREDITO_FISCAL = 31, _("31 – Factura de Crédito Fiscal")
    CONSUMO = 32, _("32 – Factura de Consumo")
    NOTA_DEBITO = 33, _("33 – Nota de Débito")
    NOTA_CREDITO = 34, _("34 – Nota de Crédito")
    COMPRAS = 41, _("41 – Comprobante de Compras")
    GASTOS_MENORES = 43, _("43 – Gastos Menores")
    REG_ESPECIALES = 44, _("44 – Regímenes Especiales")
    GUBERNAMENTAL = 45, _("45 – Gubernamental")
    EXPORTACIONES = 46, _("46 – Exportaciones")
    PAGOS_EXTERIOR = 47, _("47 – Pagos al Exterior")


# ── Customer ──────────────────────────────────────────────────────────────────


class Customer(ERPBaseModel):
    class IdType(models.TextChoices):
        RNC = "RNC", _("RNC (Empresa)")
        CEDULA = "CED", _("Cédula (Persona física)")
        PASAPORTE = "PAS", _("Pasaporte")
        EXTERIOR = "EXT", _("Identificación extranjera")

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
    default_ncf_type = models.IntegerField(
        choices=NCFType.choices,
        default=NCFType.CREDITO_FISCAL,
        verbose_name=_("tipo de comprobante por defecto"),
    )

    class Meta(ERPBaseModel.Meta):
        verbose_name = _("cliente")
        verbose_name_plural = _("clientes")
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "rnc_cedula"],
                condition=models.Q(deleted_at__isnull=True) & ~models.Q(rnc_cedula=""),
                name="unique_active_customer_rnc_per_org",
            )
        ]

    def __str__(self):
        return self.name

    def clean(self):
        from .validators import validate_rnc_cedula
        if self.rnc_cedula:
            validate_rnc_cedula(self.rnc_cedula, id_type=self.id_type)


# ── NCF Sequence ──────────────────────────────────────────────────────────────


class NCFSequence(models.Model):
    """
    Manages the authorized e-NCF sequences issued by the DGII per organization
    and per NCF type. Only one sequence may be active per (org, ncf_type) pair.

    Call NCFSequence.generate(org, ncf_type) inside an atomic block to get the
    next sequential e-NCF string (e.g. "E310000000001").
    """

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
        default="E",
        verbose_name=_("serie"),
        help_text=_(
            "'E' para electrónico (e-CF). 'B' para comprobantes físicos legacy."
        ),
    )
    current_seq = models.PositiveIntegerField(
        default=0, verbose_name=_("secuencia actual")
    )
    max_seq = models.PositiveIntegerField(
        default=9999999999, verbose_name=_("secuencia máxima")
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

    def __str__(self):
        return f"{self.organization} · {self.get_ncf_type_display()} · {self.series}{self.ncf_type:02d}{self.current_seq:010d}"

    @classmethod
    def generate(cls, organization, ncf_type: int) -> str:
        """
        Atomically reserve and return the next e-NCF string for the given
        organization and NCF type.

        Uses SELECT FOR UPDATE to prevent race conditions under concurrency.
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
                    f"está agotada (máximo: {seq.max_seq}). "
                    f"Solicite una nueva secuencia a la DGII."
                )

            seq.current_seq = next_num
            seq.save(update_fields=["current_seq", "updated_at"])

        return f"{seq.series}{seq.ncf_type:02d}{next_num:010d}"


# ── Invoice ───────────────────────────────────────────────────────────────────


class Invoice(ERPBaseModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", _("Borrador")
        CONFIRMED = "CONFIRMED", _("Confirmada")
        SENT = "SENT", _("Enviada")
        PAID = "PAID", _("Pagada")
        OVERDUE = "OVERDUE", _("Vencida")
        CANCELLED = "CANCELLED", _("Anulada")

    class PaymentCondition(models.TextChoices):
        CASH = "CASH", _("Contado")
        CREDIT = "CREDIT", _("Crédito")
        FREE = "FREE", _("Gratuito")
        OTHER = "OTHER", _("Otro")

    class Currency(models.TextChoices):
        DOP = "DOP", _("Peso Dominicano (DOP)")
        USD = "USD", _("Dólar Americano (USD)")
        EUR = "EUR", _("Euro (EUR)")

    class DGIIStatus(models.TextChoices):
        PENDING = "PENDING", _("Pendiente")
        ACCEPTED = "ACCEPTED", _("Aceptada")
        REJECTED = "REJECTED", _("Rechazada")

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

    # ── NCF / e-CF ───────────────────────────────────────────────────────────
    encf = models.CharField(
        max_length=13,
        blank=True,
        verbose_name=_("e-NCF"),
        help_text=_(
            "Número de Comprobante Fiscal Electrónico asignado por la DGII. "
            "Se genera automáticamente al confirmar la factura."
        ),
    )
    ncf_type = models.IntegerField(
        choices=NCFType.choices,
        default=NCFType.CREDITO_FISCAL,
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

    class Meta(ERPBaseModel.Meta):
        verbose_name = _("factura")
        verbose_name_plural = _("facturas")
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "encf"],
                condition=models.Q(deleted_at__isnull=True) & ~models.Q(encf=""),
                name="unique_encf_per_org",
            )
        ]

    def __str__(self):
        return self.encf or f"BORRADOR-{str(self.pk)[:8]}"

    @property
    def is_editable(self):
        return self.status == self.Status.DRAFT

    @property
    def itbis_total(self):
        return self.itbis_18 + self.itbis_16

    def recompute_totals(self):
        """Recompute subtotal, itbis_18, itbis_16 and total from line items."""
        items = self.items.all()
        subtotal = sum(i.line_total for i in items)
        itbis_18 = sum(
            i.itbis_amount
            for i in items
            if i.itbis_rate == InvoiceItem.ITBISRate.RATE_18
        )
        itbis_16 = sum(
            i.itbis_amount
            for i in items
            if i.itbis_rate == InvoiceItem.ITBISRate.RATE_16
        )
        self.subtotal = subtotal
        self.itbis_18 = itbis_18
        self.itbis_16 = itbis_16
        self.total = subtotal + itbis_18 + itbis_16
        self.save(
            update_fields=["subtotal", "itbis_18", "itbis_16", "total", "updated_at"]
        )

    def clean(self):
        # Nota de Crédito / Débito must reference another invoice
        if self.ncf_type in (NCFType.NOTA_CREDITO, NCFType.NOTA_DEBITO):
            if not self.encf_modified_id:
                raise ValidationError(
                    _(
                        "Las Notas de Crédito (34) y Débito (33) deben referenciar el NCF afectado."
                    )
                )
        # Crédito Fiscal requires buyer RNC
        if self.ncf_type == NCFType.CREDITO_FISCAL:
            if not self.customer.rnc_cedula:
                raise ValidationError(
                    _(
                        "La Factura de Crédito Fiscal (31) requiere el RNC del comprador."
                    )
                )


# ── InvoiceItem ───────────────────────────────────────────────────────────────


class InvoiceItem(models.Model):
    class ITBISRate(models.TextChoices):
        EXEMPT = "EXEMPT", _("Exento (0%)")
        RATE_0 = "RATE_0", _("Tasa 0% (exportación)")
        RATE_16 = "RATE_16", _("ITBIS 16%")
        RATE_18 = "RATE_18", _("ITBIS 18%")

    RATE_VALUES = {
        ITBISRate.EXEMPT: Decimal("0.00"),
        ITBISRate.RATE_0: Decimal("0.00"),
        ITBISRate.RATE_16: Decimal("0.16"),
        ITBISRate.RATE_18: Decimal("0.18"),
    }

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("factura"),
    )
    description = models.CharField(max_length=500, verbose_name=_("descripción"))
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=Decimal("1.0000"),
        verbose_name=_("cantidad"),
    )
    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name=_("precio unitario (sin ITBIS)"),
    )
    itbis_rate = models.CharField(
        max_length=8,
        choices=ITBISRate.choices,
        default=ITBISRate.RATE_18,
        verbose_name=_("tasa ITBIS"),
    )

    # Computed fields — stored for report generation
    line_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("total línea (sin ITBIS)"),
    )
    itbis_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("monto ITBIS"),
    )
    line_total_with_itbis = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("total línea con ITBIS"),
    )

    class Meta:
        verbose_name = _("línea de factura")
        verbose_name_plural = _("líneas de factura")
        ordering = ["pk"]

    def __str__(self):
        return f"{self.description} × {self.quantity}"

    def compute(self):
        """Recompute line totals from quantity, unit_price and itbis_rate."""
        rate = self.RATE_VALUES.get(self.itbis_rate, Decimal("0.00"))
        self.line_total = (self.quantity * self.unit_price).quantize(Decimal("0.01"))
        self.itbis_amount = (self.line_total * rate).quantize(Decimal("0.01"))
        self.line_total_with_itbis = self.line_total + self.itbis_amount

    def save(self, *args, **kwargs):
        self.compute()
        super().save(*args, **kwargs)


# ── Payment ───────────────────────────────────────────────────────────────────


class Payment(ERPBaseModel):
    class Method(models.TextChoices):
        CASH = "CASH", _("Efectivo")
        CHECK = "CHECK", _("Cheque")
        CARD = "CARD", _("Tarjeta de crédito/débito")
        TRANSFER = "TRANSFER", _("Transferencia bancaria")
        SWAP = "SWAP", _("Permuta")
        OTHER = "OTHER", _("Otro")

    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name=_("organización"),
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name=_("factura"),
    )
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name=_("monto")
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
        help_text=_("Número de cheque, confirmación de transferencia, etc."),
    )
    notes = models.TextField(blank=True, verbose_name=_("notas"))

    class Meta(ERPBaseModel.Meta):
        verbose_name = _("pago")
        verbose_name_plural = _("pagos")

    def __str__(self):
        return f"Pago {self.amount} → {self.invoice}"
