"""
Restaurant Settings model for configurable P&L parameters.

This model stores all configurable values for P&L calculation including:
- Platform commission rates
- Role-based salaries
- Monthly OPEX budgets
- Tax rates and depreciation
"""

from datetime import datetime
from typing import Dict, Optional
from pydantic import BaseModel, Field


class PlatformSettings(BaseModel):
    """Platform commission and tax settings."""
    zomato_commission_rate: float = Field(0.23, ge=0, le=1, description="Zomato commission rate (23%)")
    swiggy_commission_rate: float = Field(0.23, ge=0, le=1, description="Swiggy commission rate (23%)")
    gst_rate: float = Field(0.05, ge=0, le=1, description="GST rate on food (5%)")
    cancellation_rate: float = Field(0.015, ge=0, le=1, description="Average cancellation rate (1.5%)")


class RoleSalaries(BaseModel):
    """Monthly salaries by staff role (in paise)."""
    cook: int = Field(5000000, ge=0, description="Cook monthly salary in paise (₹50,000)")
    helper: int = Field(2500000, ge=0, description="Helper monthly salary in paise (₹25,000)")
    packing_staff: int = Field(2200000, ge=0, description="Packing staff monthly salary in paise (₹22,000)")
    supervisor: int = Field(6000000, ge=0, description="Supervisor monthly salary in paise (₹60,000)")
    manager: int = Field(8000000, ge=0, description="Manager monthly salary in paise (₹80,000)")
    waiter: int = Field(2000000, ge=0, description="Waiter monthly salary in paise (₹20,000)")
    admin: int = Field(4000000, ge=0, description="Admin monthly salary in paise (₹40,000)")


class PFESICSettings(BaseModel):
    """PF and ESIC contribution rates."""
    pf_employer_rate: float = Field(0.12, ge=0, le=1, description="PF employer contribution (12%)")
    esic_employer_rate: float = Field(0.0175, ge=0, le=1, description="ESIC employer contribution (1.75%)")

    @property
    def total_employer_contribution(self) -> float:
        """Total employer contribution rate (13.75%)."""
        return self.pf_employer_rate + self.esic_employer_rate


class OvertimeSettings(BaseModel):
    """Overtime allowance settings (monthly, in paise)."""
    cook: int = Field(500000, ge=0, description="Cook overtime allowance in paise (₹5,000)")
    helper: int = Field(300000, ge=0, description="Helper overtime allowance in paise (₹3,000)")
    packing_staff: int = Field(300000, ge=0, description="Packing staff overtime in paise (₹3,000)")
    supervisor: int = Field(500000, ge=0, description="Supervisor overtime in paise (₹5,000)")
    manager: int = Field(0, ge=0, description="Manager overtime in paise (₹0)")
    waiter: int = Field(200000, ge=0, description="Waiter overtime in paise (₹2,000)")
    admin: int = Field(0, ge=0, description="Admin overtime in paise (₹0)")


class OccupancyCosts(BaseModel):
    """Monthly occupancy and utility costs (in paise)."""
    rent: int = Field(3200000, ge=0, description="Kitchen rent in paise (₹32,000)")
    electricity: int = Field(1800000, ge=0, description="Electricity in paise (₹18,000)")
    water: int = Field(300000, ge=0, description="Water charges in paise (₹3,000)")
    internet: int = Field(200000, ge=0, description="Internet & communication in paise (₹2,000)")


class TechnologyCosts(BaseModel):
    """Monthly technology and software costs (in paise)."""
    pos_software: int = Field(1000000, ge=0, description="POS software license in paise (₹10,000)")
    platform_subscriptions: int = Field(200000, ge=0, description="Platform subscriptions in paise (₹2,000)")
    menu_photography_amortized: int = Field(150000, ge=0, description="Menu photography amortized in paise (₹1,500)")


class MarketingBudgets(BaseModel):
    """Monthly marketing budgets (in paise)."""
    zomato_ads: int = Field(2500000, ge=0, description="Zomato ads budget in paise (₹25,000)")
    swiggy_ads: int = Field(1000000, ge=0, description="Swiggy ads budget in paise (₹10,000)")
    social_media: int = Field(800000, ge=0, description="Social media marketing in paise (₹8,000)")
    influencer: int = Field(500000, ge=0, description="Influencer marketing in paise (₹5,000)")
    self_funded_discounts: int = Field(1500000, ge=0, description="Self-funded discounts in paise (₹15,000)")


