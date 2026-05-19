import pytest
from unittest.mock import MagicMock

from django.core.exceptions import ValidationError

from apps.accounts.validators import (
    validate_image_size,
    HasLetterValidator,
    HasNumberValidator,
    HasSymbolValidator,
)

_MB = 1024 * 1024


class TestValidateImageSize:

    def _make_image(self, size_bytes):
        image = MagicMock()
        image.size = size_bytes
        return image

    def test_passes_under_2mb(self):
        validate_image_size(self._make_image(1 * _MB))

    def test_passes_exactly_2mb(self):
        validate_image_size(self._make_image(2 * _MB))

    def test_raises_above_2mb(self):
        with pytest.raises(ValidationError):
            validate_image_size(self._make_image(2 * _MB + 1))


class TestHasLetterValidator:

    def test_raises_when_no_letter(self):
        v = HasLetterValidator()
        with pytest.raises(ValidationError):
            v.validate("12345678!")

    def test_passes_with_letter(self):
        HasLetterValidator().validate("abc12345!")

    def test_get_help_text_returns_string(self):
        assert str(HasLetterValidator().get_help_text())


class TestHasNumberValidator:

    def test_raises_when_no_digit(self):
        v = HasNumberValidator()
        with pytest.raises(ValidationError):
            v.validate("abcdefgh!")

    def test_passes_with_digit(self):
        HasNumberValidator().validate("abc12345!")

    def test_get_help_text_returns_string(self):
        assert str(HasNumberValidator().get_help_text())


class TestHasSymbolValidator:

    def test_raises_when_no_symbol(self):
        v = HasSymbolValidator()
        with pytest.raises(ValidationError):
            v.validate("abcde123")

    def test_passes_with_symbol(self):
        HasSymbolValidator().validate("abc12345!")

    def test_get_help_text_returns_string(self):
        assert str(HasSymbolValidator().get_help_text())
