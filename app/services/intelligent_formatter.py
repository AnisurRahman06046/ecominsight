"""Intelligent answer formatter using Hugging Face models."""

import logging
from typing import Any, List, Dict, Optional
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
import torch

logger = logging.getLogger(__name__)


class IntelligentFormatter:
    """AI-powered answer formatter that creates human-readable responses."""

    def __init__(self):
        self.summarizer = None
        self.text_generator = None
        self.initialized = False

    async def initialize(self):
        """Initialize Hugging Face models."""
        try:
            logger.info("Loading Hugging Face models for intelligent formatting...")

            # Load text generation model (lightweight)
            self.text_generator = pipeline(
                "text2text-generation",
                model="facebook/bart-base",
                device=-1,  # Use CPU
                max_length=200,
                do_sample=True,
                temperature=0.7
            )

            self.initialized = True
            logger.info("Intelligent formatter initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize intelligent formatter: {e}")
            self.initialized = False

    def format_orders_response(self, data: List[Dict], question: str) -> str:
        """Format order data into human-readable response."""
        if not data:
            return "No orders found matching your criteria."

        if len(data) == 1:
            order = data[0]
            return self._format_single_order(order)

        elif len(data) <= 5:
            # Show summary for small results
            return self._format_order_summary(data, question)

        else:
            # Show aggregate info for large results
            return self._format_order_aggregate(data, question)

    def _format_single_order(self, order: Dict) -> str:
        """Format a single order."""
        order_num = order.get('order_number', order.get('id', 'N/A'))
        total = order.get('grand_total', order.get('total_amount', 0))
        customer = order.get('shipping_name', order.get('customer_name', 'Unknown'))
        status = order.get('status', 'Unknown')

        return f"Order #{order_num}: ${total:.2f} from {customer}, Status: {status}"

    def _format_order_summary(self, data: List[Dict], question: str) -> str:
        """Format multiple orders into a concise summary."""
        order_summaries = []

        for order in data:
            order_num = order.get('order_number', order.get('id', 'N/A'))
            total = order.get('grand_total', order.get('total_amount', 0))
            customer = order.get('shipping_name', order.get('customer_name', 'Unknown'))

            # Keep customer name short
            customer_short = customer.split()[0] if customer else 'Unknown'

            order_summaries.append(f"#{order_num} (${total:.0f} - {customer_short})")

        orders_text = ", ".join(order_summaries)

        if "first" in question.lower() or "recent" in question.lower():
            return f"Here are your {len(data)} most recent orders: {orders_text}"
        else:
            return f"Found {len(data)} orders: {orders_text}"

    def _format_order_aggregate(self, data: List[Dict], question: str) -> str:
        """Format large order datasets with aggregate information."""
        total_orders = len(data)

        # Calculate aggregates
        total_value = sum(order.get('grand_total', order.get('total_amount', 0)) for order in data)
        avg_value = total_value / total_orders if total_orders > 0 else 0

        # Count by status
        status_counts = {}
        for order in data:
            status = order.get('status', 'Unknown')
            status_counts[status] = status_counts.get(status, 0) + 1

        # Find top status
        top_status = max(status_counts, key=status_counts.get) if status_counts else 'Unknown'

        return (f"Found {total_orders} orders with total value ${total_value:,.2f} "
                f"(avg ${avg_value:.2f}). Most common status: {top_status} "
                f"({status_counts.get(top_status, 0)} orders)")

    def format_products_response(self, data: List[Dict], question: str) -> str:
        """Format product data into human-readable response."""
        if not data:
            return "No products found matching your criteria."

        if len(data) == 1:
            product = data[0]
            return self._format_single_product(product)

        elif len(data) <= 10:
            return self._format_product_summary(data, question)

        else:
            return self._format_product_aggregate(data, question)

    def _format_single_product(self, product: Dict) -> str:
        """Format a single product."""
        name = product.get('name', 'Unknown Product')
        price = product.get('price', 0)
        stock = product.get('stock_quantity', 0)
        status = product.get('status', 'Unknown')

        return f"Product: {name}, Price: ${price}, Stock: {stock}, Status: {status}"

    def _format_product_summary(self, data: List[Dict], question: str) -> str:
        """Format multiple products into a summary."""
        product_summaries = []

        for product in data[:5]:  # Show first 5
            name = product.get('name', 'Unknown')
            price = product.get('price', 0)

            # Shorten long product names
            name_short = name[:30] + "..." if len(name) > 30 else name
            product_summaries.append(f"{name_short} (${price})")

        products_text = ", ".join(product_summaries)

        if len(data) > 5:
            return f"Showing 5 of {len(data)} products: {products_text}"
        else:
            return f"Found {len(data)} products: {products_text}"

    def _format_product_aggregate(self, data: List[Dict], question: str) -> str:
        """Format large product datasets."""
        total_products = len(data)

        # Calculate price stats
        prices = [p.get('price', 0) for p in data if p.get('price')]
        avg_price = sum(prices) / len(prices) if prices else 0
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0

        # Count by status
        active_count = sum(1 for p in data if p.get('status') == 'active')

        return (f"Found {total_products} products. {active_count} active. "
                f"Price range: ${min_price:.2f} - ${max_price:.2f} "
                f"(avg ${avg_price:.2f})")

    def format_customers_response(self, data: List[Dict], question: str) -> str:
        """Format customer data into human-readable response."""
        if not data:
            return "No customers found matching your criteria."

        if len(data) == 1:
            customer = data[0]
            return self._format_single_customer(customer)

        elif len(data) <= 8:
            return self._format_customer_summary(data)

        else:
            return self._format_customer_aggregate(data)

    def _format_single_customer(self, customer: Dict) -> str:
        """Format a single customer."""
        name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
        email = customer.get('email', 'No email')
        phone = customer.get('phone', 'No phone')

        return f"Customer: {name}, Email: {email}, Phone: {phone}"

    def _format_customer_summary(self, data: List[Dict]) -> str:
        """Format multiple customers."""
        customer_names = []

        for customer in data:
            name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
            if not name:
                name = customer.get('email', 'Unknown').split('@')[0]

            customer_names.append(name)

        names_text = ", ".join(customer_names)
        return f"Found {len(data)} customers: {names_text}"

    def _format_customer_aggregate(self, data: List[Dict]) -> str:
        """Format large customer datasets."""
        total = len(data)

        # Count by city/location
        cities = {}
        for customer in data:
            city = customer.get('shipping_city', customer.get('city', 'Unknown'))
            cities[city] = cities.get(city, 0) + 1

        top_city = max(cities, key=cities.get) if cities else 'Unknown'

        return f"Found {total} customers. Top location: {top_city} ({cities.get(top_city, 0)} customers)"

    def format_generic_response(self, data: Any, question: str) -> str:
        """Format any other type of data intelligently."""
        if not data:
            return "No results found for your query."

        # Handle count results
        if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
            single_result = data[0]
            if 'count' in single_result or 'total' in single_result:
                count = single_result.get('count', single_result.get('total', 0))
                return f"Result: {count}"

        # Handle list of results
        if isinstance(data, list):
            return f"Found {len(data)} results matching your criteria."

        # Handle single values
        if isinstance(data, (int, float)):
            return f"Result: {data}"

        return f"Query completed. Found data: {str(data)[:100]}..."

    def format_response(self, data: Any, question: str, query_type: str = "unknown") -> str:
        """Main formatting function that determines the best format."""
        try:
            if not data:
                return "No results found for your query."

            # Determine data type from content
            if isinstance(data, list) and data and isinstance(data[0], dict):
                sample = data[0]

                # Check if it's order data
                if any(field in sample for field in ['order_number', 'grand_total', 'shipping_name']):
                    return self.format_orders_response(data, question)

                # Check if it's product data
                elif any(field in sample for field in ['name', 'price', 'stock_quantity']):
                    return self.format_products_response(data, question)

                # Check if it's customer data
                elif any(field in sample for field in ['first_name', 'last_name', 'email']):
                    return self.format_customers_response(data, question)

            # Fallback to generic formatting
            return self.format_generic_response(data, question)

        except Exception as e:
            logger.error(f"Formatting error: {e}")
            return self.format_generic_response(data, question)


# Global instance
intelligent_formatter = IntelligentFormatter()