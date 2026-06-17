import re
from decimal import Decimal

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import AbstractDocumentLineItem, ERPBaseModel, SoftDeleteManager, SoftDeleteQuerySet


# ── Supplier ──────────────────────────────────────────────────────────────────


class Supplier(ERPBaseModel):
    class IdType(models.TextChoices):
        RNC = "RNC", _("RNC")
        CEDULA = "CED", _("Cédula")

    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="suppliers",
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
        blank=True,
        verbose_name=_("RNC / Cédula"),
        help_text=_("RNC: 9 dígitos. Cédula: 11 dígitos."),
    )
    email = models.EmailField(blank=True, verbose_name=_("correo electrónico"))
    phone = models.CharField(max_length=20, blank=True, verbose_name=_("teléfono"))
    contact_name = models.CharField(max_length=150, blank=True, verbose_name=_("nombre de contacto"))
    address = models.CharField(max_length=255, blank=True, verbose_name=_("dirección"))
    city = models.CharField(max_length=100, blank=True, verbose_name=_("ciudad"))
    notes = models.TextField(blank=True, verbose_name=_("notas"))
    credit_limit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("límite de crédito"),
    )
    payment_term = models.ForeignKey(
        "sales.PaymentTerm",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="suppliers",
        verbose_name=_("término de pago"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("activo"))

    class Meta(ERPBaseModel.Meta):
        ordering = ["-created_at"]
        verbose_name = _("proveedor")
        verbose_name_plural = _("proveedores")
        indexes = [
            GinIndex(SearchVector("name", config="spanish"), name="supplier_name_fts_idx"),
            GinIndex(fields=["name"], opclasses=["gin_trgm_ops"], name="supplier_name_trgm_idx"),
            GinIndex(fields=["rnc_cedula"], opclasses=["gin_trgm_ops"], name="supplier_rnc_cedula_trgm_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "rnc_cedula"],
                condition=models.Q(deleted_at__isnull=True) & ~models.Q(rnc_cedula=""),
                name="unique_active_supplier_rnc_cedula_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(id_type__in=["RNC", "CED"]),
                name="supplier_id_type_rnc_or_cedula",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.id_type not in (self.IdType.RNC, self.IdType.CEDULA):
            raise ValidationError(
                {"id_type": _("El tipo de identificación debe ser RNC o Cédula.")}
            )
        if not self.rnc_cedula:
            return

        normalized = re.sub(r"[\s\-]", "", self.rnc_cedula.strip())

        if self.id_type == self.IdType.RNC:
            if not re.fullmatch(r"\d{9}", normalized):
                raise ValidationError({
                    "rnc_cedula": _("El RNC debe tener exactamente 9 dígitos numéricos.")
                })
            self.rnc_cedula = normalized
        elif self.id_type == self.IdType.CEDULA:
            if not re.fullmatch(r"\d{11}", normalized):
                raise ValidationError({
                    "rnc_cedula": _("La Cédula debe tener exactamente 11 dígitos numéricos.")
                })
            self.rnc_cedula = normalized

    def delete(self, *args, **kwargs):
        has_documents = PurchaseDocument.objects.filter(supplier=self).exists()
        has_payments = SupplierPayment.objects.filter(supplier=self).exists()
        if has_documents or has_payments:
            raise ValueError(
                f"No se puede eliminar «{self.name}» porque tiene documentos o pagos asociados."
            )
        return super().delete(*args, **kwargs)


# ── PurchaseDocument ──────────────────────────────────────────────────────────


class PurchaseDocumentQuerySet(SoftDeleteQuerySet):
    pass


class PurchaseDocumentManager(SoftDeleteManager):
    def get_queryset(self):
        return PurchaseDocumentQuerySet(self.model, using=self._db).alive()

    def for_org(self, organization):
        return self.get_queryset().for_org(organization)


class DocTypeManager(PurchaseDocumentManager):
    def __init__(self, doc_type):
        super().__init__()
        self._doc_type = doc_type

    def get_queryset(self):
        return super().get_queryset().filter(doc_type=self._doc_type)


class PurchaseDocument(ERPBaseModel):
    class DocType(models.TextChoices):
        PURCHASE_ORDER = "PURCHASE_ORDER", _("Orden de Compra")
        SUPPLIER_INVOICE = "SUPPLIER_INVOICE", _("Factura de Proveedor")

    class Status(models.TextChoices):
        DRAFT = "DRAFT", _("Borrador")
        CONFIRMED = "CONFIRMED", _("Confirmada")
        RECEIVED = "RECEIVED", _("Recibida")
        CANCELLED = "CANCELLED", _("Anulada")
        PAID = "PAID", _("Pagada")

    class Currency(models.TextChoices):
        DOP = "DOP", _("Peso Dominicano (DOP)")
        USD = "USD", _("Dólar Americano (USD)")
        EUR = "EUR", _("Euro (EUR)")

    doc_type = models.CharField(
        max_length=20,
        choices=DocType.choices,
        default=DocType.PURCHASE_ORDER,
        verbose_name=_("tipo de documento"),
        db_index=True,
    )
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="purchase_documents",
        verbose_name=_("organización"),
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="purchase_documents",
        verbose_name=_("proveedor"),
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name=_("estado"),
        db_index=True,
    )
    number = models.CharField(
        max_length=30,
        blank=True,
        verbose_name=_("número de documento"),
        db_index=True,
    )
    issue_date = models.DateField(
        default=timezone.now,
        verbose_name=_("fecha de emisión"),
    )
    expected_date = models.DateField(
        null=True, blank=True,
        verbose_name=_("fecha estimada de entrega"),
    )
    due_date = models.DateField(
        null=True, blank=True,
        verbose_name=_("fecha de vencimiento"),
    )
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
    )
    notes = models.TextField(blank=True, verbose_name=_("notas"))

    # Computed totals
    subtotal = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00"),
        verbose_name=_("subtotal (sin ITBIS)"),
    )
    itbis_18 = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00"),
        verbose_name=_("ITBIS 18%"),
    )
    itbis_16 = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00"),
        verbose_name=_("ITBIS 16%"),
    )
    total = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00"),
        verbose_name=_("total"),
    )

    # DGII 606 fields (supplier invoice only)
    supplier_ncf = models.CharField(
        max_length=13, blank=True,
        verbose_name=_("NCF del proveedor"),
    )
    supplier_ncf_type = models.CharField(
        max_length=10, blank=True,
        verbose_name=_("tipo NCF del proveedor"),
    )
    supplier_rnc = models.CharField(
        max_length=20, blank=True,
        verbose_name=_("RNC del proveedor"),
    )

    # Link to PO that generated this SI
    linked_purchase_order = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_invoices_from_po",
        verbose_name=_("orden de compra origen"),
    )

    # Managers
    objects = PurchaseDocumentManager()
    all_objects = models.Manager()
    purchase_orders = DocTypeManager("PURCHASE_ORDER")
    supplier_invoices = DocTypeManager("SUPPLIER_INVOICE")

    class Meta(ERPBaseModel.Meta):
        ordering = ["-created_at"]
        verbose_name = _("documento de compra")
        verbose_name_plural = _("documentos de compra")
        indexes = [
            models.Index(
                fields=["organization", "doc_type", "status"],
                name="pur_org_doctype_status_idx",
            ),
            models.Index(
                fields=["organization", "supplier"],
                name="pur_org_supplier_idx",
            ),
            models.Index(
                fields=["organization", "doc_type", "status", "issue_date"],
                name="pur_org_dt_status_date_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "supplier_ncf"],
                condition=(
                    models.Q(deleted_at__isnull=True)
                    & ~models.Q(supplier_ncf="")
                    & ~models.Q(status="DRAFT")
                ),
                name="unique_supplier_ncf_per_org",
            ),
        ]

    def __str__(self):
        if self.number:
            return self.number
        return f"{self.get_doc_type_display()}-{str(self.pk)[:8]}"

    @property
    def is_editable(self):
        return self.status == self.Status.DRAFT

    @property
    def display_number(self):
        return self.number or f"{self.get_doc_type_display()}-{str(self.pk)[:8]}"

    @property
    def itbis_total(self):
        return self.itbis_18 + self.itbis_16

    def recompute_totals(self):
        _zero = Decimal("0.00")
        agg = self.items.aggregate(
            subtotal=Sum("line_total"),
            itbis_18=Sum(
                "itbis_amount",
                filter=Q(itbis_rate=PurchaseDocumentItem.ITBISRate.RATE_18),
            ),
            itbis_16=Sum(
                "itbis_amount",
                filter=Q(itbis_rate=PurchaseDocumentItem.ITBISRate.RATE_16),
            ),
        )
        subtotal = agg["subtotal"] or _zero
        itbis_18 = agg["itbis_18"] or _zero
        itbis_16 = agg["itbis_16"] or _zero
        self.subtotal = subtotal
        self.itbis_18 = itbis_18
        self.itbis_16 = itbis_16
        self.total = subtotal + itbis_18 + itbis_16
        self.save(update_fields=["subtotal", "itbis_18", "itbis_16", "total", "updated_at"])

    def clean(self):
        super().clean()
        if (
            self.supplier_id
            and self.organization_id
            and self.supplier.organization_id != self.organization_id
        ):
            raise ValidationError({"supplier": _("El proveedor no pertenece a esta organización.")})

    def save(self, *args, **kwargs):
        # Skip validate_constraints() — NCF uniqueness is enforced by the service and DB constraint.
        self.clean()
        return super().save(*args, **kwargs)


