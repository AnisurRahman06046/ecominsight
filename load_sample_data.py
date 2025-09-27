#!/usr/bin/env python3
"""
Load sample e-commerce data into MongoDB for testing
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
import random
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("MONGODB_DATABASE", "ecommerce_insights")


async def load_sample_data():
    """Load sample e-commerce data."""
    print("🔄 Loading sample data into MongoDB...")

    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]

    # Clear existing data (optional)
    print("🗑️  Clearing existing data...")
    for collection in ["products", "customers", "orders", "order_items", "inventory", "returns"]:
        await db[collection].delete_many({})

    # Sample shop IDs
    shop_ids = ["123", "456", "789"]

    # 1. Load Products
    print("📦 Loading products...")
    categories = ["Electronics", "Clothing", "Books", "Home & Garden", "Sports"]
    products = []

    for shop_id in shop_ids:
        for i in range(1, 51):  # 50 products per shop
            products.append({
                "_id": f"{shop_id}_prod_{i}",
                "shop_id": shop_id,
                "name": f"Product {i}",
                "category": random.choice(categories),
                "price": round(random.uniform(10, 500), 2),
                "stock_quantity": random.randint(0, 100),
                "status": "active" if random.random() > 0.1 else "inactive",
                "created_at": datetime.utcnow() - timedelta(days=random.randint(0, 365))
            })

    await db.products.insert_many(products)
    print(f"   ✅ Loaded {len(products)} products")

    # 2. Load Customers
    print("👥 Loading customers...")
    customers = []

    for shop_id in shop_ids:
        for i in range(1, 101):  # 100 customers per shop
            orders_count = random.randint(1, 20)
            customers.append({
                "_id": f"{shop_id}_cust_{i}",
                "shop_id": shop_id,
                "name": f"Customer {i}",
                "email": f"customer{i}@example.com",
                "total_spent": round(random.uniform(100, 5000), 2),
                "order_count": orders_count,
                "created_at": datetime.utcnow() - timedelta(days=random.randint(0, 730))
            })

    await db.customers.insert_many(customers)
    print(f"   ✅ Loaded {len(customers)} customers")

    # 3. Load Orders and Order Items
    print("🛒 Loading orders...")
    orders = []
    order_items = []
    order_id = 1

    for shop_id in shop_ids:
        # Generate orders for last 90 days
        for day in range(90):
            order_date = datetime.utcnow() - timedelta(days=day)

            # Random number of orders per day
            daily_orders = random.randint(5, 20)

            for _ in range(daily_orders):
                customer = random.choice([c for c in customers if c["shop_id"] == shop_id])
                shop_products = [p for p in products if p["shop_id"] == shop_id]

                # Create order
                order_total = 0
                order_doc = {
                    "_id": f"{shop_id}_order_{order_id}",
                    "shop_id": shop_id,
                    "customer_id": customer["_id"],
                    "customer_name": customer["name"],
                    "status": random.choice(["completed", "processing", "pending"]),
                    "created_at": order_date,
                    "items": []
                }

                # Add items to order
                num_items = random.randint(1, 5)
                for _ in range(num_items):
                    product = random.choice(shop_products)
                    quantity = random.randint(1, 3)
                    item_total = product["price"] * quantity
                    order_total += item_total

                    item = {
                        "_id": f"{shop_id}_order_{order_id}_item_{_}",
                        "shop_id": shop_id,
                        "order_id": f"{shop_id}_order_{order_id}",
                        "product_id": product["_id"],
                        "product_name": product["name"],
                        "quantity": quantity,
                        "price": product["price"]
                    }
                    order_items.append(item)
                    order_doc["items"].append(item["_id"])

                order_doc["total_amount"] = round(order_total, 2)
                orders.append(order_doc)
                order_id += 1

    await db.orders.insert_many(orders)
    await db.order_items.insert_many(order_items)
    print(f"   ✅ Loaded {len(orders)} orders with {len(order_items)} items")

    # 4. Load Inventory
    print("📊 Loading inventory...")
    inventory = []

    for product in products:
        inventory.append({
            "_id": f"{product['_id']}_inv",
            "shop_id": product["shop_id"],
            "product_id": product["_id"],
            "product_name": product["name"],
            "sku": f"SKU-{product['_id']}",
            "stock_quantity": product["stock_quantity"],
            "reorder_point": random.randint(5, 20)
        })

    await db.inventory.insert_many(inventory)
    print(f"   ✅ Loaded {len(inventory)} inventory records")

    # 5. Load Returns (small percentage of orders)
    print("🔄 Loading returns...")
    returns = []
    return_orders = random.sample(orders, k=min(50, len(orders) // 10))  # 10% return rate

    for order in return_orders:
        returns.append({
            "_id": f"{order['_id']}_return",
            "shop_id": order["shop_id"],
            "order_id": order["_id"],
            "product_id": random.choice(order["items"]),
            "reason": random.choice(["Defective", "Wrong item", "Not as described", "Changed mind"]),
            "refund_amount": round(order["total_amount"] * random.uniform(0.3, 1.0), 2),
            "created_at": order["created_at"] + timedelta(days=random.randint(1, 7))
        })

    if returns:
        await db.returns.insert_many(returns)
    print(f"   ✅ Loaded {len(returns)} returns")

    # Print summary
    print("\n📊 Sample Data Summary:")
    print(f"   • Shops: {len(shop_ids)}")
    print(f"   • Products: {len(products)}")
    print(f"   • Customers: {len(customers)}")
    print(f"   • Orders: {len(orders)}")
    print(f"   • Order Items: {len(order_items)}")
    print(f"   • Inventory: {len(inventory)}")
    print(f"   • Returns: {len(returns)}")

    print(f"\n✅ Sample data loaded successfully!")
    print(f"   You can now test with shop_ids: {', '.join(shop_ids)}")

    # Close connection
    client.close()


if __name__ == "__main__":
    asyncio.run(load_sample_data())