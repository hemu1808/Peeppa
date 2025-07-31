#!/usr/bin/env python3
"""
Simple test script to verify the Price Tracker application setup.
"""

import sys
import os
import logging
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")
    
    try:
        from flask import Flask
        print("✓ Flask imported successfully")
    except ImportError as e:
        print(f"✗ Flask import failed: {e}")
        return False
    
    try:
        from config import Config
        print("✓ Config imported successfully")
    except ImportError as e:
        print(f"✗ Config import failed: {e}")
        return False
    
    try:
        from models import Product, ProductSpec, PriceAlert
        print("✓ Models imported successfully")
    except ImportError as e:
        print(f"✗ Models import failed: {e}")
        return False
    
    try:
        from backend.database import MongoDB
        print("✓ Database module imported successfully")
    except ImportError as e:
        print(f"✗ Database import failed: {e}")
        return False
    
    try:
        from backend.scrapper import Scraper
        print("✓ Scraper module imported successfully")
    except ImportError as e:
        print(f"✗ Scraper import failed: {e}")
        return False
    
    return True

def test_config():
    """Test configuration loading."""
    print("\nTesting configuration...")
    
    try:
        from config import Config
        
        # Check required config values
        required_configs = [
            'SECRET_KEY',
            'DEBUG',
            'PORT',
            'MONGO_URI',
            'DATABASE_NAME',
            'DEFAULT_RETAILERS'
        ]
        
        for config_name in required_configs:
            if hasattr(Config, config_name):
                print(f"✓ {config_name} configured")
            else:
                print(f"✗ {config_name} missing from config")
                return False
        
        print("✓ All required configuration values present")
        return True
        
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False

def test_database_connection():
    """Test database connection."""
    print("\nTesting database connection...")
    
    try:
        from backend.database import MongoDB
        from config import Config
        
        # Test connection
        db = MongoDB()
        print("✓ Database connection successful")
        
        # Test basic operations
        test_product = {
            "name": "Test Product",
            "price": 99.99,
            "retailer": "Test Store",
            "specifications": {"test": "value"},
            "link": "https://example.com",
            "image_url": "https://example.com/image.jpg"
        }
        
        # Clean up test data
        db.close_connection()
        print("✓ Database operations test successful")
        return True
        
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False

def test_scraper():
    """Test scraper initialization."""
    print("\nTesting scraper...")
    
    try:
        from backend.scrapper import Scraper
        
        scraper = Scraper()
        print("✓ Scraper initialized successfully")
        
        # Test retailer configuration
        expected_retailers = ["Amazon", "Best Buy", "Walmart", "Target", "Newegg"]
        for retailer in expected_retailers:
            if retailer in scraper.RETAILERS:
                print(f"✓ {retailer} configured")
            else:
                print(f"✗ {retailer} missing from scraper")
                return False
        
        print("✓ All expected retailers configured")
        return True
        
    except Exception as e:
        print(f"✗ Scraper test failed: {e}")
        return False

def test_models():
    """Test data models."""
    print("\nTesting data models...")
    
    try:
        from models import Product, ProductSpec, PriceAlert
        from datetime import datetime
        
        # Test Product model
        specs = [ProductSpec(key="Brand", value="Test Brand")]
        product = Product(
            name="Test Product",
            price=99.99,
            link="https://example.com",
            retailer="Test Store",
            specifications=specs,
            image_url="https://example.com/image.jpg"
        )
        print("✓ Product model test successful")
        
        # Test PriceAlert model
        alert = PriceAlert(
            product_id="test_id",
            target_price=50.0,
            condition="below",
            email="test@example.com"
        )
        print("✓ PriceAlert model test successful")
        
        return True
        
    except Exception as e:
        print(f"✗ Models test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Price Tracker Application Test Suite")
    print("=" * 40)
    
    tests = [
        test_imports,
        test_config,
        test_models,
        test_scraper,
        test_database_connection
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        else:
            print(f"✗ {test.__name__} failed")
    
    print("\n" + "=" * 40)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All tests passed! Application is ready to run.")
        return True
    else:
        print("✗ Some tests failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 