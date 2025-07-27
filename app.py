import streamlit as st
import asyncio
import aiohttp
import pandas as pd
import logging
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import re
import sqlite3
import hashlib
import os
from typing import List, Dict

# --- Page and Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Price Peepa Pro - Shopping Intelligence",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS for Enhanced Styling ---
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 2rem 0;
        background: linear-gradient(90deg, #4b6cb7 0%, #182848 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .price-tag {
        font-size: 1.5rem;
        font-weight: bold;
        color: #2e7d32;
    }
    .deal-badge {
        background: linear-gradient(90deg, #ff5e62 0%, #ff9966 100%);
        color: white;
        padding: 0.3rem 1rem;
        border-radius: 20px;
        font-size: 0.9rem;
        font-weight: bold;
    }
    .stButton>button {
        width: 100%;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    .product-card {
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 8px rgba(0,0,0,0.08);
        transition: all 0.3s ease;
        border: 1px solid #e0e0e0;
    }
    .product-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.15);
    }
    .comparison-table {
        border-collapse: collapse;
        width: 100%;
    }
    .comparison-table th {
        background: linear-gradient(90deg, #4b6cb7 0%, #182848 100%);
        color: white;
        padding: 12px 15px;
        text-align: left;
    }
    .comparison-table tr:nth-child(even) {
        background-color: #f8f9fa;
    }
    .comparison-table tr:hover {
        background-color: #e9ecef;
    }
    .tab-container {
        margin-top: 2rem;
    }
    .price-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .price-table th {
        background-color: #4b6cb7;
        color: white;
        padding: 12px 15px;
        text-align: left;
        position: sticky;
        top: 0;
    }
    .price-table td {
        padding: 10px 15px;
        border-bottom: 1px solid #e0e0e0;
    }
    .price-table tr:nth-child(even) {
        background-color: #f8f9fa;
    }
    .price-table tr:hover {
        background-color: #e9f7ff;
    }
    .best-price {
        background-color: #e8f5e9 !important;
        font-weight: bold;
        color: #2e7d32;
    }
    .retailer-cell {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .table-badge {
        background: #ff5722;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
    }
    .stDataFrame {
        width: 100%;
    }
    .stTable {
        width: 100%;
    }
    .table-container {
        max-height: 500px;
        overflow-y: auto;
        margin-top: 20px;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- Database Management with Schema Migration ---
class DatabaseManager:
    DB_VERSION = 2
    
    def __init__(self, db_file="price_data_v2.db"):
        self.db_file = db_file
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._migrate_database()
        
    def _migrate_database(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS db_version (
                version INTEGER PRIMARY KEY
            )
        """)
        
        self.cursor.execute("SELECT version FROM db_version ORDER BY version DESC LIMIT 1")
        result = self.cursor.fetchone()
        current_version = result[0] if result else 0
        
        if current_version < self.DB_VERSION:
            logger.info(f"Migrating database from version {current_version} to {self.DB_VERSION}")
            
            if current_version < 1:
                self._create_table_v1()
                self.cursor.execute("INSERT INTO db_version (version) VALUES (1)")
                self.conn.commit()
                logger.info("Database migrated to version 1")
            
            if current_version < 2:
                self._create_table_v2()
                self.cursor.execute("INSERT OR REPLACE INTO db_version (version) VALUES (2)")
                self.conn.commit()
                logger.info("Database migrated to version 2")
    
    def _create_table_v1(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY,
                product_url TEXT NOT NULL,
                product_name TEXT,
                price REAL NOT NULL,
                retailer TEXT,
                timestamp DATETIME NOT NULL
            )
        """)
    
    def _create_table_v2(self):
        try:
            self.cursor.execute("ALTER TABLE price_history ADD COLUMN product_id TEXT")
            self.cursor.execute("ALTER TABLE price_history ADD COLUMN rating REAL")
            self.cursor.execute("ALTER TABLE price_history ADD COLUMN review_count INTEGER")
            self.cursor.execute("ALTER TABLE price_history ADD COLUMN shipping_info TEXT")
        except sqlite3.OperationalError:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY,
                    product_id TEXT NOT NULL,
                    product_url TEXT NOT NULL,
                    product_name TEXT,
                    price REAL NOT NULL,
                    retailer TEXT,
                    rating REAL,
                    review_count INTEGER,
                    shipping_info TEXT,
                    timestamp DATETIME NOT NULL
                )
            """)
        
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_id ON price_history (product_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON price_history (timestamp)")
    
    def generate_product_id(self, product_name: str, retailer: str) -> str:
        base_str = f"{product_name}_{retailer}".encode('utf-8')
        return hashlib.md5(base_str).hexdigest()
    
    def log_prices(self, products: List[Dict]):
        if not products:
            return
            
        insert_query = """
        INSERT OR IGNORE INTO price_history 
        (product_id, product_url, product_name, price, retailer, rating, review_count, shipping_info, timestamp) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        records = []
        for p in products:
            if p.get('url'):
                product_id = self.generate_product_id(p['name'], p['retailer'])
                records.append((
                    product_id,
                    p['url'],
                    p['name'],
                    p['price'],
                    p['retailer'],
                    p.get('rating'),
                    p.get('review_count'),
                    p.get('shipping_info'),
                    p['timestamp']
                ))
                
        if records:
            self.cursor.executemany(insert_query, records)
            self.conn.commit()
            logger.info(f"Logged {len(records)} price points to database")

    @st.cache_data(ttl=3600)
    def get_price_history(_self, product_id: str) -> pd.DataFrame:
        query = """
        SELECT timestamp, price, retailer 
        FROM price_history 
        WHERE product_id = ? 
        ORDER BY timestamp ASC
        """
        df = pd.read_sql_query(query, _self.conn, params=(product_id,))
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    
    @st.cache_data(ttl=3600)
    def get_comparison_data(_self, product_name: str) -> pd.DataFrame:
        """Get comparison data for similar products across retailers"""
        query = """
        SELECT 
            product_name, 
            retailer, 
            AVG(price) as avg_price,
            MIN(price) as min_price,
            MAX(price) as max_price,
            COUNT(*) as price_points,
            AVG(rating) as avg_rating,
            AVG(review_count) as avg_reviews
        FROM price_history
        WHERE LOWER(product_name) LIKE ?
        GROUP BY retailer, product_name
        ORDER BY avg_price ASC
        """
        search_term = f"%{product_name.lower()}%"
        return pd.read_sql_query(query, _self.conn, params=(search_term,))

# --- Enhanced API Integration ---
class ZenserpAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://app.zenserp.com/api/v2/search"
    
    async def search_products(self, query: str, session: aiohttp.ClientSession, country: str = "US") -> List[Dict]:
        headers = {"apikey": self.api_key}
        params = {
            'q': query,
            'tbm': 'shop',
            'location': self.get_location_for_country(country),
            'num': '20'
        }
        
        try:
            async with session.get(self.base_url, headers=headers, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_zenserp_results(data)
                else:
                    error_text = await response.text()
                    logger.error(f"Zenserp API error: {response.status} - {error_text}")
                    st.error(f"⚠️ API Error: {response.status}. Check your API key or plan limits.")
                    return []
        except asyncio.TimeoutError:
            logger.warning("Zenserp API request timed out")
            st.warning("⌛ Request timed out. Please try again later.")
            return []
        except Exception as e:
            logger.exception(f"Zenserp API request error: {e}")
            st.error(f"🚨 Unexpected API error: {str(e)}")
            return []
    
    def _parse_zenserp_results(self, data: Dict) -> List[Dict]:
        products = []
        
        for item in data.get('shopping_results', []):
            try:
                price_str = item.get('price', '').replace('$', '').replace(',', '').strip()
                if not price_str or not price_str.replace('.', '').isdigit():
                    continue
                    
                price = float(price_str)
                
                rating = None
                review_count = None
                if 'rating' in item and item['rating']:
                    rating_match = re.search(r'(\d+\.\d+)', str(item['rating']))
                    if rating_match:
                        rating = float(rating_match.group(1))
                
                if 'reviews' in item and item['reviews']:
                    review_match = re.search(r'(\d+)', str(item['reviews']).replace(',', ''))
                    if review_match:
                        review_count = int(review_match.group(1))
                
                shipping_info = ""
                if 'delivery' in item:
                    shipping_info = item['delivery']
                
                product = {
                    'name': item.get('title', 'No Title'),
                    'price': price,
                    'url': item.get('link', ''),
                    'retailer': item.get('source', 'Unknown Retailer'),
                    'image_url': item.get('thumbnail', ''),
                    'snippet': item.get('snippet', ''),
                    'rating': rating,
                    'review_count': review_count,
                    'shipping_info': shipping_info,
                    'source': 'Zenserp',
                    'timestamp': datetime.now().isoformat()
                }
                products.append(product)
            except (ValueError, TypeError) as e:
                logger.warning(f"Parse error: {item.get('title')} - {e}")
                continue
                
        return products
    
    def get_location_for_country(self, country_code: str) -> str:
        location_map = {
            "US": "United States", "CA": "Canada", "UK": "United Kingdom",
            "AU": "Australia", "DE": "Germany", "FR": "France",
            "JP": "Japan", "IN": "India", "BR": "Brazil"
        }
        return location_map.get(country_code, "United States")

# --- Core Engine with Comparison Features ---
class PriceComparisonEngine:
    def __init__(self):
        self.api_client = self._initialize_api()
    
    def _initialize_api(self):
        try:
            zenserp_api_key = st.secrets["ZENSERP_API_KEY"]
            return ZenserpAPI(zenserp_api_key)
        except KeyError:
            st.error("🔑 ZENSERP_API_KEY not found in secrets. Please configure your secrets.toml file.")
            return None
        except Exception as e:
            logger.error(f"API initialization failed: {str(e)}")
            return None
    
    async def search_products_async(self, query: str, country: str) -> List[Dict]:
        if not self.api_client:
            return []
            
        async with aiohttp.ClientSession() as session:
            return await self.api_client.search_products(query, session, country)

# --- Cached Search with Enhanced Performance ---
@st.cache_data(ttl=1800, show_spinner=False)
def perform_search(query: str, country: str) -> List[Dict]:
    engine = PriceComparisonEngine()
    if not engine.api_client:
        return []
    
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(engine.search_products_async(query, country))

# --- UI Components ---
def render_header():
    st.markdown("""
    <div class="main-header">
        <h1>🔍 Price Peepa Pro</h1>
        <p>Advanced Shopping Intelligence & Price Comparison</p>
    </div>
    """, unsafe_allow_html=True)

def render_sidebar():
    st.sidebar.markdown("## ⚙️ Search Configuration")
    country = st.sidebar.selectbox("Country", ["US", "CA", "UK", "AU", "DE", "FR", "JP", "IN", "BR"], index=0)
    sort_by = st.sidebar.selectbox("Sort Results By", ["Price: Low to High", "Price: High to Low", "Rating: High to Low"])
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("## ℹ️ About")
    st.sidebar.info("Price Peepa Pro analyzes prices from multiple retailers to find you the best deals.")
    
    return country, sort_by

def render_product_card(product: Dict, index: int, db_manager: DatabaseManager):
    with st.container():
        col1, col2, col3 = st.columns([1, 4, 2])
        
        with col1:
            if product.get('image_url'):
                st.image(product['image_url'], use_column_width=True)
            else:
                st.markdown("<div style='height:120px; display:flex; align-items:center; justify-content:center; background:#f0f0f0; border-radius:8px;'>📦</div>", 
                           unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"**{product['name']}**")
            
            retailer_text = f"🏪 **{product['retailer']}**"
            if product.get('rating'):
                retailer_text += f" ⭐ {product['rating']}"
                if product.get('review_count'):
                    retailer_text += f" ({product['review_count']} reviews)"
            st.caption(retailer_text)
            
            if product.get('shipping_info'):
                st.caption(f"🚚 {product['shipping_info']}")
            
            if index == 0:
                st.markdown("<div class='deal-badge'>🏆 BEST DEAL</div>", unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"<div class='price-tag' style='text-align:right;'>${product['price']:.2f}</div>", 
                       unsafe_allow_html=True)
            
            btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 1])
            with btn_col1:
                st.link_button("Visit", product['url'], use_container_width=True)
            with btn_col2:
                if st.button("📈", key=f"chart_{index}", use_container_width=True, 
                           help="View price history"):
                    st.session_state.selected_product = product
            with btn_col3:
                if st.button("📊", key=f"compare_{index}", use_container_width=True, 
                           help="Compare across retailers"):
                    st.session_state.comparison_product = product['name']
        
        st.markdown("---")

def render_product_grid(products: List[Dict], sort_by: str, db_manager: DatabaseManager):
    if not products:
        st.warning("No products found. Try a different search term.")
        return
    
    if sort_by == "Price: High to Low":
        products = sorted(products, key=lambda p: p.get('price', 0), reverse=True)
    elif sort_by == "Rating: High to Low":
        products = sorted(products, 
                         key=lambda p: p.get('rating', 0) or 0, 
                         reverse=True)
    else:
        products = sorted(products, key=lambda p: p.get('price', float('inf')))
    
    st.markdown(f"### 🛍️ Found {len(products)} Products")
    
    for i, product in enumerate(products):
        render_product_card(product, i, db_manager)

# FIXED: Improved price comparison table
def render_price_comparison_table(products: List[Dict]):
    if not products:
        return
    
    # Find the best price
    best_price = min(p['price'] for p in products)
    
    # Create a list of dictionaries for the table
    table_data = []
    for product in sorted(products, key=lambda p: p['price']):
        is_best_price = product['price'] == best_price
        
        # Format rating
        rating = product.get('rating', 'N/A')
        rating_display = f"{rating} ⭐" if isinstance(rating, float) else rating
        
        # Format shipping
        shipping = product.get('shipping_info', 'Not specified')
        if 'free' in shipping.lower():
            shipping = "🟢 FREE Shipping"
        elif shipping:
            shipping = f"🚚 {shipping}"
        else:
            shipping = "Not specified"
        
        table_data.append({
            "Retailer": product['retailer'],
            "Product": product['name'],
            "Price": f"${product['price']:.2f}",
            "Rating": rating_display,
            "Shipping": shipping,
            "Best Price": "✅" if is_best_price else "",
            "Link": product['url']
        })
    
    # Create DataFrame
    df = pd.DataFrame(table_data)
    
    # Apply styling for best price
    def highlight_best_price(row):
        styles = [''] * len(row)
        if row['Best Price'] == '✅':
            styles = ['background-color: #e8f5e9; font-weight: bold; color: #2e7d32;'] * len(row)
        return styles
    
    # Display the table
    st.markdown("### 📊 Price Comparison Across Retailers")
    st.dataframe(
        df.style.apply(highlight_best_price, axis=1),
        use_container_width=True,
        height=min(500, 35 * len(products) + 35)
    )

def render_price_history(db_manager: DatabaseManager):
    if 'selected_product' in st.session_state:
        product = st.session_state.selected_product
        product_id = db_manager.generate_product_id(product['name'], product['retailer'])
        
        with st.expander(f"📈 Price History: {product['name']}", expanded=True):
            history_df = db_manager.get_price_history(product_id)
            
            if history_df.empty or len(history_df) < 2:
                st.info("Insufficient historical data. Check back later after more searches.")
            else:
                fig = px.line(history_df, x='timestamp', y='price', 
                             color='retailer', markers=True,
                             title=f"Price History for {product['name']}",
                             labels={'price': 'Price (USD)', 'timestamp': 'Date'},
                             template='plotly_white')
                
                fig.update_layout(
                    hovermode='x unified',
                    xaxis_title='',
                    yaxis_title='Price (USD)',
                    legend_title='Retailer'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            if st.button("Close History"):
                del st.session_state.selected_product

# FIXED: Removed matplotlib dependency
def render_comparison_view(db_manager: DatabaseManager):
    if 'comparison_product' in st.session_state:
        product_name = st.session_state.comparison_product
        
        with st.container():
            st.markdown(f"## 📊 Comparing: {product_name}")
            
            comparison_df = db_manager.get_comparison_data(product_name)
            
            if comparison_df.empty:
                st.info("No comparison data available for this product.")
            else:
                # Format numbers without matplotlib dependency
                formatted_df = comparison_df.copy()
                formatted_df['avg_price'] = formatted_df['avg_price'].apply(lambda x: f"${x:.2f}")
                formatted_df['min_price'] = formatted_df['min_price'].apply(lambda x: f"${x:.2f}")
                formatted_df['max_price'] = formatted_df['max_price'].apply(lambda x: f"${x:.2f}")
                formatted_df['avg_rating'] = formatted_df['avg_rating'].apply(lambda x: f"{x:.1f}")
                formatted_df['avg_reviews'] = formatted_df['avg_reviews'].apply(lambda x: f"{x:,.0f}")
                
                # Display the formatted table
                st.dataframe(formatted_df, use_container_width=True)
            
            if st.button("Back to Results"):
                del st.session_state.comparison_product

# --- Main Application Flow ---
def main():
    db_manager = DatabaseManager()
    
    render_header()
    country, sort_by = render_sidebar()
    
    st.markdown("## 🔍 Product Search")
    query = st.text_input("What product are you looking for?", 
                         value=st.session_state.get('search_query', "Wireless Headphones"),
                         placeholder="Enter product name...")
    
    if st.button("Search", type="primary", use_container_width=True):
        st.session_state.search_query = query
        st.session_state.pop('selected_product', None)
        st.session_state.pop('comparison_product', None)
        st.rerun()
    
    render_comparison_view(db_manager)
    render_price_history(db_manager)
    
    if 'search_query' in st.session_state and st.session_state.search_query:
        current_query = st.session_state.search_query
        st.markdown(f"### Results for: '{current_query}'")
        
        with st.spinner(f"🔍 Analyzing prices for '{current_query}'..."):
            results = perform_search(current_query, country)
            if results:
                db_manager.log_prices(results)
                
                # Add tabs for different views
                grid_tab, table_tab = st.tabs(["Product Cards", "Price Comparison Table"])
                
                with grid_tab:
                    render_product_grid(results, sort_by, db_manager)
                
                with table_tab:
                    render_price_comparison_table(results)
    else:
        st.info("👆 Enter a product name and click Search to begin")

if __name__ == "__main__":
    main()