# MySQL to MongoDB Data Synchronization Guide

## Overview

This system automatically synchronizes data from MySQL (source) to MongoDB (target) with support for:
- **Dynamic schema discovery** - Automatically detects all tables and fields
- **Full sync** - Complete data migration
- **Incremental sync** - Only syncs changed/new records
- **Automated scheduling** - Periodic sync at configurable intervals
- **Primary key & relationship handling** - Preserves MySQL relationships in MongoDB

## Architecture

### Key Features

1. **Dynamic Schema Discovery**
   - Automatically discovers all MySQL tables
   - Extracts column information, types, and constraints
   - Identifies primary keys and foreign keys
   - Detects timestamp columns for incremental sync

2. **Relationship Handling**
   - Preserves MySQL primary keys as regular fields in MongoDB
   - MongoDB creates its own `_id` field
   - Foreign key relationships remain intact (e.g., `product_id` still references products)
   - Enables joins via aggregation pipelines

3. **Incremental Sync Strategy**
   - Tables WITH `updated_at`/`modified_at`: Syncs only changed records
   - Tables WITHOUT timestamps: Falls back to full sync
   - Tracks last sync time per table in `_sync_metadata` collection

## Configuration

### Environment Variables (`.env`)

```env
# Source MySQL Database
MYSQL_HOST=your-mysql-host.com
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your-password
MYSQL_DATABASE=your-database-name

# Target MongoDB
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=ecominsight

# Sync Settings
SYNC_INTERVAL=300          # Sync every 5 minutes (in seconds)
SYNC_BATCH_SIZE=1000       # Records per batch
SYNC_ENABLED=true          # Enable/disable auto sync
SYNC_TABLES=all            # "all" or "orders,products,customers"
```

## API Endpoints

### 1. Test MySQL Connection

**GET** `/api/sync/test-connection`

Tests connection to MySQL and lists available tables.

```bash
curl http://localhost:8000/api/sync/test-connection
```

**Response:**
```json
{
  "status": "success",
  "connected": true,
  "database": "ecommerce",
  "host": "localhost",
  "tables_count": 25,
  "tables": ["orders", "products", "customers", "categories", ...]
}
```

---

### 2. Trigger Manual Sync

**POST** `/api/sync/trigger`

Manually trigger data synchronization.

**Parameters:**
- `sync_type`: `"full"` or `"incremental"` (default: `"incremental"`)
- `tables`: Comma-separated table names or `"all"` (default: `"all"`)

```bash
# Incremental sync (all tables)
curl -X POST "http://localhost:8000/api/sync/trigger?sync_type=incremental"

# Full sync (specific tables)
curl -X POST "http://localhost:8000/api/sync/trigger?sync_type=full&tables=orders,products"
```

**Response:**
```json
{
  "sync_type": "incremental",
  "start_time": "2025-10-06T12:00:00",
  "end_time": "2025-10-06T12:05:30",
  "duration_seconds": 330.5,
  "total_records_synced": 15420,
  "successful_tables": 25,
  "failed_tables": 0,
  "status": "success",
  "tables": {
    "orders": {
      "status": "success",
      "records_synced": 1250,
      "sync_type": "incremental"
    },
    "products": {
      "status": "success",
      "records_synced": 350,
      "sync_type": "incremental"
    }
  }
}
```

---

### 3. Get Sync Status

**GET** `/api/sync/status`

Get current sync status and last sync times for all tables.

```bash
curl http://localhost:8000/api/sync/status
```

**Response:**
```json
{
  "scheduler": {
    "running": true,
    "interval_seconds": 300,
    "jobs": [
      {
        "id": "sync_job",
        "name": "MySQL to MongoDB sync",
        "next_run_time": "2025-10-06T12:10:00"
      }
    ]
  },
  "sync_data": {
    "total_tables": 25,
    "tables": {
      "orders": {
        "last_sync_time": "2025-10-06T12:05:00",
        "sync_type": "incremental",
        "records_synced": 1250,
        "status": "success",
        "duration_seconds": 12.5
      },
      "products": {
        "last_sync_time": "2025-10-06T12:05:10",
        "sync_type": "incremental",
        "records_synced": 350,
        "status": "success",
        "duration_seconds": 3.2
      }
    }
  }
}
```

---

### 4. Start Auto Sync Scheduler

**POST** `/api/sync/scheduler/start`

Start automatic periodic synchronization.

**Parameters:**
- `interval_seconds`: Sync interval (optional, default from `.env`)

```bash
# Start with default interval (from .env)
curl -X POST http://localhost:8000/api/sync/scheduler/start

# Start with custom interval (every 10 minutes)
curl -X POST "http://localhost:8000/api/sync/scheduler/start?interval_seconds=600"
```

**Response:**
```json
{
  "status": "success",
  "message": "Scheduler started",
  "interval_seconds": 300
}
```

---

### 5. Stop Auto Sync Scheduler

**POST** `/api/sync/scheduler/stop`

Stop automatic synchronization.

```bash
curl -X POST http://localhost:8000/api/sync/scheduler/stop
```

**Response:**
```json
{
  "status": "success",
  "message": "Scheduler stopped"
}
```

## How It Works

### Primary Key & Relationship Handling