class GeneralAdminCosts(BaseModel):
    """Monthly general & administrative costs (in paise)."""
    accounting: int = Field(500000, ge=0, description="Accounting/bookkeeping in paise (₹5,000)")
    legal_compliance: int = Field(200000, ge=0, description="Legal & compliance in paise (₹2,000)")
    insurance: int = Field(300000, ge=0, description="Business insurance in paise (₹3,000)")
    cleaning_supplies: int = Field(400000, ge=0, description="Cleaning supplies in paise (₹4,000)")
    pest_control: int = Field(150000, ge=0, description="Pest control in paise (₹1,500)")
    repairs_maintenance: int = Field(300000, ge=0, description="Repairs & maintenance in paise (₹3,000)")
    gas_lpg: int = Field(600000, ge=0, description="Gas/LPG in paise (₹6,000)")
    office_supplies: int = Field(100000, ge=0, description="Office supplies in paise (₹1,000)")
    miscellaneous: int = Field(300000, ge=0, description="Miscellaneous in paise (₹3,000)")


class DepreciationAmortization(BaseModel):
    """Monthly depreciation and amortization (in paise)."""
    equipment_depreciation: int = Field(1500000, ge=0, description="Equipment depreciation in paise (₹15,000)")
    brand_amortization: int = Field(200000, ge=0, description="Brand amortization in paise (₹2,000)")


class FinanceCosts(BaseModel):
    """Monthly finance costs (in paise)."""
    loan_interest: int = Field(800000, ge=0, description="Loan interest in paise (₹8,000)")
    bank_charges: int = Field(150000, ge=0, description="Bank charges in paise (₹1,500)")


class TaxSettings(BaseModel):
    """Tax calculation settings."""
    presumptive_tax_rate: float = Field(0.26, ge=0, le=1, description="Presumptive tax rate (26%)")


class OperatingHours(BaseModel):
    """Restaurant operating hours (IST, 24h)."""
    opening_hour: int = Field(10, ge=0, le=23, description="Opening hour in IST (24h, e.g. 10 = 10am)")
    closing_hour: int = Field(23, ge=0, le=23, description="Closing hour in IST (24h, e.g. 23 = 11pm)")


class RestaurantSettingsBase(BaseModel):
    """Base restaurant settings fields."""
    restaurant_id: str = Field(..., description="Restaurant identifier")
    operating_hours: OperatingHours = Field(default_factory=OperatingHours)
    platform_settings: PlatformSettings = Field(default_factory=PlatformSettings)
    role_salaries: RoleSalaries = Field(default_factory=RoleSalaries)
    pf_esic_settings: PFESICSettings = Field(default_factory=PFESICSettings)
    overtime_settings: OvertimeSettings = Field(default_factory=OvertimeSettings)
    occupancy_costs: OccupancyCosts = Field(default_factory=OccupancyCosts)
    technology_costs: TechnologyCosts = Field(default_factory=TechnologyCosts)
    marketing_budgets: MarketingBudgets = Field(default_factory=MarketingBudgets)
    general_admin_costs: GeneralAdminCosts = Field(default_factory=GeneralAdminCosts)
    depreciation_amortization: DepreciationAmortization = Field(default_factory=DepreciationAmortization)
    finance_costs: FinanceCosts = Field(default_factory=FinanceCosts)
    tax_settings: TaxSettings = Field(default_factory=TaxSettings)


class RestaurantSettingsCreate(RestaurantSettingsBase):
    """Schema for creating restaurant settings."""
    pass


class RestaurantSettingsUpdate(BaseModel):
    """Schema for updating restaurant settings."""
    operating_hours: Optional[OperatingHours] = None
    platform_settings: Optional[PlatformSettings] = None
    role_salaries: Optional[RoleSalaries] = None
    pf_esic_settings: Optional[PFESICSettings] = None
    overtime_settings: Optional[OvertimeSettings] = None
    occupancy_costs: Optional[OccupancyCosts] = None
    technology_costs: Optional[TechnologyCosts] = None
    marketing_budgets: Optional[MarketingBudgets] = None
    general_admin_costs: Optional[GeneralAdminCosts] = None
    depreciation_amortization: Optional[DepreciationAmortization] = None
    finance_costs: Optional[FinanceCosts] = None
    tax_settings: Optional[TaxSettings] = None


class RestaurantSettingsInDB(RestaurantSettingsBase):
    """Restaurant settings as stored in database."""
    id: str = Field(..., alias="_id")
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        populate_by_name = True


class RestaurantSettingsResponse(BaseModel):
    """Restaurant settings returned to clients."""
    id: str = Field(..., alias="_id")
    restaurant_id: str
    operating_hours: OperatingHours
    platform_settings: PlatformSettings
    role_salaries: RoleSalaries
    pf_esic_settings: PFESICSettings
    overtime_settings: OvertimeSettings
    occupancy_costs: OccupancyCosts
    technology_costs: TechnologyCosts
    marketing_budgets: MarketingBudgets
    general_admin_costs: GeneralAdminCosts
    depreciation_amortization: DepreciationAmortization
    finance_costs: FinanceCosts
    tax_settings: TaxSettings
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
        populate_by_name = True
