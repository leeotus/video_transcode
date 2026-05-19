import os

DEFAULT_BUCKET = os.getenv("VIDEO_BUCKET", "videos")
DEFAULT_DST_WIDTH = int(os.getenv("DST_WIDTH", "1920"))
DEFAULT_DST_HEIGHT = int(os.getenv("DST_HEIGHT", "1080"))
STREAM_CHUNK_SIZE = int(os.getenv("STREAM_CHUNK_SIZE", str(256 * 1024)))
