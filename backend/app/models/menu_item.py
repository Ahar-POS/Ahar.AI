"""
Menu Item model definitions.

Defines the MenuItem schema for restaurant menu management.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class IngredientTag(str, Enum):
    """
    Common ingredient tags for menu items.
    
    Note: To add new ingredients, simply add them to this enum.
    This provides validation while maintaining flexibility.
    """
    # Proteins
    BEEF = "beef"
    CHICKEN = "chicken"
    PORK = "pork"
    FISH = "fish"
    SHRIMP = "shrimp"
    LAMB = "lamb"
    TURKEY = "turkey"
    HAM = "ham"
    BACON = "bacon"
    SALAMI = "salami"
    PROSCIUTTO = "prosciutto"
    
    # Vegetables
    TOMATOES = "tomatoes"
    BASIL = "basil"
    GARLIC = "garlic"
    ONIONS = "onions"
    MUSHROOMS = "mushrooms"
    PEPPERS = "peppers"
    ARUGULA = "arugula"
    SPINACH = "spinach"
    LETTUCE = "lettuce"
    PICKLES = "pickles"
    OLIVES = "olives"
    AVOCADO = "avocado"
    
    # Dairy & Cheese
    MOZZARELLA = "mozzarella"
    PARMESAN = "parmesan"
    CHEESE = "cheese"
    CREAM = "cream"
    BUTTER = "butter"
    PROVOLONE = "provolone"
    CHEDDAR = "cheddar"
    SWISS = "swiss"
    FETA = "feta"
    
    # Grains & Pasta
    BREAD = "bread"
    PASTA = "pasta"
    RICE = "rice"
    GNOCCHI = "gnocchi"
    SPAGHETTI = "spaghetti"
    PENNE = "penne"
    
    # Condiments & Sauces
    MAYONNAISE = "mayonnaise"
    MUSTARD = "mustard"
    PESTO = "pesto"
    AIOLI = "aioli"
    HONEY = "honey"
    
    # Other
    EGG = "egg"
    OLIVE_OIL = "olive oil"
    WINE = "wine"
    NUTS = "nuts"
    CHOCOLATE = "chocolate"


class PrepType(str, Enum):
    """
    Preparation method for menu items.
    
    Note: To add new prep types, simply add them to this enum.
    Used for kitchen organization and timing.
    """
    COLD = "cold"  # No cooking required (salads, cold appetizers)
    FRY = "fry"  # Deep fried or pan fried
    GRILL = "grill"  # Grilled items
    PASTA = "pasta"  # Pasta dishes
    OVEN = "oven"  # Baked or roasted
    STEAM = "steam"  # Steamed dishes
    SAUTE = "saute"  # Sautéed dishes
    RAW = "raw"  # Raw preparations (carpaccio, tartare)
    BEVERAGE = "beverage"  # Drinks
    DESSERT = "dessert"  # Desserts


class MenuItemBase(BaseModel):
    """Base menu item fields shared across models."""
    name: str = Field(..., min_length=1, max_length=100, description="Menu item name")
    description: str = Field(..., min_length=1, max_length=500, description="Item description")
    price: int = Field(..., ge=0, description="Price in paise (smallest currency unit, e.g., 12500 = ₹125.00)")
    category: str = Field(..., min_length=1, max_length=50, description="Menu category (e.g., 'Classic Sandwiches', 'Gourmet Specials')")
    tags: List[IngredientTag] = Field(default_factory=list, description="Ingredient tags for the item")
    prep_type: PrepType = Field(..., description="Preparation method")
    is_available: bool = Field(default=True, description="Whether item is currently available for ordering")


class MenuItemCreate(MenuItemBase):
    """Schema for creating a new menu item."""
    pass


class MenuItemUpdate(BaseModel):
    """Schema for updating menu item details."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    price: Optional[int] = Field(None, ge=0)
    category: Optional[str] = Field(None, min_length=1, max_length=50)
    tags: Optional[List[IngredientTag]] = None
    prep_type: Optional[PrepType] = None
    is_available: Optional[bool] = None
    is_active: Optional[bool] = None


class MenuItemInDB(MenuItemBase):
    """Menu item model as stored in database."""
    id: str = Field(..., alias="_id")
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True


class MenuItemResponse(BaseModel):
    """Menu item data returned to clients."""
    id: str
    name: str
    description: str
    price: int
    category: str
    tags: List[IngredientTag]
    prep_type: PrepType
    is_available: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
