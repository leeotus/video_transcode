from base import VOD_BUCKET
from storage.minio_client import MinioClient, minio_client


class VodStorage:
    def __init__(self, bucket: str = VOD_BUCKET, client: MinioClient | None = None):
        self.bucket = bucket
        self.client = client or minio_client()

    def upload_file(self, local_path: str, object_name: str, content_type: str | None = None):
        return self.client.upload_from_file(self.bucket, object_name, local_path, content_type)

    def upload_directory(self, local_dir: str, object_prefix: str):
        return self.client.upload_directory(self.bucket, local_dir, object_prefix)

    def object_url(self, object_name: str):
        return self.client.object_url(self.bucket, object_name)

    def presigned_url(self, object_name: str):
        return self.client.presigned_input_url(self.bucket, object_name)


def vod_storage():
    return VodStorage()
