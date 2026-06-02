"""
apps/invoices/validators.py

Dominican Republic fiscal ID length validators.

Supported types:
  - RNC  (Registro Nacional del Contribuyente) — 9 digits, companies
  - Cédula (Cédula de Identidad y Electoral)   — 11 digits, individuals
  - Pasaporte / Exterior                        — length check only

Usage (as Django field validators):
    from apps.sales.validators import validate_rnc_cedula

    rnc_cedula = models.CharField(validators=[validate_rnc_cedula], ...)

Usage (standalone):
    from apps.sales.validators import validate_rnc, validate_cedula
    ok, error = validate_rnc("101012340")
    ok, error = validate_cedula("00113918200")
"""

import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def _digits_only(value: str) -> str:
    return re.sub(r"\D", "", value)


def validate_rnc(value: str) -> tuple[bool, str]:
    digits = _digits_only(value)
    if len(digits) != 9:
        return False, _("El RNC debe tener exactamente 9 dígitos (recibido: %(n)s).") % {"n": len(digits)}
    return True, ""


def validate_cedula(value: str) -> tuple[bool, str]:
    digits = _digits_only(value)
    if len(digits) != 11:
        return False, _("La cédula debe tener exactamente 11 dígitos (recibido: %(n)s).") % {"n": len(digits)}
    return True, ""


# ── Django field validator ────────────────────────────────────────────────────

def validate_rnc_cedula(value: str, id_type: str = None):
    """
    Django-compatible field validator for RNC or Cédula.

    Determines type by digit count if id_type is not supplied:
      9 digits  → RNC
      11 digits → Cédula
      other     → skip digit-only format checks (Pasaporte / Exterior)

    Raises ValidationError on length failure. This app does not enforce local
    RNC/Cédula check-digit or repeated-digit validation.
    """
    if not value:
        return

    digits = _digits_only(value)
    length = len(digits)

    if id_type == "RNC" or (id_type is None and length == 9):
        ok, msg = validate_rnc(value)
        if not ok:
            raise ValidationError(msg)

    elif id_type == "CED" or (id_type is None and length == 11):
        ok, msg = validate_cedula(value)
        if not ok:
            raise ValidationError(msg)

    elif id_type in ("PAS", "EXT"):
        # Passport / foreign ID — no digit-only format check.
        pass

    else:
        # Ambiguous length — just warn about format
        raise ValidationError(
            _("Ingrese un RNC válido (9 dígitos) o una cédula válida (11 dígitos). "
              "Valor recibido: %(n)s dígitos.") % {"n": length}
        )


# ── Public API lookups ────────────────────────────────────────────────────────

def _api_get(url: str) -> dict | None:
    """Shared helper: GET a JSON endpoint, return parsed dict or None."""
    import urllib.request
    import json

    try:
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "curl/8.0",
        })
        with urllib.request.urlopen(req, timeout=6) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode())
    except Exception:
        pass

    return None


def lookup_rnc(rnc: str) -> dict | None:
    """
    Query the Dominican Technology API (DGII mirror).

    Endpoint: https://api-dgii.dominicantechnology.com/api/v1/rnc/{rnc}

    Returns a dict with keys such as:
        rnc, razon_social, actividad_economica, fecha_inicio, estado, regimen_pago
    Returns None if not found or on network error.

    Example:
        data = lookup_rnc("130461554")
        if data:
            print(data["razon_social"])   # "CAFE TROPICAL MAZUR SRL"
    """
    digits = _digits_only(rnc)
    result = _api_get(f"https://api-dgii.dominicantechnology.com/api/v1/rnc/{digits}")
    if result and result.get("exito"):
        return result.get("data")
    return None


def lookup_cedula(cedula: str) -> dict | None:
    """
    Query the MegaPlus API (DGII mirror) for a cédula.

    Endpoint: https://rnc.megaplus.com.do/api/consulta?rnc={cedula}

    Returns a dict with keys such as:
        cedula_rnc, nombre_razon_social, estado, regimen_de_pagos
    Returns None if not found or on network error.

    Note: only returns data for cédulas registered in DGII (people with tax activity).

    Example:
        data = lookup_cedula("00113918205")
        if data:
            print(data["nombre_razon_social"])   # "PEREZ GARCIA JUAN"
    """
    digits = _digits_only(cedula)
    result = _api_get(f"https://rnc.megaplus.com.do/api/consulta?rnc={digits}")
    if result and not result.get("error"):
        return result
    return None


def lookup_name(value: str, id_type: str) -> tuple[str | None, str]:
    """
    Convenience wrapper: look up the full name for any supported ID type.

    Returns (name_string, source_label) or (None, "").

    source_label is "DGII" for both RNC and Cédula (MegaPlus mirrors DGII data).
    """
    digits = _digits_only(value)

    if id_type == "RNC" or (not id_type and len(digits) == 9):
        data = lookup_rnc(digits)
        if data:
            name = data.get("razon_social") or ""
            return name.strip() or None, "DGII"

    elif id_type == "CED" or (not id_type and len(digits) == 11):
        data = lookup_cedula(digits)
        if data:
            name = data.get("nombre_razon_social") or ""
            return name.strip() or None, "DGII"

    return None, ""