# ── PurchaseDocumentItem ──────────────────────────────────────────────────────


class PurchaseDocumentItem(AbstractDocumentLineItem):
    purchase_document = models.ForeignKey(
        PurchaseDocument,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("documento"),
    )
    item = models.ForeignKey(
        "items.Item",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_line_items",
        verbose_name=_("artículo"),
    )

    class Meta:
        verbose_name = _("línea de compra")
        verbose_name_plural = _("líneas de compra")
        ordering = ["pk"]
        indexes = [
            models.Index(
                fields=["purchase_document", "itbis_rate"],
                name="pur_item_doc_itbis_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="purchase_line_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="purchase_line_unit_price_nonneg",
            ),
        ]

    def clean(self):
        super().clean()
        if (
            self.item_id
            and self.purchase_document_id
            and self.item.organization_id != self.purchase_document.organization_id
        ):
            raise ValidationError({"item": _("El artículo no pertenece a esta organización.")})


# ── SupplierPayment ───────────────────────────────────────────────────────────


class SupplierPayment(ERPBaseModel):
    from apps.sales.models import PaymentMethod
    Method = PaymentMethod

    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="supplier_payments",
        verbose_name=_("organización"),
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name=_("proveedor"),
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name=_("monto total pagado"),
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
        verbose_name = _("pago a proveedor")
        verbose_name_plural = _("pagos a proveedores")
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(
                fields=["organization", "supplier", "date"],
                name="suppay_org_supplier_date_idx",
            ),
            models.Index(
                fields=["organization", "date"],
                name="suppay_org_date_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="supplier_payment_amount_positive",
            ),
        ]

    def __str__(self):
        return f"Pago {self.amount} – {self.supplier} ({self.date})"

    def clean(self):
        super().clean()
        if (
            self.supplier_id
            and self.organization_id
            and self.supplier.organization_id != self.organization_id
        ):
            raise ValidationError({"supplier": _("El proveedor no pertenece a esta organización.")})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError(
            "Use SupplierPaymentService.delete_payment() para eliminar pagos y revertir sus efectos."
        )


