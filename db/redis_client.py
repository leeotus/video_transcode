import json
from typing import Any

import redis

from base import REDIS_URL


class RedisClient:
    def __init__(self, url: str = REDIS_URL):
        """Initialize redis client

        Args:
            url (str, optional): url of redis server. Defaults to REDIS_URL.
        """
        self.url = url
        self.client = redis.from_url(url, decode_responses=True)

    def set_json(self, key: str, value: dict, ttl: int | None = None):
        """Set a redis key with a json value

        Args:
            key (str): redis key
            value (dict): corresponding json value
            ttl (int | None, optional): time to live. Defaults to None, this will make the key never expire.
        """

        payload = json.dumps(value, ensure_ascii=False, default=str)
        if ttl:
            self.client.setex(key, ttl, payload)
        else:
            self.client.set(key, payload)

    def get_json(self, key: str) -> dict[str, Any] | None:
        raw = self.client.get(key)
        if not raw:
            return None
        return json.loads(raw)

    def delete(self, key: str):
        """Delete a redis key

        Args:
            key (str): redis key
        """
        return self.client.delete(key)

    def expire(self, key: str, ttl: int):
        """Check whether a redis key expires in the given ttl or not

        Args:
            key (str): redis key
            ttl (int): time to live
        """
        return self.client.expire(key, ttl)
