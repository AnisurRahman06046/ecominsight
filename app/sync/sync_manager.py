"""Data synchronization manager for MySQL to MongoDB."""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.sync.mysql_connector import mysql_connector
from app.core.database import mongodb
from app.core.config import settings

logger = logging.getLogger(__name__)


class SyncManager:
    """Manage data synchronization from MySQL to MongoDB."""

    def __init__(self):
        self.mysql = mysql_connector
        self.metadata_collection = "_sync_metadata"

    async def sync_all_tables(self, sync_type: str = "full") -> Dict[str, Any]:
        """
        Sync all tables from MySQL to MongoDB.

        Args:
            sync_type: "full" or "incremental"

        Returns:
            Sync summary with statistics
        """
        start_time = datetime.utcnow()
        logger.info(f"Starting {sync_type} sync for all tables...")

        # Get list of tables to sync
        tables = self._get_tables_to_sync()

        if not tables:
            logger.warning("No tables found to sync")
            return {"status": "error", "message": "No tables found"}

        summary = {
            "sync_type": sync_type,
            "start_time": start_time.isoformat(),
            "tables": {},
            "total_records_synced": 0,
            "successful_tables": 0,
            "failed_tables": 0
        }

        # Sync each table
        for table_name in tables:
            logger.info(f"Syncing table: {table_name}")

            try:
                if sync_type == "incremental":
                    result = await self.sync_table_incremental(table_name)
                else:
                    result = await self.sync_table_full(table_name)

                summary["tables"][table_name] = result
                summary["total_records_synced"] += result.get("records_synced", 0)

                if result["status"] == "success":
                    summary["successful_tables"] += 1
                else:
                    summary["failed_tables"] += 1

            except Exception as e:
                logger.error(f"Failed to sync table {table_name}: {e}", exc_info=True)
                summary["tables"][table_name] = {
                    "status": "error",
                    "error": str(e),
                    "records_synced": 0
                }
                summary["failed_tables"] += 1

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        summary["end_time"] = end_time.isoformat()
        summary["duration_seconds"] = duration
        summary["status"] = "success" if summary["failed_tables"] == 0 else "partial"

        logger.info(f"Sync completed: {summary['successful_tables']} successful, "
                   f"{summary['failed_tables']} failed, "
                   f"{summary['total_records_synced']} records synced in {duration:.2f}s")

        return summary

    async def sync_table_full(self, table_name: str) -> Dict[str, Any]:
        """
        Perform full sync for a single table.

        Args:
            table_name: Name of the MySQL table

        Returns:
            Sync result with statistics
        """
        start_time = datetime.utcnow()
        logger.info(f"Full sync started for table: {table_name}")

        try:
            # Get table schema
            schema = self.mysql.get_table_schema(table_name)
            if not schema:
                return {"status": "error", "error": "Failed to get table schema"}

            # Get total count
            total_count = self.mysql.get_table_count(table_name)
            logger.info(f"Total records in {table_name}: {total_count}")

            if total_count == 0:
                return {
                    "status": "success",
                    "records_synced": 0,
                    "message": "Table is empty"
                }

            # Get MongoDB collection
            db = mongodb.database
            collection = db[table_name]

            # Clear existing data (optional - comment out to keep old data)
            # await collection.delete_many({})

            # Fetch and insert data in batches
            batch_size = settings.sync_batch_size
            offset = 0
            total_inserted = 0

            while offset < total_count:
                records = self.mysql.fetch_data(
                    table_name=table_name,
                    batch_size=batch_size,
                    offset=offset
                )

                if not records:
                    break

                # Prepare documents for MongoDB
                documents = self._prepare_documents(records, schema)

                # Upsert documents
                if documents:
                    result = await self._bulk_upsert(collection, documents, schema)
                    total_inserted += result

                offset += batch_size
                logger.info(f"Progress: {min(offset, total_count)}/{total_count} records processed")

            # Save metadata
            await self._save_sync_metadata(
                table_name=table_name,
                sync_type="full",
                records_synced=total_inserted,
                status="success",
                duration=(datetime.utcnow() - start_time).total_seconds()
            )

            return {
                "status": "success",
                "records_synced": total_inserted,
                "total_records": total_count,
                "sync_type": "full"
            }

        except Exception as e:
            logger.error(f"Full sync failed for {table_name}: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "records_synced": 0
            }

    async def sync_table_incremental(self, table_name: str) -> Dict[str, Any]:
        """
        Perform incremental sync for a single table.

        Args:
            table_name: Name of the MySQL table

        Returns:
            Sync result with statistics
        """
        start_time = datetime.utcnow()
        logger.info(f"Incremental sync started for table: {table_name}")

        try:
            # Get table schema
            schema = self.mysql.get_table_schema(table_name)
            if not schema:
                return {"status": "error", "error": "Failed to get table schema"}

            # Check if table has timestamp columns
            if not schema['has_timestamps']:
                logger.warning(f"Table {table_name} has no timestamp columns, falling back to full sync")
                return await self.sync_table_full(table_name)

            # Get last sync time
            last_sync_metadata = await self._get_sync_metadata(table_name)
            if not last_sync_metadata:
                logger.info(f"No previous sync found for {table_name}, performing full sync")
                return await self.sync_table_full(table_name)

            last_sync_time = last_sync_metadata.get("last_sync_time")
            if not last_sync_time:
                return await self.sync_table_full(table_name)

            # Use the first timestamp column
            timestamp_column = schema['timestamp_columns'][0]
            logger.info(f"Using timestamp column: {timestamp_column}, last sync: {last_sync_time}")

            # Get count of updated records
            where_clause = f"`{timestamp_column}` > '{last_sync_time}'"
            updated_count = self.mysql.get_table_count(table_name, where_clause)

            logger.info(f"Found {updated_count} updated records in {table_name}")

            if updated_count == 0:
                return {
                    "status": "success",
                    "records_synced": 0,
                    "message": "No updates found"
                }

            # Get MongoDB collection
            db = mongodb.database
            collection = db[table_name]

            # Fetch and insert updated records in batches
            batch_size = settings.sync_batch_size
            offset = 0
            total_updated = 0

            while offset < updated_count:
                records = self.mysql.fetch_updated_records(
                    table_name=table_name,
                    timestamp_column=timestamp_column,
                    last_sync_time=last_sync_time,
                    batch_size=batch_size,
                    offset=offset
                )

                if not records:
                    break

                # Prepare documents for MongoDB
                documents = self._prepare_documents(records, schema)

                # Upsert documents
                if documents:
                    result = await self._bulk_upsert(collection, documents, schema)
                    total_updated += result

                offset += batch_size
                logger.info(f"Progress: {min(offset, updated_count)}/{updated_count} records processed")

            # Save metadata
            await self._save_sync_metadata(
                table_name=table_name,
                sync_type="incremental",
                records_synced=total_updated,
                status="success",
                duration=(datetime.utcnow() - start_time).total_seconds()
            )

            return {
                "status": "success",
                "records_synced": total_updated,
                "updated_records": updated_count,
                "sync_type": "incremental"
            }

        except Exception as e:
            logger.error(f"Incremental sync failed for {table_name}: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "records_synced": 0
            }

    def _prepare_documents(
        self,
        records: List[Dict[str, Any]],
        schema: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Prepare MySQL records for MongoDB insertion.

        Handles primary key mapping and data type conversions.
        """
        documents = []
        primary_keys = schema.get('primary_keys', [])

        for record in records:
            doc = dict(record)

            # Handle primary key mapping
            # Strategy: Keep MySQL id as-is, MongoDB will create its own _id
            # This preserves relationships and allows querying by original id

            # If you want to map MySQL id to MongoDB _id, uncomment below:
            # if len(primary_keys) == 1 and primary_keys[0] in doc:
            #     doc['_id'] = doc[primary_keys[0]]

            documents.append(doc)

        return documents

    async def _bulk_upsert(
        self,
        collection,
        documents: List[Dict[str, Any]],
        schema: Dict[str, Any]
    ) -> int:
        """
        Perform bulk upsert operation using MongoDB bulk_write for maximum performance.

        Uses primary key for matching existing documents.
        """
        try:
            from pymongo import ReplaceOne

            primary_keys = schema.get('primary_keys', [])

            if not primary_keys:
                # No primary key, just insert (fastest)
                result = await collection.insert_many(documents, ordered=False)
                return len(result.inserted_ids)

            # Build bulk operations list (10-50x faster than individual upserts)
            operations = []
            for doc in documents:
                # Build filter based on primary key(s)
                filter_dict = {}
                for pk in primary_keys:
                    if pk in doc:
                        filter_dict[pk] = doc[pk]

                if filter_dict:
                    operations.append(
                        ReplaceOne(filter_dict, doc, upsert=True)
                    )

            # Execute all operations in a single bulk write
            if operations:
                result = await collection.bulk_write(operations, ordered=False)
                return result.upserted_count + result.modified_count

            return 0

        except Exception as e:
            logger.error(f"Bulk upsert failed: {e}")
            return 0

    async def _save_sync_metadata(
        self,
        table_name: str,
        sync_type: str,
        records_synced: int,
        status: str,
        duration: float
    ):
        """Save sync metadata to MongoDB."""
        try:
            db = mongodb.database
            metadata_collection = db[self.metadata_collection]

            metadata = {
                "table_name": table_name,
                "sync_type": sync_type,
                "records_synced": records_synced,
                "status": status,
                "duration_seconds": duration,
                "last_sync_time": datetime.utcnow().isoformat(),
                "timestamp": datetime.utcnow()
            }

            await metadata_collection.replace_one(
                {"table_name": table_name},
                metadata,
                upsert=True
            )

        except Exception as e:
            logger.error(f"Failed to save sync metadata: {e}")

    async def _get_sync_metadata(self, table_name: str) -> Optional[Dict[str, Any]]:
        """Get last sync metadata for a table."""
        try:
            db = mongodb.database
            metadata_collection = db[self.metadata_collection]

            metadata = await metadata_collection.find_one({"table_name": table_name})
            return metadata

        except Exception as e:
            logger.error(f"Failed to get sync metadata: {e}")
            return None

    async def get_sync_status(self) -> Dict[str, Any]:
        """Get sync status for all tables."""
        try:
            db = mongodb.database
            metadata_collection = db[self.metadata_collection]

            metadata_list = await metadata_collection.find({}).to_list(length=1000)

            status = {
                "total_tables": len(metadata_list),
                "tables": {}
            }

            for metadata in metadata_list:
                table_name = metadata.get("table_name")
                status["tables"][table_name] = {
                    "last_sync_time": metadata.get("last_sync_time"),
                    "sync_type": metadata.get("sync_type"),
                    "records_synced": metadata.get("records_synced"),
                    "status": metadata.get("status"),
                    "duration_seconds": metadata.get("duration_seconds")
                }

            return status

        except Exception as e:
            logger.error(f"Failed to get sync status: {e}")
            return {"error": str(e)}

    def _get_tables_to_sync(self) -> List[str]:
        """Get list of tables to sync based on configuration."""
        all_tables = self.mysql.get_all_tables()

        if settings.sync_tables == "all":
            return all_tables

        # Filter specific tables
        requested_tables = [t.strip() for t in settings.sync_tables.split(',')]
        return [t for t in requested_tables if t in all_tables]


# Global instance
sync_manager = SyncManager()
