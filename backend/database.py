import os
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import PyMongoError
from datetime import datetime
import logging
from typing import List, Dict, Optional, Union, Any
from bson import ObjectId

from config import Config
from models import Product, PriceHistoryPoint, ProductSpec, PriceAlert

logger = logging.getLogger(__name__)

class MongoDB:
    def __init__(self):
        try:
            self.client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=5000)
            # Test connection
            self.client.admin.command('ping')
            logger.info("Successfully connected to MongoDB")
        except PyMongoError as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise ConnectionError(f"Could not connect to MongoDB: {str(e)}")
        
        self.db = self.client[Config.DATABASE_NAME]
        self.products = self.db[Config.PRODUCTS_COLLECTION]
        self.price_history = self.db[Config.PRICE_HISTORY_COLLECTION]
        self.searches = self.db[Config.SEARCHES_COLLECTION]
        self.tracked_products = self.db[Config.TRACKED_PRODUCTS_COLLECTION]
        self.price_alerts = self.db['price_alerts']  # New collection for price alerts
        self._price_stats_cache: Dict[str, Dict[str, float]] = {}  # Cache for price stats
        
        # Create indexes
        try:
            self.products.create_index([("name", "text")])
            self.products.create_index([("retailer", ASCENDING)])
            self.price_history.create_index([("product_id", ASCENDING)])
            self.searches.create_index([("timestamp", DESCENDING)])
            self.tracked_products.create_index([("product_id", ASCENDING)], unique=True)
            logger.info("Database indexes created successfully")
        except PyMongoError as e:
            logger.error(f"Failed to create database indexes: {str(e)}")
            raise

    def save_product(self, product: Product) -> Optional[str]:
        try:
            # Convert specifications to dictionary
            product_data = product.dict()
            product_data["specifications"] = {
                spec.key: spec.value for spec in product.specifications
            }
            
            # Upsert product
            result = self.products.update_one(
                {"name": product.name, "retailer": product.retailer},
                {"$set": product_data},
                upsert=True
            )
            
            # Get product ID
            if result.upserted_id:
                return str(result.upserted_id)
            else:
                found_product = self.products.find_one(
                    {"name": product.name, "retailer": product.retailer}
                )
                if found_product:
                    return str(found_product["_id"])
                return None
                
        except PyMongoError as e:
            logger.error(f"Error saving product: {str(e)}")
            return None

    def log_price(self, product_id: str, price: float):
        try:
            price_point = PriceHistoryPoint(
                product_id=product_id,
                price=price
            )
            self.price_history.insert_one(price_point.dict())
            
            # Invalidate price stats cache for this product
            if product_id in self._price_stats_cache:
                del self._price_stats_cache[product_id]
                
        except PyMongoError as e:
            logger.error(f"Error logging price: {str(e)}")

    def get_products_by_name(self, product_name: str) -> list:
        try:
            products = self.products.find(
                {"$text": {"$search": product_name}},
                {"score": {"$meta": "textScore"}}
            ).sort([("score", {"$meta": "textScore"})]).limit(20)
            
            return [
                {
                    "id": str(p["_id"]),
                    "name": p["name"],
                    "price": p["price"],
                    "retailer": p["retailer"],
                    "specifications": p["specifications"],
                    "link": p["link"],
                    "image_url": p.get("image_url")
                } 
                for p in products
            ]
        except PyMongoError as e:
            logger.error(f"Error fetching products: {str(e)}")
            return []

    def get_price_history(self, product_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[PriceHistoryPoint]:
        try:
            # Build query with type-safe dictionary
            query: Dict[str, Any] = {"product_id": product_id}
            
            # Add date range filters if provided
            if start_date or end_date:
                date_range: Dict[str, datetime] = {}
                if start_date:
                    date_range["$gte"] = start_date
                if end_date:
                    date_range["$lte"] = end_date
                query["timestamp"] = date_range
            
            history = list(self.price_history.find(query).sort("timestamp", ASCENDING))
            return [PriceHistoryPoint(**p) for p in history]
        except PyMongoError as e:
            logger.error(f"Error fetching price history: {str(e)}")
            return []

    def get_product(self, product_id: str) -> Optional[Dict]:
        try:
            product = self.products.find_one({"_id": ObjectId(product_id)})
            if product:
                product['id'] = str(product['_id'])
                return product
            return None
        except PyMongoError as e:
            logger.error(f"Error fetching product: {str(e)}")
            return None

    def get_price_stats(self, product_id: str) -> Dict[str, float]:
        try:
            # Check cache first
            if product_id in self._price_stats_cache:
                return self._price_stats_cache[product_id]
            
            # Calculate stats from database
            pipeline = [
                {"$match": {"product_id": product_id}},
                {
                    "$group": {
                        "_id": None,
                        "highest": {"$max": "$price"},
                        "lowest": {"$min": "$price"},
                        "average": {"$avg": "$price"}
                    }
                }
            ]
            stats = list(self.price_history.aggregate(pipeline))
            
            if stats:
                stats = stats[0]
                result = {
                    "highest": float(stats["highest"]),
                    "lowest": float(stats["lowest"]),
                    "average": float(stats["average"])
                }
                # Cache the results
                self._price_stats_cache[product_id] = result
                return result
                
            default_stats = {"highest": 0.0, "lowest": 0.0, "average": 0.0}
            self._price_stats_cache[product_id] = default_stats
            return default_stats
            
        except PyMongoError as e:
            logger.error(f"Error calculating price stats: {str(e)}")
            return {"highest": 0.0, "lowest": 0.0, "average": 0.0}

    def save_search_query(self, query: str) -> None:
        try:
            self.searches.insert_one({
                "query": query,
                "timestamp": datetime.now()
            })
        except PyMongoError as e:
            logger.error(f"Error saving search query: {str(e)}")

    def get_recent_searches(self, limit: int = 5) -> List[Dict]:
        try:
            searches = self.searches.find().sort("timestamp", DESCENDING).limit(limit)
            return list(searches)
        except PyMongoError as e:
            logger.error(f"Error fetching recent searches: {str(e)}")
            return []

    def toggle_product_tracking(self, product_id: str) -> bool:
        try:
            # Check if product is already being tracked
            existing = self.tracked_products.find_one({"product_id": product_id})
            
            if existing:
                # Untrack the product
                self.tracked_products.delete_one({"product_id": product_id})
            else:
                # Track the product
                self.tracked_products.insert_one({
                    "product_id": product_id,
                    "timestamp": datetime.now()
                })
            return True
        except PyMongoError as e:
            logger.error(f"Error toggling product tracking: {str(e)}")
            return False

    def is_product_tracked(self, product_id: str) -> bool:
        try:
            return bool(self.tracked_products.find_one({"product_id": product_id}))
        except PyMongoError as e:
            logger.error(f"Error checking product tracking status: {str(e)}")
            return False

    def get_tracked_products(self) -> List[Dict]:
        try:
            # Get list of tracked product IDs
            tracked = self.tracked_products.find().sort("timestamp", DESCENDING)
            tracked_ids = [t["product_id"] for t in tracked]
            
            if not tracked_ids:
                return []
            
            # Get product details for tracked products
            products = self.products.find({"_id": {"$in": [ObjectId(pid) for pid in tracked_ids]}})
            
            tracked_products = []
            for product in products:
                product_id = str(product["_id"])
                
                # Get latest price and previous price for change calculation
                latest_prices = list(self.price_history.find(
                    {"product_id": product_id}
                ).sort("timestamp", DESCENDING).limit(2))
                
                current_price = latest_prices[0]["price"] if latest_prices else product["price"]
                price_change = 0
                if len(latest_prices) > 1:
                    price_change = current_price - latest_prices[1]["price"]
                
                tracked_products.append({
                    "id": product_id,
                    "name": product["name"],
                    "current_price": current_price,
                    "price_change": price_change,
                    "retailer": product["retailer"],
                    "image_url": product.get("image_url"),
                    "url": product["link"]
                })
            
            return tracked_products
            
        except PyMongoError as e:
            logger.error(f"Error fetching tracked products: {str(e)}")
            return []

    def create_price_alert(self, alert: PriceAlert) -> Optional[str]:
        """Create a new price alert."""
        try:
            # Check if product exists
            if not self.products.find_one({"_id": ObjectId(alert.product_id)}):
                raise ValueError("Product not found")

            # Check for existing active alert for the same product and email
            existing = self.price_alerts.find_one({
                "product_id": alert.product_id,
                "email": alert.email,
                "is_active": True
            })

            if existing:
                # Update existing alert
                self.price_alerts.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {
                        "target_price": alert.target_price,
                        "condition": alert.condition,
                        "last_checked": None
                    }}
                )
                return str(existing["_id"])
            else:
                # Create new alert
                result = self.price_alerts.insert_one(alert.dict())
                return str(result.inserted_id)

        except PyMongoError as e:
            logger.error(f"Error creating price alert: {str(e)}")
            return None

    def get_active_price_alerts(self, product_id: Optional[str] = None) -> List[PriceAlert]:
        """Get all active price alerts, optionally filtered by product."""
        try:
            query: Dict[str, Any] = {"is_active": True}
            if product_id:
                query["product_id"] = product_id

            alerts = list(self.price_alerts.find(query))
            return [PriceAlert(**alert) for alert in alerts]

        except PyMongoError as e:
            logger.error(f"Error fetching price alerts: {str(e)}")
            return []

    def deactivate_price_alert(self, alert_id: str) -> bool:
        """Deactivate a price alert."""
        try:
            result = self.price_alerts.update_one(
                {"_id": ObjectId(alert_id)},
                {"$set": {"is_active": False}}
            )
            return result.modified_count > 0

        except PyMongoError as e:
            logger.error(f"Error deactivating price alert: {str(e)}")
            return False
    
    def close_connection(self):
        """Close the MongoDB connection."""
        try:
            self.client.close()
            logger.info("MongoDB connection closed successfully")
        except Exception as e:
            logger.error(f"Error closing MongoDB connection: {str(e)}")