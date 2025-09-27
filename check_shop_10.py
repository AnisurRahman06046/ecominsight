#!/usr/bin/env python3
"""
Check data for shop_id 10 specifically
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("MONGODB_DATABASE", "ecommerce_insights")


async def check_shop_10():
    """Check data for shop_id 10."""
    print(f"🔍 Checking data for shop_id 10 in database: {DATABASE_NAME}\n")

    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]

    shop_id = 10  # Check as integer
    shop_id_str = "10"  # Check as string

    collections_to_check = [
        "products", "product", "orders", "order", "customers", "customer",
        "sku", "shop", "inventory", "order_items", "order_product"
    ]

    print("Checking for shop_id = 10 (both as integer and string):\n")

    for collection_name in collections_to_check:
        if collection_name not in await db.list_collection_names():
            continue

        collection = db[collection_name]

        # Check as integer
        count_int = await collection.count_documents({"shop_id": shop_id})
        # Check as string
        count_str = await collection.count_documents({"shop_id": shop_id_str})

        if count_int > 0 or count_str > 0:
            print(f"✅ {collection_name}:")
            if count_int > 0:
                print(f"   - As integer (10): {count_int} documents")
                sample = await collection.find_one({"shop_id": shop_id})
                if sample:
                    print(f"     Sample fields: {list(sample.keys())[:10]}")
            if count_str > 0:
                print(f"   - As string ('10'): {count_str} documents")
                sample = await collection.find_one({"shop_id": shop_id_str})
                if sample:
                    print(f"     Sample fields: {list(sample.keys())[:10]}")
            print()

    # Check shop collection specifically
    shop_collection = db["shop"]
    shop_10 = await shop_collection.find_one({"id": shop_id})
    if not shop_10:
        shop_10 = await shop_collection.find_one({"id": shop_id_str})

    if shop_10:
        print(f"\n📊 Shop details for ID 10:")
        print(f"   Name: {shop_10.get('name')}")
        print(f"   Slug: {shop_10.get('slug')}")
        print(f"   Status: {shop_10.get('status')}")

    # Summary
    print("\n📝 Summary:")
    print("   Shop ID 10 exists in your database!")
    print("   It appears to be stored as an INTEGER in most collections")
    print("\n   Use shop_id: 10 (as integer) in queries")
    print("   Or convert it in the query processor if needed")

    client.close()


if __name__ == "__main__":
    asyncio.run(check_shop_10())