from django import forms


# ── Flatpickr date/time widgets ───────────────────────────────────────────────


class FlatpickrDateInput(forms.DateInput):
    def __init__(self, attrs=None, format="%Y-%m-%d"):
        super().__init__(attrs=attrs, format=format)

    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs)
        attrs["type"] = "text"
        attrs["autocomplete"] = "off"
        cls = attrs.get("class", "")
        for needed in ("form-control", "js-flatpickr-date"):
            if needed not in cls:
                cls = f"{cls} {needed}".strip()
        attrs["class"] = cls
        return attrs


class FlatpickrDateTimeInput(forms.DateTimeInput):
    def __init__(self, attrs=None, format="%Y-%m-%d %H:%M"):
        super().__init__(attrs=attrs, format=format)

    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs)
        attrs["type"] = "text"
        attrs["autocomplete"] = "off"
        cls = attrs.get("class", "")
        for needed in ("form-control", "js-flatpickr-datetime"):
            if needed not in cls:
                cls = f"{cls} {needed}".strip()
        attrs["class"] = cls
        return attrs


class FlatpickrTimeInput(forms.TimeInput):
    def __init__(self, attrs=None, format="%H:%M"):
        super().__init__(attrs=attrs, format=format)

    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs)
        attrs["type"] = "text"
        attrs["autocomplete"] = "off"
        cls = attrs.get("class", "")
        for needed in ("form-control", "js-flatpickr-time"):
            if needed not in cls:
                cls = f"{cls} {needed}".strip()
        attrs["class"] = cls
        return attrs


# ── TomSelect / ItbisSelect ───────────────────────────────────────────────────

_ITBIS_RATE_BADGES = {
    "EXEMPT": "0%",
    "RATE_16": "16%",
    "RATE_18": "18%",
}


class TomSelect(forms.Select):
    def __init__(self, *args, placeholder="Seleccione…", **kwargs):
        attrs = kwargs.pop("attrs", None) or {}
        attrs.setdefault("class", "form-select")
        attrs.setdefault("data-tom", "")
        attrs.setdefault("data-placeholder", placeholder)
        super().__init__(*args, attrs=attrs, **kwargs)


class ItbisSelect(TomSelect):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, placeholder="Tasa ITBIS…", **kwargs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        badge = _ITBIS_RATE_BADGES.get(str(value))
        if badge:
            option["attrs"]["data-rate"] = badge
        return option
