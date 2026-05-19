from .minio_client import MinioClient

"""
  这里将FileUploader和MinioClient分离开是为了以后可能会在这里
  进行数据库相关的操作，我希望可以将两者的操作分离开
"""

# TODO FileUploader
class FileUploader(MinioClient):
  pass

def generate_presigned_url(bucket_name: str, object_name: str):
  client = MinioClient()
  return client.presigned_input_url(bucket_name, object_name)
