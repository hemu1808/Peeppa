from datetime import datetime
from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, EmailStr, Field

class ProductSpec(BaseModel):
    key: str
    value: str

class Product(BaseModel):
    name: str
    price: float
    link: str
    retailer: str
    specifications: List[ProductSpec]
    last_updated: datetime = datetime.now()
    image_url: Optional[str] = None

class PriceHistoryPoint(BaseModel):
    product_id: str
    price: float
    timestamp: datetime = datetime.now()

class ProductDisplay(BaseModel):
    id: str
    name: str
    price: str
    retailer: str
    specifications: Dict[str, str]
    link: str

class PriceAlert(BaseModel):
    product_id: str
    target_price: float
    condition: Literal["above", "below"]
    email: EmailStr
    created_at: datetime = Field(default_factory=datetime.now)
    last_checked: Optional[datetime] = None
    is_active: bool = True

class PriceAlertResponse(BaseModel):
    success: bool
    message: str
    alert_id: Optional[str] = None