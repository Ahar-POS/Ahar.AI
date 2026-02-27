"""
Pydantic models for request/response validation.

This module contains data models used across the application.
"""

# User models
from app.models.user import (
    UserRole,
    UserStatus,
    UserBase,
    UserCreate,
    UserLogin,
    UserUpdate,
    UserInDB,
    UserResponse,
)

# Session models
from app.models.session import (
    SessionBase,
    SessionCreate,
    SessionInDB,
    SessionResponse,
)

# Table models
from app.models.table import (
    TableStatus,
    TableBase,
    TableCreate,
    TableUpdate,
    TableInDB,
    TableResponse,
)

# Menu Item models
from app.models.menu_item import (
    IngredientTag,
    PrepType,
    MenuItemBase,
    MenuItemCreate,
    MenuItemUpdate,
    MenuItemInDB,
    MenuItemResponse,
)

# Order models
from app.models.order import (
    OrderType,
    OrderStatus,
    OrderItemStatus,
    OrderItem,
    OrderBase,
    OrderCreate,
    OrderUpdate,
    OrderItemStatusUpdate,
    OrderInDB,
    OrderResponse,
    OrderSummary,
)

# Restaurant Settings models
from app.models.restaurant_settings import (
    PlatformSettings,
    RoleSalaries,
    PFESICSettings,
    OvertimeSettings,
    OccupancyCosts,
    TechnologyCosts,
    MarketingBudgets,
    GeneralAdminCosts,
    DepreciationAmortization,
    FinanceCosts,
    TaxSettings,
    RestaurantSettingsBase,
    RestaurantSettingsCreate,
    RestaurantSettingsUpdate,
    RestaurantSettingsInDB,
    RestaurantSettingsResponse,
)

# Packaging Material models
from app.models.packaging_material import (
    PackagingCategory,
    PackagingMaterialBase,
    PackagingMaterialCreate,
    PackagingMaterialUpdate,
    PackagingMaterialInDB,
    PackagingMaterialResponse,
)

# Packaging BOM models
from app.models.packaging_bom import (
    PackagingBOMBase,
    PackagingBOMCreate,
    PackagingBOMUpdate,
    PackagingBOMInDB,
    PackagingBOMResponse,
)

# Fixed Asset models
from app.models.fixed_asset import (
    AssetCategory,
    FixedAssetBase,
    FixedAssetCreate,
    FixedAssetUpdate,
    FixedAssetInDB,
    FixedAssetResponse,
)

__all__ = [
    # User
    "UserRole",
    "UserStatus",
    "UserBase",
    "UserCreate",
    "UserLogin",
    "UserUpdate",
    "UserInDB",
    "UserResponse",
    # Session
    "SessionBase",
    "SessionCreate",
    "SessionInDB",
    "SessionResponse",
    # Table
    "TableStatus",
    "TableBase",
    "TableCreate",
    "TableUpdate",
    "TableInDB",
    "TableResponse",
    # Menu Item
    "IngredientTag",
    "PrepType",
    "MenuItemBase",
    "MenuItemCreate",
    "MenuItemUpdate",
    "MenuItemInDB",
    "MenuItemResponse",
    # Order
    "OrderType",
    "OrderStatus",
    "OrderItemStatus",
    "OrderItem",
    "OrderBase",
    "OrderCreate",
    "OrderUpdate",
    "OrderItemStatusUpdate",
    "OrderInDB",
    "OrderResponse",
    "OrderSummary",
    # Restaurant Settings
    "PlatformSettings",
    "RoleSalaries",
    "PFESICSettings",
    "OvertimeSettings",
    "OccupancyCosts",
    "TechnologyCosts",
    "MarketingBudgets",
    "GeneralAdminCosts",
    "DepreciationAmortization",
    "FinanceCosts",
    "TaxSettings",
    "RestaurantSettingsBase",
    "RestaurantSettingsCreate",
    "RestaurantSettingsUpdate",
    "RestaurantSettingsInDB",
    "RestaurantSettingsResponse",
    # Packaging Material
    "PackagingCategory",
    "PackagingMaterialBase",
    "PackagingMaterialCreate",
    "PackagingMaterialUpdate",
    "PackagingMaterialInDB",
    "PackagingMaterialResponse",
    # Packaging BOM
    "PackagingBOMBase",
    "PackagingBOMCreate",
    "PackagingBOMUpdate",
    "PackagingBOMInDB",
    "PackagingBOMResponse",
    # Fixed Asset
    "AssetCategory",
    "FixedAssetBase",
    "FixedAssetCreate",
    "FixedAssetUpdate",
    "FixedAssetInDB",
    "FixedAssetResponse",
]
