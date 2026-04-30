from datetime import datetime
from typing import Optional, List, Dict, Any
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


class Notification(BaseModel):
    """In-app notification record — persisted in MongoDB with 7-day TTL."""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    notification_id: str = Field(..., description="Unique string ID for frontend dedup")
    type: str = Field(..., description="low_stock | revenue_anomaly | expiry_alert | po_approval | system")
    title: str = Field(..., description="Short display title")
    message: str = Field(..., description="Full notification message")
    severity: str = Field(default="info", description="info | warning | high")
    target_roles: List[str] = Field(..., description="Roles that should see this notification")
    restaurant_id: str = Field(..., description="Scoped to restaurant")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary context payload")
    is_read: bool = Field(default=False)
    read_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class NotificationResponse(BaseModel):
    """Serialised notification for API responses."""
    notification_id: str
    type: str
    title: str
    message: str
    severity: str
    target_roles: List[str]
    metadata: Dict[str, Any] = {}
    is_read: bool
    read_at: Optional[str] = None
    created_at: str

    class Config:
        populate_by_name = True
