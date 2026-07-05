from unittest.mock import AsyncMock

import pytest
from botocore.exceptions import BotoCoreError, NoCredentialsError

from app.exceptions import MinioConnectionError, MinioFileUploadError
from app.storage import minio

pytestmark = pytest.mark.asyncio


class _FakeClientContext:
    def __init__(self, client: AsyncMock):
        self._client = client

    async def __aenter__(self) -> AsyncMock:
        return self._client

    async def __aexit__(self, *exc_info) -> bool:
        return False


@pytest.fixture
def fake_client(monkeypatch) -> AsyncMock:
    client = AsyncMock()
    monkeypatch.setattr(minio, "_get_client", lambda: _FakeClientContext(client))
    monkeypatch.setattr(minio, "_get_public_client", lambda: _FakeClientContext(client))
    return client


class TestUploadAvatar:
    async def test_uploads_and_returns_generated_key(self, fake_client: AsyncMock):
        key = await minio.upload_avatar("42", b"binary-data", "image/png")

        assert key.startswith("avatars/42/")
        assert key.endswith(".png")
        fake_client.put_object.assert_awaited_once()
        call_kwargs = fake_client.put_object.await_args.kwargs
        assert call_kwargs["Key"] == key
        assert call_kwargs["Body"] == b"binary-data"
        assert call_kwargs["ContentType"] == "image/png"

    async def test_raises_connection_error(self, fake_client: AsyncMock):
        fake_client.put_object.side_effect = NoCredentialsError()

        with pytest.raises(MinioConnectionError):
            await minio.upload_avatar("42", b"data")

    async def test_raises_upload_error(self, fake_client: AsyncMock):
        fake_client.put_object.side_effect = BotoCoreError()

        with pytest.raises(MinioFileUploadError):
            await minio.upload_avatar("42", b"data")


class TestDeleteAvatar:
    async def test_deletes_object(self, fake_client: AsyncMock):
        await minio.delete_avatar("avatars/42/old.jpg")

        fake_client.delete_object.assert_awaited_once()
        call_kwargs = fake_client.delete_object.await_args.kwargs
        assert call_kwargs["Key"] == "avatars/42/old.jpg"

    async def test_raises_connection_error(self, fake_client: AsyncMock):
        fake_client.delete_object.side_effect = NoCredentialsError()

        with pytest.raises(MinioConnectionError):
            await minio.delete_avatar("avatars/42/old.jpg")

    async def test_raises_upload_error(self, fake_client: AsyncMock):
        fake_client.delete_object.side_effect = BotoCoreError()

        with pytest.raises(MinioFileUploadError):
            await minio.delete_avatar("avatars/42/old.jpg")


class TestGetAvatarUrl:
    async def test_returns_none_when_no_file_name(self, fake_client: AsyncMock):
        assert await minio.get_avatar_url(None) is None
        fake_client.generate_presigned_url.assert_not_awaited()

    async def test_returns_presigned_url(self, fake_client: AsyncMock):
        fake_client.generate_presigned_url.return_value = "https://minio.local/signed"

        url = await minio.get_avatar_url("avatars/42/new.jpg", expires_in=120)

        assert url == "https://minio.local/signed"
        call_kwargs = fake_client.generate_presigned_url.await_args.kwargs
        assert call_kwargs["Params"]["Key"] == "avatars/42/new.jpg"
        assert call_kwargs["ExpiresIn"] == 120

    async def test_raises_connection_error(self, fake_client: AsyncMock):
        fake_client.generate_presigned_url.side_effect = NoCredentialsError()

        with pytest.raises(MinioConnectionError):
            await minio.get_avatar_url("avatars/42/new.jpg")
