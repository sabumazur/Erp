import re
from django.core.exceptions import ValidationError


class HasLetterValidator:
    def validate(self, password, user=None):
        if not re.search(r'[a-zA-Z]', password):
            raise ValidationError('Password must contain at least one letter.')

    def get_help_text(self):
        return 'Your password must contain at least one letter.'


class HasNumberValidator:
    def validate(self, password, user=None):
        if not re.search(r'\d', password):
            raise ValidationError('Password must contain at least one number.')

    def get_help_text(self):
        return 'Your password must contain at least one number.'


class HasSymbolValidator:
    def validate(self, password, user=None):
        if not re.search(r'[^a-zA-Z0-9]', password):
            raise ValidationError('Password must contain at least one symbol.')

    def get_help_text(self):
        return 'Your password must contain at least one symbol.'
