from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from app.schemas.profiles import validate_birth_date, validate_image, validate_name


class TestValidateName:
    def test_accepts_normal_name(self):
        validate_name("Taras")

    def test_accepts_hyphenated_name(self):
        validate_name("Anna-Maria")

    def test_rejects_empty_string(self):
        with pytest.raises(ValueError):
            validate_name("   ")

    def test_rejects_digits(self):
        with pytest.raises(ValueError):
            validate_name("T4ras123")

    def test_rejects_too_long_name(self):
        with pytest.raises(ValueError):
            validate_name("a" * 101)


class TestValidateBirthDate:
    def test_accepts_past_date(self):
        validate_birth_date(date(2000, 1, 1))

    def test_rejects_today(self):
        with pytest.raises(ValueError):
            validate_birth_date(date.today())

    def test_rejects_future_date(self):
        with pytest.raises(ValueError):
            validate_birth_date(date.today() + timedelta(days=1))

    def test_rejects_unreasonably_old_date(self):
        with pytest.raises(ValueError):
            validate_birth_date(date(1850, 1, 1))


class TestValidateImage:
    def _make_upload_file(self, content_type: str, size: int) -> MagicMock:
        upload_file = MagicMock()
        upload_file.content_type = content_type
        upload_file.size = size
        return upload_file

    def test_accepts_valid_image(self):
        validate_image(self._make_upload_file("image/jpeg", 1024))

    def test_rejects_unsupported_content_type(self):
        with pytest.raises(ValueError):
            validate_image(self._make_upload_file("application/octet-stream", 1024))

    def test_rejects_oversized_file(self):
        with pytest.raises(ValueError):
            validate_image(self._make_upload_file("image/png", 6 * 1024 * 1024))
