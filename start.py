#!/usr/bin/env python3
"""
Startup script for the Price Tracker application.
Provides better error handling and application management.
"""

import os
import sys
import logging
import signal
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def check_environment():
    """Check if required environment variables are set."""
    logger.info("Checking environment...")
    
    # Check if .env file exists
    env_file = Path('.env')
    if not env_file.exists():
        logger.warning(".env file not found. Using default configuration.")
        logger.info("Please copy env.example to .env and configure your settings.")
    
    # Check required environment variables
    required_vars = ['SECRET_KEY']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.warning(f"Missing environment variables: {', '.join(missing_vars)}")
        logger.info("Using default values for missing variables.")
    
    return True

def check_dependencies():
    """Check if all required dependencies are installed."""
    logger.info("Checking dependencies...")
    
    required_packages = [
        'flask',
        'pymongo',
        'beautifulsoup4',
        'requests',
        'plotly',
        'pydantic',
        'python-dotenv',
        'pandas',
        'email-validator'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        logger.error(f"Missing packages: {', '.join(missing_packages)}")
        logger.info("Please run: pip install -r requirements.txt")
        return False
    
    logger.info("All dependencies are installed.")
    return True

def check_database():
    """Check database connectivity."""
    logger.info("Checking database connection...")
    
    try:
        from backend.database import MongoDB
        db = MongoDB()
        db.close_connection()
        logger.info("Database connection successful.")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        logger.info("Please ensure MongoDB is running.")
        return False

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}. Shutting down gracefully...")
    sys.exit(0)

def main():
    """Main startup function."""
    print("Price Tracker Application Startup")
    print("=" * 40)
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run checks
    checks = [
        ("Environment", check_environment),
        ("Dependencies", check_dependencies),
        ("Database", check_database)
    ]
    
    for check_name, check_func in checks:
        logger.info(f"Running {check_name} check...")
        if not check_func():
            logger.error(f"{check_name} check failed.")
            return False
        logger.info(f"{check_name} check passed.")
    
    # Start the application
    logger.info("Starting Flask application...")
    
    try:
        from app import app, db
        from config import Config
        
        logger.info(f"Application will be available at http://localhost:{Config.PORT}")
        logger.info("Press Ctrl+C to stop the application.")
        
        app.run(
            debug=Config.DEBUG,
            host='0.0.0.0',
            port=Config.PORT,
            use_reloader=False  # Disable reloader to avoid duplicate processes
        )
        
    except KeyboardInterrupt:
        logger.info("Application stopped by user.")
    except Exception as e:
        logger.error(f"Application error: {e}")
        return False
    finally:
        try:
            db.close_connection()
            logger.info("Database connection closed.")
        except Exception as e:
            logger.error(f"Error closing database connection: {e}")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 