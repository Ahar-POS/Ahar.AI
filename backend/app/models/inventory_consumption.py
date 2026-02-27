"""
Inventory Consumption Log Models

Tracks inventory usage from completed orders for audit and analytics.
"""

from datetime import datetime
from typing import Optional, List
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


class ConsumedMaterial(BaseModel):
    """Individual material consumed in an order"""
    material_id: str = Field(..., description="Material identifier")
    material_name: str = Field(..., description="Material name")
    quantity: float = Field(..., description="Quantity consumed")
    unit: str = Field(..., description="Unit of measurement")
    cost_per_unit: int = Field(0, description="Cost per unit in paise at time of consumption")


class InventoryConsumption(BaseModel):
    """Log entry for inventory consumption from an order"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    order_id: str = Field(..., description="Order ID that triggered consumption")
    order_number: int = Field(..., description="Order number for reference")
    restaurant_id: str = Field(..., description="Restaurant identifier")
    consumed_materials: List[ConsumedMaterial] = Field(
        default_factory=list,
        description="List of materials consumed"
    )
    total_cost: int = Field(0, description="Total raw material cost in paise")
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings generated during consumption (e.g., low stock)"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Errors encountered (e.g., missing recipes)"
    )
    consumed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When inventory was consumed"
    )

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        json_schema_extra = {
            "example": {
                "order_id": "507f1f77bcf86cd799439011",
                "order_number": 1234567890,
                "restaurant_id": "rest_001",
                "consumed_materials": [
                    {
                        "material_id": "RM001",
                        "material_name": "Ciabatta Bread",
                        "quantity": 2,
                        "unit": "Loaf",
                        "cost_per_unit": 6000
                    }
                ],
                "total_cost": 12000,
                "warnings": ["LOW STOCK: Ciabatta Bread at 10 Loaf"],
                "errors": []
            }
        }
