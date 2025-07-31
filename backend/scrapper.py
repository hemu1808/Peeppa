"""
Web scraper implementation for various online retailers.
Supports product search and detailed product information retrieval.
"""

import requests
from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString
import re
import logging
import random
import time
from datetime import datetime
from typing import List, Optional, Dict, Any, Union, Callable
from abc import ABC, abstractmethod

from config import Config
from models import Product, ProductSpec

# Configure logger
logger = logging.getLogger(__name__)

class ScraperError(Exception):
    """Base exception for all scraper-related errors."""
    pass

class RetailerNotSupportedError(ScraperError):
    """Raised when attempting to use an unsupported retailer."""
    pass

class ProductParsingError(ScraperError):
    """Raised when unable to parse product information."""
    pass

class Scraper:
    """A web scraper for various online retailers."""
    
    RETAILERS = {
        "Amazon": "https://www.amazon.com",
        "Best Buy": "https://www.bestbuy.com",
        "Walmart": "https://www.walmart.com",
        "Target": "https://www.target.com",
        "Newegg": "https://www.newegg.com"
    }
    
    def __init__(self) -> None:
        """Initialize the scraper with a session and headers."""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": Config.USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        })
        
        # Initialize retailer-specific search handlers
        self.search_handlers: Dict[str, Callable[[str], List[Product]]] = {
            "Amazon": self._search_amazon,
            "Best Buy": self._search_bestbuy,
            "Walmart": self._search_walmart,
            "Target": self._search_target,
            "Newegg": self._search_newegg
        }
        
    def search_products(self, query: str, retailers: List[str]) -> List[Product]:
        """Search for products across multiple retailers."""
        results: List[Product] = []
        successful_retailers = 0
        
        for retailer in retailers:
            if retailer not in self.RETAILERS:
                logger.warning(f"Unsupported retailer: {retailer}")
                continue
            
            try:
                handler = self.search_handlers.get(retailer)
                if handler:
                    retailer_results = handler(query)
                    if retailer_results:
                        results.extend(retailer_results)
                        successful_retailers += 1
                        logger.info(f"Successfully scraped {len(retailer_results)} products from {retailer}")
                    else:
                        logger.warning(f"No products found for {retailer}")
                else:
                    logger.warning(f"No search handler for retailer: {retailer}")
            except Exception as e:
                logger.error(f"Error searching {retailer}: {str(e)}")
        
        # If no real results, provide fallback demo data
        if not results and Config.ENABLE_DEMO_MODE:
            logger.info("No real products found, providing demo data")
            results = self._get_demo_products(query)
        
        logger.info(f"Search completed: {successful_retailers}/{len(retailers)} retailers successful, {len(results)} total products found")
        return results

    def _get_demo_products(self, query: str) -> List[Product]:
        """Provide demo products when scraping fails."""
        demo_products = [
            Product(
                name=f"{query.title()} - Demo Product 1",
                price=299.99,
                link="https://example.com/product1",
                retailer="Demo Store",
                specifications=[
                    ProductSpec(key="Brand", value="Demo Brand"),
                    ProductSpec(key="Model", value=f"{query.upper()}-001"),
                    ProductSpec(key="Condition", value="New")
                ],
                image_url="https://via.placeholder.com/300x300?text=Product+1"
            ),
            Product(
                name=f"{query.title()} - Demo Product 2",
                price=399.99,
                link="https://example.com/product2",
                retailer="Demo Store",
                specifications=[
                    ProductSpec(key="Brand", value="Demo Brand"),
                    ProductSpec(key="Model", value=f"{query.upper()}-002"),
                    ProductSpec(key="Condition", value="New")
                ],
                image_url="https://via.placeholder.com/300x300?text=Product+2"
            ),
            Product(
                name=f"{query.title()} - Demo Product 3",
                price=199.99,
                link="https://example.com/product3",
                retailer="Demo Store",
                specifications=[
                    ProductSpec(key="Brand", value="Demo Brand"),
                    ProductSpec(key="Model", value=f"{query.upper()}-003"),
                    ProductSpec(key="Condition", value="New")
                ],
                image_url="https://via.placeholder.com/300x300?text=Product+3"
            )
        ]
        return demo_products

    def _parse_price(self, price_str: Optional[str]) -> float:
        """Extract price from string, handling currency symbols and formatting."""
        if not price_str:
            return 0.0
        # Remove currency symbols and whitespace
        price_str = re.sub(r'[^\d.]', '', price_str)
        try:
            return float(price_str)
        except ValueError:
            return 0.0

    def _extract_text(self, element: Optional[Union[Tag, NavigableString]]) -> str:
        """Safely extract text from a BS4 element."""
        if element is None:
            return ""
        if isinstance(element, NavigableString):
            return str(element).strip()
        return element.get_text(strip=True)

    def _extract_attr(self, element: Optional[Tag], attr: str) -> str:
        """Safely extract attribute from a BS4 element."""
        if element is None:
            return ""
        return element.get(attr, "")

    def _get_soup(self, url: str) -> Optional[BeautifulSoup]:
        """Get BeautifulSoup object from URL with error handling."""
        try:
            # Add random delay to avoid rate limiting
            time.sleep(random.uniform(1, 3))
            
            # Enhanced headers to avoid detection
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Cache-Control": "max-age=0"
            }
            
            response = self.session.get(
                url, 
                timeout=Config.SCRAPE_TIMEOUT,
                headers=headers,
                allow_redirects=True
            )
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except requests.RequestException as e:
            logger.error(f"Request failed for {url}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error parsing {url}: {str(e)}")
            return None

    def _search_amazon(self, query: str) -> List[Product]:
        """Search Amazon for products."""
        products: List[Product] = []
        url = f"{self.RETAILERS['Amazon']}/s?k={query.replace(' ', '+')}"
        
        soup = self._get_soup(url)
        if not soup:
            return products
            
        for item in soup.select('.s-result-item[data-component-type="s-search-result"]'):
            try:
                # Extract product elements
                name_elem = item.select_one('h2 .a-link-normal')
                price_elem = item.select_one('.a-price .a-offscreen')
                link_elem = item.select_one('h2 .a-link-normal')
                image_elem = item.select_one('img.s-image')
                
                # Skip if missing required elements
                if not all([name_elem, price_elem, link_elem, image_elem]):
                    continue
                
                # Extract and validate name
                name = self._extract_text(name_elem)
                if not name:
                    continue
                    
                # Extract and validate price
                price = self._parse_price(self._extract_text(price_elem))
                if price <= 0:
                    continue
                    
                # Build product URLs
                link = self._extract_attr(link_elem, 'href')
                if not link.startswith('http'):
                    link = f"{self.RETAILERS['Amazon']}{link}"
                    
                image = self._extract_attr(image_elem, 'src')
                
                # Create product with basic info
                product = Product(
                    name=name,
                    price=price,
                    link=link,
                    retailer="Amazon",
                    specifications=[],
                    image_url=image
                )
                products.append(product)
                
            except Exception as e:
                logger.error(f"Error parsing Amazon product: {str(e)}")
                continue
                
        # Respect rate limits
        time.sleep(random.uniform(1, 2))
            
        # Return limited results
        return products[:5]

    def _search_bestbuy(self, query: str) -> List[Product]:
        """Search Best Buy for products."""
        products: List[Product] = []
        url = f"{self.RETAILERS['Best Buy']}/site/searchpage.jsp?st={query.replace(' ', '+')}"
        
        soup = self._get_soup(url)
        if not soup:
            return products
            
        try:
            # Look for product cards in search results
            product_cards = soup.select(".sku-item, .shop-sku-list-item")
            
            for card in product_cards[:10]:  # Limit to 10 results
                try:
                    # Extract product information
                    name_elem = card.select_one(".sku-title h4 a, .sku-title a")
                    price_elem = card.select_one(".priceView-customer-price span, .priceView-layout-large .priceView-customer-price")
                    link_elem = card.select_one(".sku-title h4 a, .sku-title a")
                    image_elem = card.select_one(".sku-image img, .product-image img")
                    
                    if not name_elem:
                        continue
                    
                    name = self._extract_text(name_elem)
                    price = self._parse_price(self._extract_text(price_elem)) if price_elem else 0.0
                    link = self._extract_attr(link_elem, "href")
                    image_url = self._extract_attr(image_elem, "src")
                    
                    if name and price > 0:
                        # Construct full URL
                        product_url = f"{self.RETAILERS['Best Buy']}{link}" if link and link.startswith('/') else link
                        
                        # Get basic specs from search result
                        specs = []
                        spec_elems = card.select(".sku-attribute-text")
                        for spec_elem in spec_elems[:3]:  # Limit specs
                            spec_text = self._extract_text(spec_elem)
                            if spec_text:
                                specs.append(ProductSpec(key="Specification", value=spec_text))
                        
                        products.append(Product(
                            name=name,
                            price=price,
                            link=product_url,
                            retailer="Best Buy",
                            specifications=specs,
                            image_url=image_url
                        ))
                except Exception as e:
                    logger.warning(f"Error parsing Best Buy product: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error searching Best Buy: {str(e)}")
            
        return products
            
    def _search_walmart(self, query: str) -> List[Product]:
        """Search Walmart for products."""
        products: List[Product] = []
        url = f"{self.RETAILERS['Walmart']}/search?q={query.replace(' ', '+')}"
        
        soup = self._get_soup(url)
        if not soup:
            return products
            
        try:
            # Look for product cards in search results
            product_cards = soup.select("[data-item-id], .search-result-gridview-item")
            
            for card in product_cards[:10]:  # Limit to 10 results
                try:
                    # Extract product information
                    name_elem = card.select_one(".product-title-link, .product-title")
                    price_elem = card.select_one(".price-main, .price-characteristic")
                    link_elem = card.select_one(".product-title-link, .product-title a")
                    image_elem = card.select_one(".product-image img, .product-image-photo")
                    
                    if not name_elem:
                        continue
                    
                    name = self._extract_text(name_elem)
                    price = self._parse_price(self._extract_text(price_elem)) if price_elem else 0.0
                    link = self._extract_attr(link_elem, "href")
                    image_url = self._extract_attr(image_elem, "src")
                    
                    if name and price > 0:
                        # Construct full URL
                        product_url = f"{self.RETAILERS['Walmart']}{link}" if link and link.startswith('/') else link
                        
                        # Get basic specs from search result
                        specs = []
                        spec_elems = card.select(".product-attribute")
                        for spec_elem in spec_elems[:3]:  # Limit specs
                            spec_text = self._extract_text(spec_elem)
                            if spec_text:
                                specs.append(ProductSpec(key="Specification", value=spec_text))
                        
                        products.append(Product(
                            name=name,
                            price=price,
                            link=product_url,
                            retailer="Walmart",
                            specifications=specs,
                            image_url=image_url
                        ))
                except Exception as e:
                    logger.warning(f"Error parsing Walmart product: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error searching Walmart: {str(e)}")
            
        return products
            
    def _search_target(self, query: str) -> List[Product]:
        """Search Target for products."""
        products: List[Product] = []
        url = f"{self.RETAILERS['Target']}/s?searchTerm={query.replace(' ', '+')}"
        
        soup = self._get_soup(url)
        if not soup:
            return products
            
        try:
            # Look for product cards in search results
            product_cards = soup.select("[data-testid='product-card'], .ProductCard")
            
            for card in product_cards[:10]:  # Limit to 10 results
                try:
                    # Extract product information
                    name_elem = card.select_one("[data-testid='product-title'], .ProductCard__Title")
                    price_elem = card.select_one("[data-testid='product-price'], .ProductCard__Price")
                    link_elem = card.select_one("a[href*='/p/']")
                    image_elem = card.select_one("img[data-testid='product-image']")
                    
                    if not name_elem:
                        continue
                    
                    name = self._extract_text(name_elem)
                    price = self._parse_price(self._extract_text(price_elem)) if price_elem else 0.0
                    link = self._extract_attr(link_elem, "href")
                    image_url = self._extract_attr(image_elem, "src")
                    
                    if name and price > 0:
                        # Construct full URL
                        product_url = f"{self.RETAILERS['Target']}{link}" if link and link.startswith('/') else link
                        
                        # Get basic specs from search result
                        specs = []
                        spec_elems = card.select("[data-testid='product-description']")
                        for spec_elem in spec_elems[:2]:  # Limit specs
                            spec_text = self._extract_text(spec_elem)
                            if spec_text:
                                specs.append(ProductSpec(key="Description", value=spec_text))
                        
                        products.append(Product(
                            name=name,
                            price=price,
                            link=product_url,
                            retailer="Target",
                            specifications=specs,
                            image_url=image_url
                        ))
                except Exception as e:
                    logger.warning(f"Error parsing Target product: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error searching Target: {str(e)}")
            
        return products
            
    def _search_newegg(self, query: str) -> List[Product]:
        """Search Newegg for products."""
        products: List[Product] = []
        url = f"{self.RETAILERS['Newegg']}/p/pl?d={query.replace(' ', '+')}"
        
        soup = self._get_soup(url)
        if not soup:
            return products
            
        try:
            # Look for product cards in search results
            product_cards = soup.select(".item-cell, .item-container")
            
            for card in product_cards[:10]:  # Limit to 10 results
                try:
                    # Extract product information
                    name_elem = card.select_one(".item-title, .item-title a")
                    price_elem = card.select_one(".price-current, .price-current .price")
                    link_elem = card.select_one(".item-title a, .item-img a")
                    image_elem = card.select_one(".item-img img")
                    
                    if not name_elem:
                        continue
                    
                    name = self._extract_text(name_elem)
                    price = self._parse_price(self._extract_text(price_elem)) if price_elem else 0.0
                    link = self._extract_attr(link_elem, "href")
                    image_url = self._extract_attr(image_elem, "src")
                    
                    if name and price > 0:
                        # Construct full URL
                        product_url = f"{self.RETAILERS['Newegg']}{link}" if link and link.startswith('/') else link
                        
                        # Get basic specs from search result
                        specs = []
                        spec_elems = card.select(".item-features li, .item-description")
                        for spec_elem in spec_elems[:3]:  # Limit specs
                            spec_text = self._extract_text(spec_elem)
                            if spec_text:
                                specs.append(ProductSpec(key="Feature", value=spec_text))
                        
                        products.append(Product(
                            name=name,
                            price=price,
                            link=product_url,
                            retailer="Newegg",
                            specifications=specs,
                            image_url=image_url
                        ))
                except Exception as e:
                    logger.warning(f"Error parsing Newegg product: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error searching Newegg: {str(e)}")
            
        return products

    def scrape_product(self, url: str, retailer: str) -> Optional[Product]:
        """Scrape detailed product information from a product page."""
        soup = self._get_soup(url)
        if not soup:
            return None
            
        try:
            # Get product details
            name = self._extract_product_name(soup, retailer)
            if not name:
                logger.error(f"Could not find product name for {url}")
                return None
                
            price = self._parse_product_price(soup, retailer)
            if price <= 0:
                logger.error(f"Could not find valid price for {url}")
                return None
                
            specs = self._extract_product_specs(soup, retailer)
            image = self._extract_product_image(soup, retailer)
            
            # Create product with all available info
            return Product(
                name=name,
                price=price,
                link=url,
                retailer=retailer,
                specifications=specs,
                image_url=image
            )
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            return None
    
    def _extract_product_name(self, soup: BeautifulSoup, retailer: str) -> Optional[str]:
        """Extract product name based on retailer-specific selectors."""
        try:
            if retailer == "Amazon":
                elem = soup.select_one("#productTitle")
            elif retailer == "Best Buy":
                elem = soup.select_one("h1.sku-title")
            else:
                elem = soup.select_one("h1") or soup.title
                
            return self._extract_text(elem)
        except Exception as e:
            logger.error(f"Error extracting product name: {str(e)}")
            return None

    def _parse_product_price(self, soup: BeautifulSoup, retailer: str) -> float:
        """Extract product price based on retailer-specific selectors."""
        try:
            if retailer == "Amazon":
                price_elem = soup.select_one("#priceblock_ourprice, .a-price .a-offscreen")
            elif retailer == "Best Buy":
                price_elem = soup.select_one(".priceView-customer-price span")
            else:
                price_elem = soup.select_one("[class*='price'], .price")
                
            if price_elem:
                return self._parse_price(self._extract_text(price_elem))
            return 0.0
        except Exception as e:
            logger.error(f"Error parsing product price: {str(e)}")
            return 0.0

    def _extract_product_specs(self, soup: BeautifulSoup, retailer: str) -> List[ProductSpec]:
        """Extract product specifications based on retailer-specific selectors."""
        specs = []
        try:
            if retailer == "Amazon":
                spec_table = soup.select_one("#productDetails_techSpec_section_1")
                if spec_table:
                    rows = spec_table.select("tr")
                    for row in rows:
                        key = self._extract_text(row.select_one("th"))
                        value = self._extract_text(row.select_one("td"))
                        if key and value:
                            specs.append(ProductSpec(key=key, value=value))
            else:
                # Generic spec extraction
                spec_elems = soup.select("table tr, .specs tr")
                for row in spec_elems:
                    key = self._extract_text(row.select_one("th"))
                    value = self._extract_text(row.select_one("td"))
                    if key and value:
                        specs.append(ProductSpec(key=key, value=value))
                        
        except Exception as e:
            logger.error(f"Error extracting product specs: {str(e)}")
            
        return specs

    def _extract_product_image(self, soup: BeautifulSoup, retailer: str) -> str:
        """Extract product image URL based on retailer-specific selectors."""
        try:
            if retailer == "Amazon":
                img_elem = soup.select_one("#landingImage, #imgBlkFront")
            elif retailer == "Best Buy":
                img_elem = soup.select_one(".primary-image img")
            else:
                img_elem = soup.select_one("img[src*='product'], .product-image img")
                
            if img_elem:
                return self._extract_attr(img_elem, "src")
            return ""
        except Exception as e:
            logger.error(f"Error extracting product image: {str(e)}")
            return ""
