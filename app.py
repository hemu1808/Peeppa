import streamlit as st
import asyncio
import aiohttp
import pandas as pd
import logging
import json
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from typing import List, Dict, Optional
import re
import sqlite3

# --- Page and Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Price Peepa - Shopping Assistant",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS for Styling ---
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 2rem 0;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .price-tag {
        font-size: 1.5rem;
        font-weight: bold;
        color: #2e7d32;
    }
    .deal-badge {
        background: #ff5722;
        color: white;
        padding: 0.2rem 0.8rem;
        border-radius: 20px;
        font-size: 0.8rem;
    }
    .stButton>button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# --- Database Management for Price History ---
class DatabaseManager:
    """Handles all SQLite database operations for storing price history."""
    def __init__(self, db_file="price_data.db"):
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_table()

    def create_table(self):
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
        self.cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_url_timestamp ON price_history (product_url, timestamp)")
        self.conn.commit()

    def log_prices(self, products: List[Dict]):
        if not products:
            return
        insert_query = "INSERT OR IGNORE INTO price_history (product_url, product_name, price, retailer, timestamp) VALUES (?, ?, ?, ?, ?)"
        records = [(p['url'], p['name'], p['price'], p['retailer'], p['timestamp']) for p in products if p.get('url')]
        if records:
            self.cursor.executemany(insert_query, records)
            self.conn.commit()
            logger.info(f"Logged {len(records)} price points to the database.")

    def get_price_history(self, product_url: str) -> pd.DataFrame:
        query = "SELECT timestamp, price, retailer FROM price_history WHERE product_url = ? ORDER BY timestamp ASC"
        df = pd.read_sql_query(query, self.conn, params=(product_url,))
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df

