from datetime import datetime, timezone

from base import MONGO_VIDEO_COLLECTION, VOD_CACHE_TTL
from db.mongo_client import MongoCollection, normalize_mongo_doc
from db.redis_client import RedisClient


def utc_now():
    return datetime.now(timezone.utc)


class VideoRepository:
    def __init__(
        self,
        mongo_collection: MongoCollection | None = None,
        redis_client: RedisClient | None = None,
        cache_ttl: int = VOD_CACHE_TTL,
    ):
        self.mongo = mongo_collection or MongoCollection(MONGO_VIDEO_COLLECTION)
        self.redis = redis_client or RedisClient()
        self.cache_ttl = cache_ttl

    def cache_key(self, video_id: str) -> str:
        return f"vod:video:{video_id}"

    def set_cache(self, video_id: str, payload: dict):
        self.redis.set_json(self.cache_key(video_id), payload, self.cache_ttl)

    def get_cache(self, video_id: str):
        return self.redis.get_json(self.cache_key(video_id))

    def upsert(self, video_id: str, updates: dict):
        updates = dict(updates)
        updates["updated_at"] = utc_now()
        updates.setdefault("video_id", video_id)
        doc = self.mongo.upsert_one(
            {"video_id": video_id},
            updates,
            {"created_at": utc_now()},
        )
        payload = normalize_mongo_doc(doc)
        self.set_cache(video_id, payload)
        return payload

    def find_by_id(self, video_id: str):
        cached = self.get_cache(video_id)
        if cached:
            return cached

        doc = self.mongo.find_one({"video_id": video_id})
        if not doc:
            return None

        payload = normalize_mongo_doc(doc)
        self.set_cache(video_id, payload)
        return payload


_default_repository = VideoRepository()


def video_repository():
    return _default_repository