# ── SupplierPaymentAllocation ─────────────────────────────────────────────────


class SupplierPaymentAllocation(models.Model):
    payment = models.ForeignKey(
        SupplierPayment,
        on_delete=models.CASCADE,
        related_name="allocations",
        verbose_name=_("pago"),
    )
    supplier_invoice = models.ForeignKey(
        PurchaseDocument,
        on_delete=models.PROTECT,
        related_name="allocations",
        verbose_name=_("factura de proveedor"),
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
                fields=["payment", "supplier_invoice"],
                name="unique_supplier_payment_invoice_alloc",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="supplier_alloc_amount_positive",
            ),
        ]

    def __str__(self):
        return f"{self.payment} → {self.supplier_invoice}: {self.amount}"

    def clean(self):
        super().clean()
        if self.payment_id and self.supplier_invoice_id:
            si = self.supplier_invoice
            if si.doc_type != PurchaseDocument.DocType.SUPPLIER_INVOICE:
                raise ValidationError(_("Solo se puede aplicar a facturas de proveedor."))
            if si.organization_id != self.payment.organization_id:
                raise ValidationError(_("El pago y la factura deben pertenecer a la misma organización."))
            if si.supplier_id != self.payment.supplier_id:
                raise ValidationError(_("El pago y la factura deben pertenecer al mismo proveedor."))
            if si.status not in (PurchaseDocument.Status.CONFIRMED, PurchaseDocument.Status.PAID):
                raise ValidationError(_("La factura no está disponible para aplicar pagos."))

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
