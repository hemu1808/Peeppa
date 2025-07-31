import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # Flask configuration
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
    PORT = int(os.getenv("PORT", "5000"))
    
    # MongoDB configuration
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DATABASE_NAME = "price_comparison"
    PRODUCTS_COLLECTION = "products"
    PRICE_HISTORY_COLLECTION = "price_history"
    SEARCHES_COLLECTION = "searches"
    TRACKED_PRODUCTS_COLLECTION = "tracked_products"
    
    # Scraper configuration
    SCRAPE_TIMEOUT = 30  # Increased timeout for slower sites
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ENABLE_DEMO_MODE = os.getenv("ENABLE_DEMO_MODE", "True").lower() == "true"  # Enable demo data when scraping fails
    
    # UI defaults
    DEFAULT_PRODUCT = "iphone"
    DEFAULT_RETAILERS = ["Amazon", "Best Buy", "Walmart", "Target", "Newegg"]
    
    # Email Configuration
    SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
    SMTP_USERNAME = os.getenv('SMTP_USERNAME', '')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
    SMTP_FROM_EMAIL = os.getenv('SMTP_FROM_EMAIL', 'price.tracker@example.com')
    SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', 'True').lower() == 'true'

    # Price Alert Settings
    ALERT_CHECK_INTERVAL = int(os.getenv('ALERT_CHECK_INTERVAL', '3600'))  # In seconds
    ALERT_THRESHOLD_PERCENT = float(os.getenv('ALERT_THRESHOLD_PERCENT', '0.5'))  # Percentage threshold for price changes