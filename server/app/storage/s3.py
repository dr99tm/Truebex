"""The `s3` storage adapter: any S3-compatible bucket (PF14).

Downloads and uploads use presigned URLs, so large files never pass through
the API. Objects under the public prefixes are served from CDN_BASE_URL when
it is set. A presigned PUT cannot enforce `max_bytes`; callers `stat` the
object after the upload and refuse one that is too large. The SHA-256 of a
`put` is kept as object metadata; `list` leaves it empty (it would cost one
HEAD per object).
"""

import hashlib
from typing import BinaryIO

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from . import PUBLIC_PREFIXES, BlobInfo, check_key


class S3Store:
    def __init__(
        self,
        *,
        bucket: str,
        endpoint: str | None,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        cdn_base_url: str = "",
    ) -> None:
        self.bucket = bucket
        self.cdn_base_url = cdn_base_url.rstrip("/")
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=region,
            aws_access_key_id=access_key_id or None,
            aws_secret_access_key=secret_access_key or None,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    @classmethod
    def from_settings(cls, s) -> "S3Store":
        return cls(
            bucket=s.s3_bucket,
            endpoint=s.s3_endpoint or None,
            region=s.s3_region,
            access_key_id=s.s3_access_key_id,
            secret_access_key=s.s3_secret_access_key,
            cdn_base_url=s.cdn_base_url,
        )

    def put(
        self,
        key: str,
        data: bytes | BinaryIO,
        *,
        content_type: str,
        cache_control: str | None = None,
    ) -> BlobInfo:
        check_key(key)
        payload = bytes(data) if isinstance(data, (bytes, bytearray, memoryview)) else data.read()
        digest = hashlib.sha256(payload).hexdigest()
        extra = {"CacheControl": cache_control} if cache_control else {}
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=payload,
            ContentType=content_type,
            Metadata={"sha256": digest},
            **extra,
        )
        return BlobInfo(
            key=key,
            bytes=len(payload),
            content_type=content_type,
            sha256=digest,
            cache_control=cache_control,
        )

    def open(self, key: str) -> BinaryIO:
        check_key(key)
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"]

    def stat(self, key: str) -> BlobInfo | None:
        check_key(key)
        try:
            head = self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return None
            raise
        return BlobInfo(
            key=key,
            bytes=int(head["ContentLength"]),
            content_type=head.get("ContentType") or "application/octet-stream",
            sha256=(head.get("Metadata") or {}).get("sha256", ""),
            cache_control=head.get("CacheControl"),
            modified_at=head.get("LastModified"),
        )

    def delete(self, key: str) -> None:
        check_key(key)
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def list(self, prefix: str = "") -> list[BlobInfo]:
        out = []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                out.append(
                    BlobInfo(
                        key=obj["Key"],
                        bytes=int(obj["Size"]),
                        content_type="application/octet-stream",
                        sha256="",
                        modified_at=obj.get("LastModified"),
                    )
                )
        return sorted(out, key=lambda b: b.key)

    def signed_get_url(self, key: str, *, expires_in: int = 900, filename: str | None = None) -> str:
        check_key(key)
        if self.cdn_base_url and key.startswith(PUBLIC_PREFIXES) and not filename:
            return f"{self.cdn_base_url}/{key}"
        params = {"Bucket": self.bucket, "Key": key}
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
        return self.client.generate_presigned_url("get_object", Params=params, ExpiresIn=expires_in)

    def signed_put_url(
        self, key: str, *, expires_in: int = 900, content_type: str, max_bytes: int
    ) -> str:
        check_key(key)
        return self.client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires_in,
        )
