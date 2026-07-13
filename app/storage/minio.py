import uuid
from typing import Optional, Union, Any

import aioboto3
from botocore.exceptions import (
    BotoCoreError,
    NoCredentialsError,
    HTTPClientError,
    ConnectionError,
)


from app.core.config import settings
from app.exceptions import MinioConnectionError, MinioFileUploadError
from loguru import logger
from botocore.exceptions import ClientError


_session = aioboto3.Session(
    aws_access_key_id=settings.STORAGE_ACCESS_KEY,
    aws_secret_access_key=settings.STORAGE_SECRET_KEY,
)


_public_session = aioboto3.Session(
    aws_access_key_id=settings.STORAGE_ACCESS_KEY,
    aws_secret_access_key=settings.STORAGE_SECRET_KEY,
)


def _get_public_client() -> Any:
    return _public_session.client("s3", endpoint_url=settings.STORAGE_PUBLIC_URL)


async def get_avatar_url(file_name: Optional[str], expires_in: int = 3600) -> Optional[str]:
    if not file_name:
        return None

    try:
        async with _get_public_client() as client:
            return await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.STORAGE_BUCKET_NAME, "Key": file_name},
                ExpiresIn=expires_in,
            )
    except (ConnectionError, HTTPClientError, NoCredentialsError) as e:
        raise MinioConnectionError(f"Failed to connect to MinIO storage: {str(e)}") from e


async def init_storage() -> None:
    try:
        async with _get_client() as client:
            await ensure_bucket_exists(client, settings.STORAGE_BUCKET_NAME)
    except (ConnectionError, HTTPClientError, NoCredentialsError) as e:
        raise MinioConnectionError(f"Failed to connect to MinIO storage: {str(e)}") from e


async def ensure_bucket_exists(client: Any, bucket_name: str) -> None:
    try:
        await client.head_bucket(Bucket=bucket_name)
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code in ("404", "NoSuchBucket"):
            await client.create_bucket(Bucket=bucket_name)
            logger.info(f"Created bucket: {bucket_name}")
        else:
            raise


def _get_client(public: bool = False) -> Any:
    endpoint = settings.STORAGE_PUBLIC_URL if public else settings.STORAGE_ENDPOINT_URL
    return _session.client("s3", endpoint_url=endpoint)


async def upload_avatar(
    user_id: str,
    file_data: Union[bytes, bytearray],
    content_type: str = "image/jpeg",
) -> str:
    extension = content_type.split("/")[-1] or "jpg"
    file_name = f"avatars/{user_id}/{uuid.uuid4().hex}.{extension}"

    try:
        async with _get_client() as client:
            await client.put_object(
                Bucket=settings.STORAGE_BUCKET_NAME,
                Key=file_name,
                Body=file_data,
                ContentType=content_type,
            )
    except (ConnectionError, HTTPClientError, NoCredentialsError) as e:
        raise MinioConnectionError(f"Failed to connect to MinIO storage: {str(e)}") from e
    except BotoCoreError as e:
        raise MinioFileUploadError(f"Failed to upload avatar to MinIO storage: {str(e)}") from e

    return file_name


async def delete_avatar(file_name: str) -> None:
    try:
        async with _get_client() as client:
            await client.delete_object(
                Bucket=settings.STORAGE_BUCKET_NAME,
                Key=file_name,
            )
    except (ConnectionError, HTTPClientError, NoCredentialsError) as e:
        raise MinioConnectionError(f"Failed to connect to MinIO storage: {str(e)}") from e
    except BotoCoreError as e:
        raise MinioFileUploadError(f"Failed to delete avatar from MinIO storage: {str(e)}") from e
