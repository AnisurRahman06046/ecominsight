"""MySQL database connector for data synchronization."""

import logging
import pymysql
from typing import List, Dict, Any, Optional, Tuple
from contextlib import contextmanager
from app.core.config import settings

logger = logging.getLogger(__name__)


class MySQLConnector:
    """Connector for MySQL database operations."""

    def __init__(self):
        self.connection_params = {
            'host': settings.mysql_host,
            'port': settings.mysql_port,
            'user': settings.mysql_user,
            'password': settings.mysql_password,
            'database': settings.mysql_database,
            'charset': 'utf8mb4',
            'cursorclass': pymysql.cursors.DictCursor,
            'autocommit': True,  # Prevent transaction locks
            'read_timeout': 30,
            'write_timeout': 30
        }

    @contextmanager
    def get_connection(self):
        """Get MySQL database connection with context manager."""
        connection = None
        try:
            connection = pymysql.connect(**self.connection_params)
            yield connection
        except Exception as e:
            logger.error(f"MySQL connection error: {e}")
            raise
        finally:
            if connection:
                connection.close()

    def test_connection(self) -> bool:
        """Test MySQL connection."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    return result is not None
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def get_all_tables(self) -> List[str]:
        """Get list of all table names in the database."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SHOW TABLES")
                    tables = [list(row.values())[0] for row in cursor.fetchall()]
                    logger.info(f"Found {len(tables)} tables in MySQL database")
                    return tables
        except Exception as e:
            logger.error(f"Failed to get tables: {e}")
            return []

    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """
        Get detailed schema information for a table.

        Returns:
            Schema dict with columns, primary keys, indexes, etc.
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Get column information
                    cursor.execute(f"DESCRIBE `{table_name}`")
                    columns = cursor.fetchall()

                    # Get primary keys
                    cursor.execute(f"""
                        SELECT COLUMN_NAME
                        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                        WHERE TABLE_SCHEMA = '{settings.mysql_database}'
                        AND TABLE_NAME = '{table_name}'
                        AND CONSTRAINT_NAME = 'PRIMARY'
                    """)
                    primary_keys = [row['COLUMN_NAME'] for row in cursor.fetchall()]

                    # Get foreign keys
                    cursor.execute(f"""
                        SELECT
                            COLUMN_NAME,
                            REFERENCED_TABLE_NAME,
                            REFERENCED_COLUMN_NAME
                        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                        WHERE TABLE_SCHEMA = '{settings.mysql_database}'
                        AND TABLE_NAME = '{table_name}'
                        AND REFERENCED_TABLE_NAME IS NOT NULL
                    """)
                    foreign_keys = cursor.fetchall()

                    # Check for timestamp columns
                    timestamp_columns = []
                    for col in columns:
                        col_name = col['Field'].lower()
                        if col_name in ['updated_at', 'modified_at', 'last_modified', 'timestamp']:
                            timestamp_columns.append(col['Field'])

                    schema = {
                        'table_name': table_name,
                        'columns': columns,
                        'primary_keys': primary_keys,
                        'foreign_keys': foreign_keys,
                        'timestamp_columns': timestamp_columns,
                        'has_timestamps': len(timestamp_columns) > 0
                    }

                    return schema

        except Exception as e:
            logger.error(f"Failed to get schema for table {table_name}: {e}")
            return {}

    def get_table_count(self, table_name: str, where_clause: Optional[str] = None) -> int:
        """Get total record count for a table."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    query = f"SELECT COUNT(*) as count FROM `{table_name}`"
                    if where_clause:
                        query += f" WHERE {where_clause}"

                    cursor.execute(query)
                    result = cursor.fetchone()
                    return result['count'] if result else 0
        except Exception as e:
            logger.error(f"Failed to get count for table {table_name}: {e}")
            return 0

    def fetch_data(
        self,
        table_name: str,
        batch_size: int = 1000,
        offset: int = 0,
        where_clause: Optional[str] = None,
        order_by: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch data from table in batches.

        Args:
            table_name: Name of the table
            batch_size: Number of records per batch
            offset: Starting offset
            where_clause: Optional WHERE condition
            order_by: Optional ORDER BY clause

        Returns:
            List of records as dictionaries
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    query = f"SELECT * FROM `{table_name}`"

                    if where_clause:
                        query += f" WHERE {where_clause}"

                    if order_by:
                        query += f" ORDER BY {order_by}"

                    query += f" LIMIT {batch_size} OFFSET {offset}"

                    cursor.execute(query)
                    records = cursor.fetchall()

                    # Convert datetime objects to strings for MongoDB compatibility
                    return self._convert_datetime_fields(records)

        except Exception as e:
            logger.error(f"Failed to fetch data from {table_name}: {e}")
            return []

    def fetch_updated_records(
        self,
        table_name: str,
        timestamp_column: str,
        last_sync_time: str,
        batch_size: int = 1000,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Fetch only updated records since last sync.

        Args:
            table_name: Name of the table
            timestamp_column: Column to check for updates
            last_sync_time: Last sync timestamp
            batch_size: Number of records per batch
            offset: Starting offset

        Returns:
            List of updated records
        """
        where_clause = f"`{timestamp_column}` > '{last_sync_time}'"
        return self.fetch_data(
            table_name=table_name,
            batch_size=batch_size,
            offset=offset,
            where_clause=where_clause,
            order_by=timestamp_column
        )

    def _convert_datetime_fields(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert datetime objects to ISO format strings."""
        import datetime

        converted_records = []
        for record in records:
            converted_record = {}
            for key, value in record.items():
                if isinstance(value, (datetime.datetime, datetime.date)):
                    converted_record[key] = value.isoformat()
                elif isinstance(value, datetime.time):
                    converted_record[key] = value.strftime('%H:%M:%S')
                elif isinstance(value, bytes):
                    # Convert binary data to hex string
                    converted_record[key] = value.hex()
                else:
                    converted_record[key] = value
            converted_records.append(converted_record)

        return converted_records


# Global instance
mysql_connector = MySQLConnector()
