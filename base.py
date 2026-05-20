import os

DEFAULT_BUCKET = os.getenv("VIDEO_BUCKET", "videos")
DEFAULT_DST_WIDTH = int(os.getenv("DST_WIDTH", "1920"))
DEFAULT_DST_HEIGHT = int(os.getenv("DST_HEIGHT", "1080"))
STREAM_CHUNK_SIZE = int(os.getenv("STREAM_CHUNK_SIZE", str(256 * 1024)))

VOD_BUCKET = os.getenv("VOD_BUCKET", "vod")
VOD_TMP_DIR = os.getenv("VOD_TMP_DIR", "/tmp/video-transcode-vod")
VOD_HLS_TIME = int(os.getenv("VOD_HLS_TIME", "4"))
VOD_CACHE_TTL = int(os.getenv("VOD_CACHE_TTL", str(7 * 24 * 60 * 60)))
VOD_COVER_TTL = int(os.getenv("VOD_COVER_TTL", str(7 * 24 * 60 * 60)))
VOD_DEFAULT_WIDTH = int(os.getenv("VOD_DEFAULT_WIDTH", "1920"))
VOD_DEFAULT_HEIGHT = int(os.getenv("VOD_DEFAULT_HEIGHT", "1080"))

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:8379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
MONGO_DB = os.getenv("MONGO_DB", "video_transcode")
MONGO_VIDEO_COLLECTION = os.getenv("MONGO_VIDEO_COLLECTION", "vod_videos")
