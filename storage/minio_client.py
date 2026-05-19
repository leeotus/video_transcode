from minio import Minio
from minio.error import S3Error
from etc.config import minio_config
from typing import BinaryIO, Optional
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.Logger(__name__)

def minio_client():
    return MinioClient()

class MinioClient:
    def __init__(self):
        self.endpoint = minio_config["endpoint"]
        self.access_key = minio_config["access_key"]
        self.secret_key = minio_config["secret_key"]
        self.secure = minio_config.get("secure", False)
        try:
            self.client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )
        except ValueError:
            logger.error("Minio client initialization failed")
            self.client = None  # failed to connect to the minio

    def create_bucket(self, bucket_name):
        """ create a bucket

        Args:
            bucket_name (str): name of the bucket
        """
        if self.client is None:
            return
        if self._check_bucket(bucket_name):
            # no need to create again
            logger.info(f"Bucket {bucket_name} already exists")
            return
        try:
            self.client.make_bucket(bucket_name)
            logger.info(f"Bucket {bucket_name} created successfully")
        except S3Error as e:
            logger.error(f"Error creating bucket {bucket_name}: {e}")

    def presigned_input_url(self, bucket_name, object_name):
        """ get presigned url for input video

        Args:
            bucket_name (str): name of the bucket
            object_name (str): name of the upload object

        Returns:
            str: presigned url for input video
        """
        return self.client.presigned_get_object(bucket_name, object_name)

    # TODO: upload from local file
    def upload_from_file(self, *, path):
      pass

    def upload_from_stream(
      self,
      bucket_name: str,
      object_name: str,
      data_stream: BinaryIO,
      length: int,
      content_type: str = "application/octet-stream",
      part_size: Optional[int] = None,
    ):
      """Upload object from a binary stream

      Args:
          bucket_name (str): Minio bucket name
          object_name (str): name/path in the bucket
          data_stream (BinaryIO): Binary stream, for example Flask request.stream
          length (int): Object size in bytes. Use -1 if unknown
          content_type (str, optional): MIME type
          part_size (Optional[int], optional): Multipart upload part size, required when length is -1. Defaults to None.
      """
      # errors
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
        actual_part_size = 10 * 1024 * 1024   # 10MB
      if length != -1 and actual_part_size is None:
        actual_part_size = 0

      self.create_bucket(bucket_name) # create bucket if not exists
      try:
        result = self.client.put_object( # upload to minio
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
        logger.exception(
          "Upload object failed: bucket:%s, object:%s",
          bucket_name,
          object_name,
        )
        raise


    def _check_bucket(self, bucket_name):
        """ check whether 'bucket_name' exists or not

        Args:
            bucket_name (str): name of bucket

        Returns:
            bool: True if exists, False otherwise
        """
        if self.client is None:
            return False
        if self.client.bucket_exists(bucket_name):
            return True
        return False
