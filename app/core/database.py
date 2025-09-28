"""MongoDB database connection and management."""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional, Dict, Any, List
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class MongoDB:
    """MongoDB connection manager."""

    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.database: Optional[AsyncIOMotorDatabase] = None

    async def connect(self) -> bool:
        """Connect to MongoDB."""
        try:
            self.client = AsyncIOMotorClient(
                settings.mongodb_url,
                maxPoolSize=settings.mongodb_max_pool_size,
                minPoolSize=settings.mongodb_min_pool_size,
            )
            self.database = self.client[settings.mongodb_database]

            # Test connection
            await self.database.command("ping")
            logger.info("Successfully connected to MongoDB")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            return False

    async def disconnect(self):
        """Disconnect from MongoDB."""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")

    async def execute_aggregation(
        self,
        collection: str,
        pipeline: List[Dict[str, Any]],
        timeout: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Execute aggregation pipeline."""
        if self.database is None:
            raise RuntimeError("Database not connected")

        try:
            coll = self.database[collection]
            options = {}
            if timeout:
                options['maxTimeMS'] = timeout * 1000
            cursor = coll.aggregate(pipeline, **options)
            results = await cursor.to_list(length=None)
            return results
        except Exception as e:
            logger.error(f"Aggregation failed: {e}")
            raise

    async def find_one(
        self, collection: str, filter: Dict[str, Any], projection: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Find single document."""
        if self.database is None:
            raise RuntimeError("Database not connected")

        coll = self.database[collection]
        return await coll.find_one(filter, projection)

    async def find(
        self,
        collection: str,
        filter: Dict[str, Any],
        projection: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        sort: Optional[List[tuple]] = None,
    ) -> List[Dict[str, Any]]:
        """Find multiple documents."""
        if self.database is None:
            raise RuntimeError("Database not connected")

        coll = self.database[collection]
        cursor = coll.find(filter, projection)

        if sort:
            cursor = cursor.sort(sort)

        cursor = cursor.limit(limit)
        return await cursor.to_list(length=limit)

    async def insert_one(self, collection: str, document: Dict[str, Any]) -> str:
        """Insert single document."""
        if self.database is None:
            raise RuntimeError("Database not connected")

        coll = self.database[collection]
        result = await coll.insert_one(document)
        return str(result.inserted_id)

    async def insert_many(self, collection: str, documents: List[Dict[str, Any]]) -> List[str]:
        """Insert multiple documents."""
        if self.database is None:
            raise RuntimeError("Database not connected")

        coll = self.database[collection]
        result = await coll.insert_many(documents)
        return [str(id) for id in result.inserted_ids]

    async def get_collection_stats(self, collection: str) -> Dict[str, Any]:
        """Get collection statistics."""
        if self.database is None:
            raise RuntimeError("Database not connected")

        stats = await self.database.command("collStats", collection)
        return {
            "count": stats.get("count", 0),
            "size": stats.get("size", 0),
            "avgObjSize": stats.get("avgObjSize", 0),
            "indexes": stats.get("nindexes", 0),
        }

    async def list_collections(self) -> List[str]:
        """List all collections in database."""
        if self.database is None:
            raise RuntimeError("Database not connected")

        return await self.database.list_collection_names()


# Global MongoDB instance
mongodb = MongoDB()