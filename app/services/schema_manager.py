"""Schema manager for caching and managing database schema."""

import json
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from app.services.schema_extractor import schema_extractor

logger = logging.getLogger(__name__)


class SchemaManager:
    """Manage database schema with caching and refresh capabilities."""

    def __init__(self):
        self._schema: Optional[Dict[str, Any]] = None
        self._formatted_schema: Optional[str] = None
        self._last_refresh: Optional[datetime] = None
        self._refresh_interval = timedelta(hours=24)
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize schema manager by loading schema."""
        await self.load_schema()

    async def load_schema(self, force: bool = False) -> Dict[str, Any]:
        """
        Load or refresh database schema.

        Args:
            force: Force refresh even if cache is fresh

        Returns:
            Database schema dictionary
        """
        async with self._lock:
            if not force and self._schema and self._last_refresh:
                time_since_refresh = datetime.utcnow() - self._last_refresh
                if time_since_refresh < self._refresh_interval:
                    logger.debug("Using cached schema")
                    return self._schema

            try:
                logger.info("Loading database schema...")

                self._schema = await schema_extractor.extract_database_schema()

                self._formatted_schema = schema_extractor.format_schema_for_llm(self._schema)

                self._last_refresh = datetime.utcnow()

                collection_count = len(self._schema.get("collections", {}))
                logger.info(f"Schema loaded successfully: {collection_count} collections")

                for name, info in self._schema.get("collections", {}).items():
                    doc_count = info.get("document_count", 0)
                    field_count = len(info.get("fields", {}))
                    logger.debug(f"  - {name}: {doc_count} docs, {field_count} fields")

                return self._schema

            except Exception as e:
                logger.error(f"Failed to load schema: {e}")
                if self._schema:
                    logger.warning("Using previously cached schema due to error")
                    return self._schema
                raise

    def get_schema(self) -> Optional[Dict[str, Any]]:
        """
        Get current schema (must be loaded first).

        Returns:
            Database schema or None if not loaded
        """
        return self._schema

    def get_formatted_schema(self) -> Optional[str]:
        """
        Get formatted schema string for LLM.

        Returns:
            Formatted schema string or None if not loaded
        """
        return self._formatted_schema

    def get_collection_schema(self, collection_name: str) -> Optional[Dict[str, Any]]:
        """
        Get schema for specific collection.

        Args:
            collection_name: Name of collection

        Returns:
            Collection schema or None if not found
        """
        if not self._schema:
            return None

        return self._schema.get("collections", {}).get(collection_name)

    def get_collection_fields(self, collection_name: str) -> Optional[Dict[str, Any]]:
        """
        Get field information for a collection.

        Args:
            collection_name: Name of collection

        Returns:
            Field information or None if not found
        """
        collection_schema = self.get_collection_schema(collection_name)
        if collection_schema:
            return collection_schema.get("fields")
        return None

    def has_shop_id(self, collection_name: str) -> bool:
        """
        Check if collection has shop_id field (multi-tenant).

        Args:
            collection_name: Name of collection

        Returns:
            True if collection has shop_id field
        """
        fields = self.get_collection_fields(collection_name)
        if fields:
            return "shop_id" in fields
        return False

    def get_relationships(self) -> Optional[list]:
        """
        Get all inferred relationships.

        Returns:
            List of relationships or None if not loaded
        """
        if not self._schema:
            return None

        return self._schema.get("relationships", [])

    def get_related_collections(self, collection_name: str) -> list:
        """
        Get collections related to the specified collection.

        Args:
            collection_name: Name of collection

        Returns:
            List of related collection names
        """
        if not self._schema:
            return []

        related = set()
        relationships = self.get_relationships() or []

        for rel in relationships:
            if rel["from_collection"] == collection_name:
                related.add(rel["to_collection"])
            elif rel["to_collection"] == collection_name:
                related.add(rel["from_collection"])

        return list(related)

    def get_schema_summary(self) -> Dict[str, Any]:
        """
        Get summary of loaded schema.

        Returns:
            Schema summary with statistics
        """
        if not self._schema:
            return {
                "loaded": False,
                "message": "Schema not loaded"
            }

        collections = self._schema.get("collections", {})

        total_documents = sum(
            coll.get("document_count", 0)
            for coll in collections.values()
        )

        total_fields = sum(
            len(coll.get("fields", {}))
            for coll in collections.values()
        )

        multi_tenant_collections = [
            name for name, coll in collections.items()
            if coll.get("patterns", {}).get("has_shop_id")
        ]

        return {
            "loaded": True,
            "last_refresh": self._last_refresh.isoformat() if self._last_refresh else None,
            "statistics": {
                "collections": len(collections),
                "total_documents": total_documents,
                "total_fields": total_fields,
                "relationships": len(self._schema.get("relationships", [])),
                "multi_tenant_collections": len(multi_tenant_collections)
            },
            "collections": list(collections.keys()),
            "multi_tenant_collections": multi_tenant_collections
        }

    def build_llm_context(self, include_examples: bool = False) -> str:
        """
        Build context string for LLM with schema information.

        Args:
            include_examples: Whether to include field examples

        Returns:
            Context string for LLM
        """
        if not self._formatted_schema:
            return "No schema available. Database schema not loaded."

        context = f"""You have access to the following MongoDB database schema:

