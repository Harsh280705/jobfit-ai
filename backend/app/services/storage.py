"""Storage abstraction: LocalStorage (dev) + S3Storage (prod-ready)."""
from __future__ import annotations
import os
import uuid
from abc import ABC, abstractmethod


def _secure(name: str) -> str:
    keep = "".join(c if (c.isalnum() or c in ("-", "_", ".")) else "_" for c in name)
    return keep[-200:] or "upload.bin"


class StorageService(ABC):
    @abstractmethod
    def save(self, data: bytes, filename: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def load(self, path: str) -> bytes:
        raise NotImplementedError


class LocalStorage(StorageService):
    def __init__(self, base_path: str):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)

    def save(self, data: bytes, filename: str) -> str:
        safe = _secure(filename)
        # path traversal protection: never trust directories from client
        dest = os.path.join(self.base_path, f"{uuid.uuid4().hex}_{safe}")
        with open(dest, "wb") as f:
            f.write(data)
        return dest

    def load(self, path: str) -> bytes:
        base = os.path.abspath(self.base_path)
        target = os.path.abspath(path)
        if not target.startswith(base):
            raise ValueError("Path traversal blocked")
        with open(target, "rb") as f:
            return f.read()


class S3Storage(StorageService):
    """Production-ready stub: requires boto3 + env config. Falls back clearly if unconfigured."""

    def __init__(self, bucket: str):
        try:
            import boto3  # type: ignore
        except ImportError as e:
            raise RuntimeError("boto3 is required for S3Storage") from e
        import os as _os

        self.bucket = bucket or _os.environ.get("S3_BUCKET", "")
        self._s3 = boto3.client("s3")

    def save(self, data: bytes, filename: str) -> str:
        import uuid as _uuid

        key = f"uploads/{_uuid.uuid4().hex}_{_secure(filename)}"
        self._s3.put_object(Bucket=self.bucket, Key=key, Body=data)
        return f"s3://{self.bucket}/{key}"

    def load(self, path: str) -> bytes:
        assert path.startswith("s3://")
        _, _, rest = path[5:].partition("/")
        bucket, _, key = rest.partition("/")
        obj = self._s3.get_object(Bucket=bucket or self.bucket, Key=key)
        return obj["Body"].read()


def get_storage() -> StorageService:
    from app.core.config import get_settings

    settings = get_settings()
    bucket = os.environ.get("S3_BUCKET", "")
    if bucket:
        return S3Storage(bucket)
    return LocalStorage(settings.FILE_STORAGE_PATH)
