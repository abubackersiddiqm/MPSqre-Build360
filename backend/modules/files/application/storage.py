from __future__ import annotations

from dataclasses import dataclass

import boto3
from botocore.client import Config
from django.conf import settings


@dataclass(frozen=True, slots=True)
class StoredObjectMetadata:
    size_bytes: int
    sha256: str
    content_type: str


def _client(*, public: bool = False):  # type: ignore[no-untyped-def]
    endpoint = (
        settings.OBJECT_STORAGE_PUBLIC_ENDPOINT
        if public
        else settings.OBJECT_STORAGE_ENDPOINT
    )
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.OBJECT_STORAGE_ACCESS_KEY,
        aws_secret_access_key=settings.OBJECT_STORAGE_SECRET_KEY,
        region_name=settings.OBJECT_STORAGE_REGION,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def create_upload_url(
    *,
    object_key: str,
    content_type: str,
    sha256: str,
    expires_seconds: int = 900,
) -> str:
    return str(
        _client(public=True).generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.OBJECT_STORAGE_BUCKET,
                "Key": object_key,
                "ContentType": content_type,
                "Metadata": {"sha256": sha256},
            },
            ExpiresIn=expires_seconds,
        )
    )


def head_object(*, object_key: str) -> StoredObjectMetadata:
    response = _client().head_object(
        Bucket=settings.OBJECT_STORAGE_BUCKET,
        Key=object_key,
    )
    metadata = response.get("Metadata", {})
    return StoredObjectMetadata(
        size_bytes=int(response["ContentLength"]),
        sha256=str(metadata.get("sha256", "")).lower(),
        content_type=str(response.get("ContentType", "application/octet-stream")),
    )


def create_download_url(*, object_key: str, expires_seconds: int = 300) -> str:
    return str(
        _client(public=True).generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.OBJECT_STORAGE_BUCKET, "Key": object_key},
            ExpiresIn=expires_seconds,
        )
    )
