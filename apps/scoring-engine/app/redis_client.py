import json
import redis
from typing import Any


class RedisClient:
    def __init__(self, url: str):
        self.client = redis.from_url(url, decode_responses=True)

    def ping(self) -> bool:
        try:
            return self.client.ping()
        except redis.ConnectionError:
            return False

    def set_cache(self, key: str, value: Any, ttl: int = 3600) -> None:
        self.client.setex(key, ttl, json.dumps(value))

    def get_cache(self, key: str) -> Any | None:
        data = self.client.get(key)
        if data is None:
            return None
        return json.loads(data)

    def delete_cache(self, key: str) -> None:
        self.client.delete(key)

    def enqueue(self, queue_name: str, payload: dict) -> None:
        self.client.rpush(queue_name, json.dumps(payload))

    def dequeue(self, queue_name: str, timeout: int = 0) -> dict | None:
        if timeout > 0:
            result = self.client.blpop(queue_name, timeout=timeout)
            if result is None:
                return None
            return json.loads(result[1])
        else:
            data = self.client.lpop(queue_name)
            if data is None:
                return None
            return json.loads(data)

    def queue_length(self, queue_name: str) -> int:
        return self.client.llen(queue_name)
