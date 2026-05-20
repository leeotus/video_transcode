from storage.minio_client import object_name_from_url
from storage.vod_storage import vod_storage


def upload_file(local_path: str, object_name: str, bucket: str | None = None, content_type: str | None = None):
    storage = vod_storage()
    if bucket:
        storage.bucket = bucket
    result = storage.upload_file(local_path, object_name, content_type)
    return result["url"]


def upload_directory(local_dir: str, object_prefix: str, bucket: str | None = None):
    storage = vod_storage()
    if bucket:
        storage.bucket = bucket
    uploaded = storage.upload_directory(local_dir, object_prefix)
    return [{"object": item["object"], "url": item["url"]} for item in uploaded]
