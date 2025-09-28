"""MongoDB schema extractor for dynamic schema discovery."""

import asyncio
import logging
from typing import Dict, Any, List, Set
from collections import defaultdict
from datetime import datetime
from app.core.database import mongodb

logger = logging.getLogger(__name__)


class SchemaExtractor:
    """Extract and analyze MongoDB collection schemas."""

    def __init__(self):
        self.sample_size = 100
        self.max_array_items = 5

    async def extract_database_schema(self) -> Dict[str, Any]:
        """
        Extract complete database schema from MongoDB.

        Returns:
            Dictionary containing collection schemas and metadata
        """
        try:
            db = mongodb.database
            if db is None:
                raise Exception("Database not initialized")

            collection_names = await db.list_collection_names()
            logger.info(f"Found {len(collection_names)} collections")

            schema = {
                "database_name": db.name,
                "extracted_at": datetime.utcnow().isoformat(),
                "collections": {}
            }

            for collection_name in collection_names:
                if collection_name.startswith('system.'):
                    continue

                collection_schema = await self._extract_collection_schema(
                    db[collection_name],
                    collection_name
                )
                schema["collections"][collection_name] = collection_schema

            schema["relationships"] = self._infer_relationships(schema["collections"])

            return schema

        except Exception as e:
            logger.error(f"Failed to extract database schema: {e}")
            raise

    async def _extract_collection_schema(self, collection, collection_name: str) -> Dict[str, Any]:
        """
        Extract schema for a single collection.

        Args:
            collection: MongoDB collection object
            collection_name: Name of the collection

        Returns:
            Collection schema with fields and types
        """
        try:
            count = await collection.count_documents({})

            sample_docs = await collection.find({}).limit(self.sample_size).to_list(length=self.sample_size)

            if not sample_docs:
                return {
                    "document_count": 0,
                    "fields": {},
                    "sample_document": None
                }

            field_info = self._analyze_documents(sample_docs)

            indexes = []
            async for index in collection.list_indexes():
                indexes.append({
                    "name": index.get("name"),
                    "keys": list(index.get("key", {}).keys())
                })

            patterns = self._identify_patterns(sample_docs, collection_name)

            return {
                "document_count": count,
                "sample_size": len(sample_docs),
                "fields": field_info,
                "indexes": indexes,
                "patterns": patterns,
                "sample_document": self._clean_sample_doc(sample_docs[0]) if sample_docs else None
            }

        except Exception as e:
            logger.error(f"Failed to extract schema for collection {collection_name}: {e}")
            return {
                "error": str(e),
                "document_count": 0,
                "fields": {}
            }

    def _analyze_documents(self, documents: List[Dict]) -> Dict[str, Any]:
        """
        Analyze documents to extract field information.

        Args:
            documents: List of sample documents

        Returns:
            Field information with types and statistics
        """
        field_data = defaultdict(lambda: {
            "types": defaultdict(int),
            "nullable": False,
            "array": False,
            "nested": False,
            "examples": set(),
            "count": 0
        })

        for doc in documents:
            self._analyze_document_recursive(doc, field_data)

        fields = {}
        for field_name, data in field_data.items():
            primary_type = max(data["types"].items(), key=lambda x: x[1])[0] if data["types"] else "unknown"

            examples = list(data["examples"])[:3]

            fields[field_name] = {
                "type": primary_type,
                "types": dict(data["types"]),
                "nullable": data["nullable"],
                "array": data["array"],
                "nested": data["nested"],
                "examples": examples,
                "occurrence_rate": round(data["count"] / len(documents), 2)
            }

        return fields

    def _analyze_document_recursive(self, doc: Any, field_data: Dict, prefix: str = ""):
        """
        Recursively analyze document structure.

        Args:
            doc: Document or subdocument to analyze
            field_data: Accumulator for field data
            prefix: Field name prefix for nested fields
        """
        if isinstance(doc, dict):
            for key, value in doc.items():
                field_path = f"{prefix}.{key}" if prefix else key

                if value is None:
                    field_data[field_path]["nullable"] = True
                    field_data[field_path]["types"]["null"] += 1
                elif isinstance(value, dict):
                    field_data[field_path]["nested"] = True
                    field_data[field_path]["types"]["object"] += 1
                    field_data[field_path]["count"] += 1
                    self._analyze_document_recursive(value, field_data, field_path)
                elif isinstance(value, list):
                    field_data[field_path]["array"] = True
                    field_data[field_path]["types"]["array"] += 1
                    field_data[field_path]["count"] += 1
                    for item in value[:self.max_array_items]:
                        if isinstance(item, dict):
                            self._analyze_document_recursive(item, field_data, f"{field_path}[]")
                else:
                    type_name = type(value).__name__
                    field_data[field_path]["types"][type_name] += 1
                    field_data[field_path]["count"] += 1

                    if len(str(value)) < 100:
                        field_data[field_path]["examples"].add(str(value))

    def _identify_patterns(self, documents: List[Dict], collection_name: str) -> Dict[str, Any]:
        """
        Identify common patterns in the collection.

        Args:
            documents: Sample documents
            collection_name: Name of the collection

        Returns:
            Identified patterns like date fields, IDs, etc.
        """
        patterns = {
            "has_timestamps": False,
            "has_status": False,
            "has_shop_id": False,
            "primary_key": None,
            "date_fields": [],
            "reference_fields": []
        }

        if not documents:
            return patterns

        sample = documents[0]

        for key in sample.keys():
            if key in ["_id", "id", f"{collection_name}_id"]:
                patterns["primary_key"] = key

            if key == "shop_id":
                patterns["has_shop_id"] = True

            if key in ["created_at", "updated_at", "date", "timestamp"]:
                patterns["has_timestamps"] = True
                patterns["date_fields"].append(key)

            if key in ["status", "state"]:
                patterns["has_status"] = True

            if key.endswith("_id") and key not in ["_id", "shop_id"]:
                patterns["reference_fields"].append({
                    "field": key,
                    "likely_references": key[:-3]
                })

        return patterns

    def _infer_relationships(self, collections: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Infer relationships between collections based on field names.

        Args:
            collections: All collection schemas

        Returns:
            List of inferred relationships
        """
        relationships = []

        for collection_name, schema in collections.items():
            if "fields" not in schema:
                continue

            for field_name in schema["fields"].keys():
                if field_name.endswith("_id") and field_name not in ["_id", "shop_id"]:
                    potential_collection = field_name[:-3]

                    if potential_collection in collections:
                        relationships.append({
                            "from_collection": collection_name,
                            "from_field": field_name,
                            "to_collection": potential_collection,
                            "to_field": "_id",
                            "type": "reference"
                        })
                    elif potential_collection + "s" in collections:
                        relationships.append({
                            "from_collection": collection_name,
                            "from_field": field_name,
                            "to_collection": potential_collection + "s",
                            "to_field": "_id",
                            "type": "reference"
                        })

        return relationships

    def _clean_sample_doc(self, doc: Dict) -> Dict:
        """
        Clean sample document for display (remove sensitive data).

        Args:
            doc: Sample document

        Returns:
            Cleaned document
        """
        if not doc:
            return {}

        cleaned = {}
        for key, value in doc.items():
            if isinstance(value, str) and len(value) > 50:
                cleaned[key] = value[:50] + "..."
            elif isinstance(value, list) and len(value) > 3:
                cleaned[key] = value[:3] + ["..."]
            elif isinstance(value, dict):
                cleaned[key] = self._clean_sample_doc(value)
            else:
                cleaned[key] = value

        return cleaned

    def format_schema_for_llm(self, schema: Dict[str, Any]) -> str:
        """
        Format schema for LLM consumption.

        Args:
            schema: Extracted database schema

        Returns:
            Formatted string representation
        """
        lines = ["DATABASE SCHEMA:", "=" * 50]

        for collection_name, collection_schema in schema["collections"].items():
            lines.append(f"\nCollection: {collection_name}")
            lines.append(f"Documents: {collection_schema.get('document_count', 0)}")

            if collection_schema.get("patterns", {}).get("has_shop_id"):
                lines.append("Multi-tenant: Yes (has shop_id)")

            lines.append("Fields:")
            fields = collection_schema.get("fields", {})

            for field_name, field_info in fields.items():
                type_str = field_info["type"]
                if field_info.get("array"):
                    type_str = f"Array<{type_str}>"
                if field_info.get("nullable"):
                    type_str += "?"

                lines.append(f"  - {field_name}: {type_str}")

                if field_info.get("examples") and len(field_info["examples"]) > 0:
                    examples = list(field_info["examples"])[:2]
                    examples_str = ", ".join(examples)
                    lines.append(f"    Examples: {examples_str}")

            if collection_schema.get("indexes"):
                lines.append("Indexes:")
                for index in collection_schema["indexes"]:
                    lines.append(f"  - {index['name']}: {', '.join(index['keys'])}")

        if schema.get("relationships"):
            lines.append("\nRELATIONSHIPS:")
            lines.append("-" * 30)
            for rel in schema["relationships"]:
                lines.append(
                    f"{rel['from_collection']}.{rel['from_field']} -> "
                    f"{rel['to_collection']}.{rel['to_field']}"
                )

        return "\n".join(lines)


schema_extractor = SchemaExtractor()