**MySQL Table Structure:**
```sql
CREATE TABLE orders (
  id INT PRIMARY KEY,
  customer_id INT,
  product_id INT,
  total DECIMAL(10,2),
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

**MongoDB Document:**
```json
{
  "_id": ObjectId("..."),      // MongoDB's own ID
  "id": 12345,                 // Original MySQL primary key
  "customer_id": 567,          // Foreign key preserved
  "product_id": 89,            // Foreign key preserved
  "total": 99.99,
  "created_at": "2025-10-06T10:30:00",
  "updated_at": "2025-10-06T12:00:00"
}
```

**Why This Approach?**
1. **Preserves Relationships**: `customer_id` and `product_id` remain the same
2. **Enables Queries**: Can query by original MySQL id: `{"id": 12345}`
3. **Supports Joins**: Aggregation pipeline can join: `$lookup` on `customer_id`
4. **No Conflicts**: MongoDB's `_id` is separate from MySQL `id`

### Incremental Sync Logic

For tables with `updated_at` or `modified_at`:

1. **Get Last Sync Time**: Read from `_sync_metadata` collection
   ```json
   {
     "table_name": "orders",
     "last_sync_time": "2025-10-06T11:00:00"
   }
   ```

2. **Query Only Changed Records**:
   ```sql
   SELECT * FROM orders
   WHERE updated_at > '2025-10-06T11:00:00'
   ```

3. **Upsert to MongoDB**: Update existing or insert new
   ```javascript
   collection.replace_one(
     {"id": 12345},  // Match by MySQL primary key
     document,        // Full document
     {upsert: true}   // Insert if not exists
   )
   ```

4. **Update Metadata**: Save new sync time
   ```json
   {
     "table_name": "orders",
     "last_sync_time": "2025-10-06T12:00:00",
     "records_synced": 150
   }
   ```

### Full Sync Logic

For first-time sync or tables without timestamps:

1. **Get Total Count**: `SELECT COUNT(*) FROM table`
2. **Fetch in Batches**: Prevent memory issues
   ```sql
   SELECT * FROM table LIMIT 1000 OFFSET 0
   SELECT * FROM table LIMIT 1000 OFFSET 1000
   ...
   ```
3. **Upsert All Records**: Same as incremental
4. **Track Progress**: Log every batch

## Usage Examples

### Initial Setup

1. **Configure `.env`** with MySQL credentials
2. **Test Connection**:
   ```bash
   curl http://localhost:8000/api/sync/test-connection
   ```

3. **Run Initial Full Sync**:
   ```bash
   curl -X POST "http://localhost:8000/api/sync/trigger?sync_type=full"
   ```

4. **Start Auto Sync** (every 5 minutes):
   ```bash
   curl -X POST http://localhost:8000/api/sync/scheduler/start
   ```

### Ongoing Operations

**Check sync status:**
```bash
curl http://localhost:8000/api/sync/status
```

**Manual sync when needed:**
```bash
curl -X POST "http://localhost:8000/api/sync/trigger?sync_type=incremental"
```

**Sync specific tables:**
```bash
curl -X POST "http://localhost:8000/api/sync/trigger?tables=orders,products"
```

## Monitoring

### Sync Metadata Collection

MongoDB collection `_sync_metadata` tracks all syncs:

```javascript
db._sync_metadata.find().pretty()

// Example output:
{
  "table_name": "orders",
  "sync_type": "incremental",
  "records_synced": 1250,
  "status": "success",
  "duration_seconds": 12.5,
  "last_sync_time": "2025-10-06T12:00:00",
  "timestamp": ISODate("2025-10-06T12:00:00Z")
}
```

### Application Logs

Check `logs/app.log` for detailed sync information:
```
INFO - Starting incremental sync for all tables...
INFO - Total records in orders: 25000
INFO - Found 1250 updated records in orders
INFO - Progress: 1000/1250 records processed
INFO - Sync completed: 25 successful, 0 failed, 15420 records synced
```

## Troubleshooting

### MySQL Connection Failed

**Error**: "Failed to connect to MySQL database"

**Solution**:
1. Check `.env` credentials
2. Verify MySQL server is running
3. Check firewall/network settings
4. Test with: `curl http://localhost:8000/api/sync/test-connection`

### No Timestamp Columns

**Warning**: "Table has no timestamp columns, falling back to full sync"

**Impact**: Table will be fully synced each time (slower but works)

**Solution**: Add `updated_at` column to MySQL table:
```sql
ALTER TABLE your_table
ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
```

### Sync Takes Too Long

**Solution**: Adjust batch size in `.env`:
```env
SYNC_BATCH_SIZE=5000  # Increase for faster sync (uses more memory)
```

### Table Not Syncing

**Check**:
1. Is table listed in `SYNC_TABLES`? (or set to `"all"`)
2. Does table exist in MySQL?
3. Check sync status: `/api/sync/status`

## Performance Considerations

- **Batch Size**: Default 1000 records/batch balances speed and memory
- **Sync Interval**: Default 5 minutes, adjust based on data change frequency
- **Network**: Use same datacenter for MySQL and MongoDB
- **Indexes**: Ensure MySQL has indexes on timestamp columns

## Best Practices

1. **Initial Setup**: Run full sync first, then enable incremental
2. **Monitoring**: Regularly check `/api/sync/status`
3. **Timestamps**: Add `updated_at` to all tables for efficient sync
4. **Table Selection**: Sync only needed tables for faster performance
5. **Scheduling**: Adjust interval based on data update frequency

---

**Your MySQL to MongoDB sync system is now ready!** 🚀

The system will:
- ✅ Automatically discover all tables and schemas
- ✅ Preserve primary keys and relationships
- ✅ Sync data incrementally (only changes)
- ✅ Run on a schedule automatically
- ✅ Provide real-time status via API