# --- API Integration (Now with Zenserp) ---
class ZenserpAPI:
    """Zenserp API integration for fetching Google Shopping results."""
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://app.zenserp.com/api/v2/search"

    async def search_products(self, query: str, session: aiohttp.ClientSession, country: str = "US") -> List[Dict]:
        headers = {"apikey": self.api_key}
        params = {
            'q': query,
            'tbm': 'shop',  # This is crucial for getting shopping results
            'location': self.get_location_for_country(country),
        }
        try:
            async with session.get(self.base_url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_zenserp_results(data)
                else:
                    logger.error(f"Zenserp API error: {response.status} - {await response.text()}")
                    st.error(f"Zenserp API Error: {response.status}. Check your API key or plan limits.")
                    return []
        except Exception as e:
            logger.error(f"Zenserp API request error: {e}")
            return []

    def _parse_zenserp_results(self, data: Dict) -> List[Dict]:
        """Parse Zenserp shopping results into our standard product format."""
        products = []
        for item in data.get('shopping_results', []):
            try:
                # Zenserp provides structured price data, which is much more reliable
                price_str = item.get('price', '').replace('$', '').replace(',', '').strip()
                if not price_str:
                    continue
                
                price = float(price_str)
                product = {
                    'name': item.get('title', 'No Title'),
                    'price': price,
                    'url': item.get('link', ''),
                    'retailer': item.get('source', 'Unknown Retailer'),
                    'image_url': item.get('thumbnail', ''),
                    'snippet': item.get('snippet', ''),
                    'source': 'Zenserp',
                    'timestamp': datetime.now().isoformat()
                }
                products.append(product)
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse item: {item.get('title')} - Price: {item.get('price')} - Error: {e}")
                continue
        return products

    def get_location_for_country(self, country_code: str) -> str:
        """Map country code to Zenserp location string."""
        location_map = {
            "US": "United States", "CA": "Canada", "UK": "United Kingdom",
            "AU": "Australia", "DE": "Germany", "FR": "France"
        }
        return location_map.get(country_code, "United States")

# --- Core Application Logic ---
class PriceComparisonEngine:
    def __init__(self):
        self.api_client = self._initialize_apis()
    
    def _initialize_apis(self):
        zenserp_api_key = st.secrets.get("ZENSERP_API_KEY")
        if zenserp_api_key:
            logger.info("Zenserp API initialized.")
            return ZenserpAPI(zenserp_api_key)
        else:
            logger.warning("Zenserp API key not found in Streamlit secrets.")
            st.error("ZENSERP_API_KEY is not set in your secrets.toml file.")
            return None

    async def search_products_async(self, query: str, country: str) -> List[Dict]:
        if not self.api_client:
            return []
        async with aiohttp.ClientSession() as session:
            products = await self.api_client.search_products(query, session, country)
            products.sort(key=lambda p: p.get('price', float('inf')))
            return products

# --- Cached Search Function ---
@st.cache_data(ttl=1800) # Cache results for 30 minutes
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

# --- UI Rendering Functions (largely unchanged) ---
def render_header():
    st.markdown("""
    <div class="main-header">
        <h1>🐍 Price Peepa</h1>
        <p>Your Smart Shopping Assistant - Powered by Zenserp</p>
    </div>
    """, unsafe_allow_html=True)

def render_sidebar():
    st.sidebar.markdown("## 🎛️ Search Options")
    country = st.sidebar.selectbox("Country", ["US", "CA", "UK", "AU", "DE", "FR"], index=0)
    sort_by = st.sidebar.selectbox("Sort By", ["Price: Low to High", "Price: High to Low"])
    return country, sort_by

def render_product_grid(products: List[Dict], sort_by: str):
    if not products:
        st.warning("No products found. Try a different search term or check your API key.")
        return

    if sort_by == "Price: High to Low":
        products = sorted(products, key=lambda p: p.get('price', 0), reverse=True)
    
    st.markdown(f"### 🛍️ Found {len(products)} Product Offers")
    st.divider()

    for i, product in enumerate(products):
        col1, col2, col3 = st.columns([1, 4, 1.5])
        with col1:
            st.image(product['image_url'], width=80) if product.get('image_url') else st.markdown("📦")
        with col2:
            st.markdown(f"**{product['name']}**")
            st.caption(f"🏪 Sold by: {product['retailer']}")
            if i == 0 and sort_by == "Price: Low to High":
                st.markdown("<span class='deal-badge'>🏆 Best Deal</span>", unsafe_allow_html=True)
        with col3:
            st.markdown(f"<p class='price-tag' style='text-align:right;'>${product['price']:.2f}</p>", unsafe_allow_html=True)
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                st.link_button("🔗 Visit", product['url'], use_container_width=True)
            with btn_col2:
                if st.button("📈 History", key=f"hist_{i}", use_container_width=True):
                    st.session_state.selected_product_for_history = product
                    st.rerun()
        st.divider()

def render_price_history_chart(db_manager: DatabaseManager):
    if 'selected_product_for_history' in st.session_state:
        product = st.session_state.selected_product_for_history
        with st.expander(f"📈 Price History for: {product['name']}", expanded=True):
            history_df = db_manager.get_price_history(product['url'])
            if len(history_df) < 2:
                st.info("Not enough data to plot a history chart. Search for this product again over time to build history.")
            else:
                fig = go.Figure(go.Scatter(x=history_df['timestamp'], y=history_df['price'], mode='lines+markers', line=dict(color='#667eea', width=2)))
                fig.update_layout(title=f"Price History on {product['retailer']}", xaxis_title="Date", yaxis_title="Price (USD)", yaxis_tickprefix='$')
                st.plotly_chart(fig, use_container_width=True)
            if st.button("Close History"):
                del st.session_state.selected_product_for_history
                st.rerun()

# --- Main Application ---
def main():
    render_header()
    db_manager = DatabaseManager()
    country, sort_by = render_sidebar()
    
    st.markdown("## 🔍 Find a Product")
    query = st.text_input("What are you looking for?", st.session_state.get('search_query', "Sony WH-1000XM5"))
    
    if st.button("Search", type="primary"):
        st.session_state.search_query = query
        if 'selected_product_for_history' in st.session_state:
            del st.session_state.selected_product_for_history

    render_price_history_chart(db_manager)

    if 'search_query' in st.session_state and st.session_state.search_query:
        current_query = st.session_state.search_query
        with st.spinner(f"🐍 Peeping at prices for '{current_query}'..."):
            results = perform_search(current_query, country)
            if results:
                db_manager.log_prices(results)
                render_product_grid(results, sort_by)
    else:
         st.info("👆 Enter a product name and click Search to begin.")

if __name__ == "__main__":
    main()