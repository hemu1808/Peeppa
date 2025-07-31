from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import logging
from datetime import datetime

from backend.database import MongoDB
from backend.scrapper import Scraper
from config import Config
from models import Product, ProductSpec, PriceAlert

# Configure logging
logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = Config.SECRET_KEY  # Add this to config.py

# Initialize services
try:
    db = MongoDB()
    scraper = Scraper()
except Exception as e:
    logger.error(f"Failed to initialize services: {str(e)}")
    raise

@app.route('/')
def index():
    # Get recent searches from database (last 5)
    recent_searches = db.get_recent_searches(limit=5)
    
    # Get currently tracked products
    tracked_products = db.get_tracked_products()
    
    # Get available retailers
    retailers = [
        {"id": retailer, "name": retailer, "checked": retailer in Config.DEFAULT_RETAILERS}
        for retailer in Config.DEFAULT_RETAILERS
    ]
    
    return render_template('index.html',
                         retailers=retailers,
                         recent_searches=recent_searches,
                         tracked_products=tracked_products,
                         query=request.args.get('query', ''))

@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        query = request.form.get('query')
        selected_retailers = request.form.getlist('retailers')
    else:
        query = request.args.get('query')
        selected_retailers = Config.DEFAULT_RETAILERS

    if not query:
        return redirect(url_for('index'))

    # Save search query to recent searches
    db.save_search_query(query)

    # Perform search
    products = scraper.search_products(query, selected_retailers)
    
    # Process and save products
    search_results = []
    for product in products:
        product_id = db.save_product(product)
        if product_id:
            db.log_price(product_id, product.price)
            
            # Get price history stats if product is being tracked
            price_stats = None
            if db.is_product_tracked(product_id):
                price_stats = db.get_price_stats(product_id)
            
            search_results.append({
                "id": product_id,
                "name": product.name,
                "price": product.price,
                "retailer": product.retailer,
                "specifications": {spec.key: spec.value for spec in product.specifications},
                "url": product.link,
                "image_url": product.image_url,
                "is_tracked": db.is_product_tracked(product_id),
                "price_stats": price_stats
            })
    
    # Sort results if requested
    sort = request.args.get('sort', 'price_asc')
    if sort == 'price_desc':
        search_results.sort(key=lambda x: x['price'], reverse=True)
    elif sort == 'price_asc':
        search_results.sort(key=lambda x: x['price'])
    elif sort == 'name_asc':
        search_results.sort(key=lambda x: x['name'])
    elif sort == 'name_desc':
        search_results.sort(key=lambda x: x['name'], reverse=True)

    return render_template('results.html',
                         query=query,
                         results=search_results)

@app.route('/price-history/<product_id>')
def price_history(product_id):
    product = db.get_product(product_id)
    if not product:
        return redirect(url_for('index'))
    
    # Get price history data
    history_data = db.get_price_history(product_id)
    
    # Prepare data for the chart
    dates = [point.timestamp.strftime('%Y-%m-%d') for point in history_data]
    prices = [float(point.price) for point in history_data]
    
    # Calculate price statistics
    if prices:
        price_stats = {
            'highest': float(max(prices)),
            'lowest': float(min(prices)),
            'average': float(sum(prices) / len(prices))
        }
    else:
        price_stats = {'highest': 0.0, 'lowest': 0.0, 'average': 0.0}
    
    # Calculate price changes and ensure all numeric values are float
    price_history = []
    for i, point in enumerate(history_data):
        change = 0.0
        if i > 0:
            change = float(point.price - history_data[i-1].price)
        price_history.append({
            'date': point.timestamp,
            'price': float(point.price),
            'change': change
        })
        
    # Ensure product price is float
    if product and 'current_price' in product:
        product['current_price'] = float(product['current_price'])

    return render_template('price_history.html',
                         product=product,
                         price_history=price_history,
                         price_stats=price_stats,
                         dates=dates,
                         prices=prices)

@app.route('/track-product', methods=['POST'])
def track_product():
    data = request.get_json()
    product_id = data.get('product_id')
    
    if not product_id:
        return jsonify({'success': False, 'error': 'Product ID is required'}), 400
    
    success = db.toggle_product_tracking(product_id)
    return jsonify({'success': success})

@app.route('/api/set-price-alert', methods=['POST'])
def set_price_alert():
    try:
        data = request.get_json()
        
        # Validate input
        if not all(key in data for key in ['productId', 'targetPrice', 'condition', 'email']):
            return jsonify({
                'success': False,
                'message': 'Missing required fields'
            }), 400
            
        # Create price alert
        alert = PriceAlert(
            product_id=data['productId'],
            target_price=float(data['targetPrice']),
            condition=data['condition'],
            email=data['email']
        )
        
        # Save alert to database
        alert_id = db.create_price_alert(alert)
        
        if alert_id:
            return jsonify({
                'success': True,
                'message': 'Price alert created successfully',
                'alert_id': alert_id
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to create price alert'
            }), 500
            
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error setting price alert: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring."""
    try:
        # Test database connection
        db.client.admin.command('ping')
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'database': 'disconnected',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/status')
def status():
    """Status page showing application information."""
    try:
        # Test database connection
        db.client.admin.command('ping')
        db_status = "Connected"
    except Exception as e:
        db_status = f"Disconnected: {str(e)}"
    
    return render_template('status.html',
                         db_status=db_status,
                         demo_mode=Config.ENABLE_DEMO_MODE,
                         retailers=Config.DEFAULT_RETAILERS,
                         timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

if __name__ == '__main__':
    try:
        app.run(debug=Config.DEBUG, host='0.0.0.0', port=Config.PORT)
    except KeyboardInterrupt:
        logger.info("Shutting down application...")
        try:
            db.close_connection()
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        try:
            db.close_connection()
        except Exception as shutdown_error:
            logger.error(f"Error during shutdown: {str(shutdown_error)}")