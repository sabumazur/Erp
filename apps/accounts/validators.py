import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

_MAX_IMAGE_BYTES = 2 * 1024 * 1024  # 2 MB


def validate_image_size(image):
    if image.size > _MAX_IMAGE_BYTES:
        raise ValidationError(
            _("El archivo de imagen es demasiado grande (máx. 2 MB).")
        )


class HasLetterValidator:
    def validate(self, password, user=None):
        if not re.search(r'[a-zA-Z]', password):
            raise ValidationError(_('La contraseña debe contener al menos una letra.'))

    def get_help_text(self):
        return _('Tu contraseña debe contener al menos una letra.')


class HasNumberValidator:
    def validate(self, password, user=None):
        if not re.search(r'\d', password):
            raise ValidationError(_('La contraseña debe contener al menos un número.'))

    def get_help_text(self):
        return _('Tu contraseña debe contener al menos un número.')


class HasSymbolValidator:
    def validate(self, password, user=None):
        if not re.search(r'[^a-zA-Z0-9]', password):
            raise ValidationError(_('La contraseña debe contener al menos un símbolo.'))

    def get_help_text(self):
        return _('Tu contraseña debe contener al menos un símbolo.')