{self._formatted_schema}

IMPORTANT NOTES:
1. Collections with 'shop_id' field are multi-tenant - always filter by shop_id
2. Use the exact field names as shown in the schema
3. Date fields should be handled with appropriate MongoDB date operators
4. Array fields require special handling (use $unwind, $elemMatch, etc.)
5. Relationships between collections are indicated by _id fields

When generating MongoDB queries:
- Always use proper MongoDB syntax
- Include appropriate filters based on the schema
- Use aggregation pipelines for complex queries
- Respect data types shown in the schema"""

        return context

    def validate_collection_exists(self, collection_name: str) -> bool:
        """
        Check if a collection exists in the schema.

        Args:
            collection_name: Name of collection to check

        Returns:
            True if collection exists
        """
        if not self._schema:
            return False

        return collection_name in self._schema.get("collections", {})

    def validate_field_exists(self, collection_name: str, field_name: str) -> bool:
        """
        Check if a field exists in a collection.

        Args:
            collection_name: Name of collection
            field_name: Name of field to check

        Returns:
            True if field exists in collection
        """
        fields = self.get_collection_fields(collection_name)
        if not fields:
            return False

        if "." in field_name:
            parent = field_name.split(".")[0]
            return parent in fields

        return field_name in fields

    def get_field_type(self, collection_name: str, field_name: str) -> Optional[str]:
        """
        Get the type of a field.

        Args:
            collection_name: Name of collection
            field_name: Name of field

        Returns:
            Field type or None if not found
        """
        fields = self.get_collection_fields(collection_name)
        if not fields or field_name not in fields:
            return None

        return fields[field_name].get("type")

    async def refresh_schema(self) -> Dict[str, Any]:
        """
        Force refresh the schema from database.

        Returns:
            Updated schema
        """
        logger.info("Manually refreshing database schema...")
        return await self.load_schema(force=True)

    def export_schema(self) -> str:
        """
        Export schema as JSON string.

        Returns:
            JSON representation of schema
        """
        if not self._schema:
            return json.dumps({"error": "Schema not loaded"})

        export_schema = {
            "exported_at": datetime.utcnow().isoformat(),
            "database_name": self._schema.get("database_name"),
            "collections": {}
        }

        for name, coll in self._schema.get("collections", {}).items():
            export_schema["collections"][name] = {
                "document_count": coll.get("document_count"),
                "fields": coll.get("fields"),
                "indexes": coll.get("indexes"),
                "patterns": coll.get("patterns")
            }

        export_schema["relationships"] = self._schema.get("relationships", [])

        return json.dumps(export_schema, indent=2, default=str)


schema_manager = SchemaManager()