#!/usr/bin/env python3
"""
Check what data exists in MongoDB and find valid shop_ids
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
from pprint import pprint

# Load environment variables
load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("MONGODB_DATABASE", "ecommerce_insights")


async def check_data():
    """Check existing MongoDB data."""
    print(f"🔍 Checking MongoDB data in database: {DATABASE_NAME}")
    print(f"   URL: {MONGODB_URL}\n")

    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]

    # List all collections
    collections = await db.list_collection_names()
    print(f"📂 Collections found: {collections}\n")

    # Check each collection
    for collection_name in collections:
        collection = db[collection_name]
        count = await collection.count_documents({})
        print(f"📊 {collection_name}: {count} documents")

        # Show sample document
        if count > 0:
            sample = await collection.find_one()
            print(f"   Sample fields: {list(sample.keys())}")

            # For key collections, find shop_ids
            if collection_name in ["products", "orders", "customers", "shops"]:
                # Find unique shop_ids
                if "shop_id" in sample:
                    shop_ids = await collection.distinct("shop_id")
                    print(f"   Shop IDs found: {shop_ids[:10]}")  # Show first 10
                elif collection_name == "shops" and "id" in sample:
                    # For shops collection, the id is the shop_id
                    shops = await collection.find({}, {"id": 1, "name": 1}).limit(10).to_list(10)
                    print(f"   Available shops:")
                    for shop in shops:
                        print(f"      - ID: {shop.get('id')}, Name: {shop.get('name')}")

        print()

    # Check specific shop data
    print("\n🔍 Checking data for specific shops:")

    # Try to find which shop has the most orders
    orders_collection = db["orders"]
    pipeline = [
        {"$group": {"_id": "$shop_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]

    shop_order_counts = await orders_collection.aggregate(pipeline).to_list(10)

    if shop_order_counts:
        print("\n📈 Top shops by order count:")
        for shop in shop_order_counts:
            shop_id = shop["_id"]
            count = shop["count"]
            print(f"   Shop ID {shop_id}: {count} orders")

            # Get more details about the top shop
            if shop == shop_order_counts[0]:
                print(f"\n   📊 Details for shop {shop_id}:")

                # Count products
                products_count = await db["products"].count_documents({"shop_id": shop_id})
                print(f"      Products: {products_count}")

                # Count customers
                customers_count = await db["customers"].count_documents({"shop_id": shop_id})
                print(f"      Customers: {customers_count}")

                # Sample order
                sample_order = await orders_collection.find_one({"shop_id": shop_id})
                if sample_order:
                    print(f"      Sample order fields: {list(sample_order.keys())}")

    print("\n✅ Use one of the shop IDs above in your queries!")
    print("   Example: shop_id = str(shop_id) if it's a number")

    # Close connection
    client.close()


if __name__ == "__main__":
    asyncio.run(check_data())