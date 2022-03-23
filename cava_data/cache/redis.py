import aioredis
from aioredis.exceptions import ConnectionError
from typing import Optional
from cava_data.core.config import settings
import time
import logging

logger = logging.getLogger('uvicorn')
logging.root.setLevel(level=logging.INFO)


class RedisDependency:
    """FastAPI Dependency for Redis Connections"""

    redis: Optional[aioredis.client.Redis] = None
    connected: bool = False

    async def __call__(self):
        if self.redis is None:
            await self.init()
        return self.redis

    async def init(self):
        """Initialises the Redis Dependency"""
        self.redis = await aioredis.from_url(settings.REDIS_URI)

        while not self.connected:
            try:
                await self.redis.ping()
                self.connected = True
                logger.info("Redis connected!")
            except ConnectionError:
                logger.warning("Not connected to Redis. Trying again.")
                time.sleep(5)


redis_dependency: RedisDependency = RedisDependency()
