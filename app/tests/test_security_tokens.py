from datetime import timedelta

import jwt
import pytest

from app.core.config import settings
from app.exceptions import InvalidTokenTypeError
from app.security.tokens import (
    create_access_token,
    create_refresh_token,
    decode_token,
)


class TestCreateAccessToken:
    def test_encodes_expected_claims(self):
        token = create_access_token(user_id=42)
        decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        assert decoded["sub"] == "42"
        assert decoded["type"] == "access"
        assert "exp" in decoded
        assert "iat" in decoded

    def test_default_expiry_matches_settings(self):
        token = create_access_token(user_id=1)
        decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        expected_lifetime = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        actual_lifetime = decoded["exp"] - decoded["iat"]
        assert actual_lifetime == pytest.approx(expected_lifetime, abs=2)

    def test_custom_expires_delta_is_respected(self):
        token = create_access_token(user_id=1, expires_delta=timedelta(minutes=1))
        decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        assert decoded["exp"] - decoded["iat"] == 60


class TestCreateRefreshToken:
    def test_encodes_expected_claims(self):
        token = create_refresh_token(user_id=7)
        decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        assert decoded["sub"] == "7"
        assert decoded["type"] == "refresh"

    def test_default_expiry_matches_settings(self):
        token = create_refresh_token(user_id=1)
        decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        expected_lifetime = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        actual_lifetime = decoded["exp"] - decoded["iat"]
        assert actual_lifetime == pytest.approx(expected_lifetime, abs=2)

    def test_refresh_token_lives_longer_than_access_token(self):
        access = jwt.decode(
            create_access_token(user_id=1), settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        refresh = jwt.decode(
            create_refresh_token(user_id=1), settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )

        assert refresh["exp"] > access["exp"]


class TestDecodeToken:
    def test_decodes_matching_token_type(self):
        token = create_access_token(user_id=5)
        decoded = decode_token(token, token_type="access")

        assert decoded["sub"] == "5"

    def test_raises_for_mismatched_token_type(self):
        token = create_access_token(user_id=5)

        with pytest.raises(InvalidTokenTypeError):
            decode_token(token, token_type="refresh")

    def test_refresh_token_rejected_as_access_token(self):
        token = create_refresh_token(user_id=5)

        with pytest.raises(InvalidTokenTypeError):
            decode_token(token, token_type="access")

    def test_raises_for_malformed_token(self):
        with pytest.raises(jwt.InvalidTokenError):
            decode_token("not-a-real-token", token_type="access")

    def test_raises_for_expired_token(self):
        expired_token = create_access_token(
            user_id=5, expires_delta=timedelta(seconds=-1)
        )

        with pytest.raises(jwt.ExpiredSignatureError):
            decode_token(expired_token, token_type="access")

    def test_raises_for_token_signed_with_wrong_secret(self):
        tampered = jwt.encode(
            {"sub": "5", "type": "access"}, "wrong-secret", algorithm=settings.ALGORITHM
        )

        with pytest.raises(jwt.InvalidTokenError):
            decode_token(tampered, token_type="access")
