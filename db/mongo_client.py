from datetime import datetime
from typing import Any

from pymongo import MongoClient, ReturnDocument

from base import MONGO_DB, MONGO_URI


class MongoDatabase:
    def __init__(self, uri: str = MONGO_URI, database: str = MONGO_DB):
        self.uri = uri
        self.database_name = database
        self.client = MongoClient(uri)
        self.database = self.client[database]

    def collection(self, name: str):
        return self.database[name]


class MongoCollection:
    def __init__(self, collection_name: str, database: MongoDatabase | None = None):
        self.database = database or MongoDatabase()
        self.collection = self.database.collection(collection_name)

    def find_one(self, query: dict) -> dict[str, Any] | None:
        return self.collection.find_one(query)

    def upsert_one(self, query: dict, updates: dict, set_on_insert: dict | None = None) -> dict[str, Any]:
        update_doc = {"$set": updates}
        if set_on_insert:
            update_doc["$setOnInsert"] = set_on_insert
        return self.collection.find_one_and_update(
            query,
            update_doc,
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )


def normalize_mongo_doc(doc: dict | None):
    if not doc:
        return None
    payload = dict(doc)
    payload.pop("_id", None)
    for key, value in list(payload.items()):
        if isinstance(value, datetime):
            payload[key] = value.isoformat()
    return payload
