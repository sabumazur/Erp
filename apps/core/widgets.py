from django import forms


# ── Native date/time widgets ──────────────────────────────────────────────────
# Browser-native pickers (type=date/datetime-local/time) styled by Bootstrap's
# .form-control. The value must be pre-formatted to match the input type.


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, attrs=None, format="%Y-%m-%d"):
        super().__init__(attrs=attrs, format=format)

    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs)
        cls = attrs.get("class", "")
        if "form-control" not in cls:
            cls = f"{cls} form-control".strip()
        attrs["class"] = cls
        return attrs


class DateTimeInput(forms.DateTimeInput):
    # datetime-local needs the "T" separator; fields reusing this widget must set
    # input_formats=["%Y-%m-%dT%H:%M"] so Django parses the posted value.
    input_type = "datetime-local"

    def __init__(self, attrs=None, format="%Y-%m-%dT%H:%M"):
        super().__init__(attrs=attrs, format=format)

    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs)
        cls = attrs.get("class", "")
        if "form-control" not in cls:
            cls = f"{cls} form-control".strip()
        attrs["class"] = cls
        return attrs


class TimeInput(forms.TimeInput):
    input_type = "time"

    def __init__(self, attrs=None, format="%H:%M"):
        super().__init__(attrs=attrs, format=format)

    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs)
        cls = attrs.get("class", "")
        if "form-control" not in cls:
            cls = f"{cls} form-control".strip()
        attrs["class"] = cls
        return attrs


# ── TomSelect / ItbisSelect ───────────────────────────────────────────────────

_ITBIS_RATE_BADGES: dict = {}


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


# ── AutosizeTextarea ──────────────────────────────────────────────────────────


class AutosizeTextarea(forms.Textarea):
    """Textarea that grows with its content via a JS .autosize-ta hook."""

    def __init__(self, attrs=None):
        merged = {"rows": 2}
        if attrs:
            merged.update(attrs)
        super().__init__(attrs=merged)

    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs)
        cls = attrs.get("class", "")
        for needed in ("form-control", "autosize-ta"):
            if needed not in cls:
                cls = f"{cls} {needed}".strip()
        attrs["class"] = cls
        return attrs
