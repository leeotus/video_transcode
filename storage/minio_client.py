import logging
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

from minio import Minio
from minio.error import S3Error

from etc.config import minio_config

logger = logging.getLogger(__name__)


def minio_client():
    return MinioClient()


class MinioClient:
    def __init__(self):
        self.endpoint = minio_config["endpoint"]
        self.access_key = minio_config["access_key"]
        self.secret_key = minio_config["secret_key"]
        self.secure = minio_config.get("secure", False)
        self.public_base_url = minio_config.get("public_base_url") or self._default_public_base_url()
        try:
            self.client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )
        except ValueError:
            logger.error("Minio client initialization failed")
            self.client = None

    def _default_public_base_url(self):
        scheme = "https" if self.secure else "http"
        return f"{scheme}://{self.endpoint}"

    def create_bucket(self, bucket_name):
        if self.client is None:
            raise RuntimeError("Minio client not initialized")
        if self.bucket_exists(bucket_name):
            logger.info("Bucket %s already exists", bucket_name)
            return
        try:
            self.client.make_bucket(bucket_name)
            logger.info("Bucket %s created successfully", bucket_name)
        except S3Error as e:
            logger.error("Error creating bucket %s: %s", bucket_name, e)
            raise

    def bucket_exists(self, bucket_name):
        if self.client is None:
            return False
        return self.client.bucket_exists(bucket_name)

    def presigned_input_url(self, bucket_name, object_name):
        if self.client is None:
            raise RuntimeError("Minio client not initialized")
        return self.client.presigned_get_object(bucket_name, object_name)

    def object_url(self, bucket_name: str, object_name: str):
        return f"{self.public_base_url.rstrip('/')}/{bucket_name}/{object_name.lstrip('/')}"

    def upload_from_file(self, bucket_name: str, object_name: str, path: str, content_type: str | None = None):
        if self.client is None:
            raise RuntimeError("Minio client not initialized")
        if not bucket_name:
            raise ValueError("Bucket name cannot be empty")
        if not object_name:
            raise ValueError("Object name cannot be empty")

        self.create_bucket(bucket_name)
        guessed_type = content_type or mimetypes.guess_type(path)[0] or "application/octet-stream"
        self.client.fput_object(bucket_name, object_name, path, content_type=guessed_type)
        return {
            "bucket": bucket_name,
            "object": object_name,
            "url": self.object_url(bucket_name, object_name),
        }

    def upload_directory(self, bucket_name: str, local_dir: str, object_prefix: str):
        uploaded = []
        base = Path(local_dir)
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            relative_path = path.relative_to(base).as_posix()
            object_name = f"{object_prefix.rstrip('/')}/{relative_path}"
            uploaded.append(self.upload_from_file(bucket_name, object_name, str(path)))
        return uploaded

    def upload_from_stream(
        self,
        bucket_name: str,
        object_name: str,
        data_stream,
        length: int,
        content_type: str = "application/octet-stream",
        part_size: int | None = None,
    ):
        if self.client is None:
            raise RuntimeError("Minio client not initialized")
        if not bucket_name:
            raise ValueError("Bucket name cannot be empty")
        if not object_name:
            raise ValueError("Object name cannot be empty")
        if length == 0:
            raise ValueError("Length cannot be zero")

        actual_part_size = part_size
        if length == -1 and actual_part_size is None:
            actual_part_size = 10 * 1024 * 1024
        if length != -1 and actual_part_size is None:
            actual_part_size = 0

        self.create_bucket(bucket_name)
        try:
            result = self.client.put_object(
                bucket_name,
                object_name,
                data_stream,
                length=length,
                part_size=actual_part_size,
                content_type=content_type or "application/octet-stream",
            )
            logger.info(
                "Uploaded object successfully: bucket:%s, object:%s, etag:%s",
                result.bucket_name,
                result.object_name,
                result.etag,
            )
            return result
        except S3Error:
            logger.exception("Upload object failed: bucket:%s, object:%s", bucket_name, object_name)
            raise


def object_name_from_url(url: str):
    parsed = urlparse(url)
    return parsed.path.lstrip("/")
