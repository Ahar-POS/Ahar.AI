from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from bson import ObjectId


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")


class InventoryItem(BaseModel):
    """Raw material inventory item model"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    material_id: str = Field(..., description="Unique material identifier")
    material_name: str = Field(..., description="Name of the material")
    category: str = Field(..., description="Category of the material")
    unit: str = Field(..., description="Unit of measurement")
    unit_cost_inr: int = Field(..., description="Cost per unit in INR (paise)")
    reorder_level: int = Field(..., description="Stock level that triggers reorder")
    reorder_qty: int = Field(..., description="Quantity to order when restocking")
    current_stock: int = Field(..., description="Current stock quantity")
    max_stock: int = Field(..., description="Maximum stock capacity")
    lead_time_days: int = Field(..., description="Days required for delivery")
    supplier_id: str = Field(..., description="Supplier identifier")
    last_restock_date: Optional[str] = Field(None, description="Last restocking date")
    shelf_life_days: int = Field(..., description="Shelf life in days")
    storage_temp_c: str = Field(..., description="Storage temperature requirement")
    is_perishable: str = Field(..., description="Whether item is perishable (Yes/No)")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        json_schema_extra = {
            "example": {
                "material_id": "RM001",
                "material_name": "Ciabatta Bread",
                "category": "Bakery",
                "unit": "Loaf",
                "unit_cost_inr": 6000,
                "reorder_level": 20,
                "reorder_qty": 50,
                "current_stock": 45,
                "max_stock": 100,
                "lead_time_days": 1,
                "supplier_id": "SUP001",
                "last_restock_date": "2025-01-15",
                "shelf_life_days": 3,
                "storage_temp_c": "Room Temp",
                "is_perishable": "Yes"
            }
        }


class InventoryItemCreate(BaseModel):
    """Schema for creating a new inventory item"""
    material_id: str
    material_name: str
    category: str
    unit: str
    unit_cost_inr: int
    reorder_level: int
    reorder_qty: int
    current_stock: int
    max_stock: int
    lead_time_days: int
    supplier_id: str
    last_restock_date: Optional[str] = None
    shelf_life_days: int
    storage_temp_c: str
    is_perishable: str


class InventoryItemUpdate(BaseModel):
    """Schema for updating an inventory item"""
    material_name: Optional[str] = None
    category: Optional[str] = None
    unit: Optional[str] = None
    unit_cost_inr: Optional[int] = None
    reorder_level: Optional[int] = None
    reorder_qty: Optional[int] = None
    current_stock: Optional[int] = None
    max_stock: Optional[int] = None
    lead_time_days: Optional[int] = None
    supplier_id: Optional[str] = None
    last_restock_date: Optional[str] = None
    shelf_life_days: Optional[int] = None
    storage_temp_c: Optional[str] = None
    is_perishable: Optional[str] = None


class InventoryItemResponse(BaseModel):
    """Schema for inventory item response"""
    id: str = Field(alias="_id")
    material_id: str
    material_name: str
    category: str
    unit: str
    unit_cost_inr: int
    reorder_level: int
    reorder_qty: int
    current_stock: int
    max_stock: int
    lead_time_days: int
    supplier_id: str
    last_restock_date: Optional[str]
    shelf_life_days: int
    storage_temp_c: str
    is_perishable: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        populate_by_name = True
