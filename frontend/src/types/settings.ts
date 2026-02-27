/**
 * Restaurant Settings Types
 *
 * TypeScript interfaces for restaurant configuration settings used in P&L calculations.
 */

export interface PlatformSettings {
  zomato_commission_rate: number;
  swiggy_commission_rate: number;
  gst_rate: number;
  cancellation_rate: number;
}

export interface RoleSalaries {
  cook: number;
  helper: number;
  packing_staff: number;
  supervisor: number;
  manager: number;
  waiter: number;
  admin: number;
}

export interface PFESICSettings {
  pf_employer_rate: number;
  esic_employer_rate: number;
}

export interface OvertimeSettings {
  cook: number;
  helper: number;
  packing_staff: number;
  supervisor: number;
  manager: number;
  waiter: number;
  admin: number;
}

export interface OccupancyCosts {
  rent: number;
  electricity: number;
  water: number;
  internet: number;
}

export interface TechnologyCosts {
  pos_software: number;
  platform_subscriptions: number;
  menu_photography_amortized: number;
}

export interface MarketingBudgets {
  zomato_ads: number;
  swiggy_ads: number;
  social_media: number;
  influencer: number;
  self_funded_discounts: number;
}

export interface GeneralAdminCosts {
  accounting: number;
  legal_compliance: number;
  insurance: number;
  cleaning_supplies: number;
  pest_control: number;
  repairs_maintenance: number;
  gas_lpg: number;
  office_supplies: number;
  miscellaneous: number;
}

export interface DepreciationAmortization {
  equipment_depreciation: number;
  brand_amortization: number;
}

export interface FinanceCosts {
  loan_interest: number;
  bank_charges: number;
}

export interface TaxSettings {
  presumptive_tax_rate: number;
}

export interface RestaurantSettings {
  _id?: string;
  restaurant_id: string;
  platform_settings: PlatformSettings;
  role_salaries: RoleSalaries;
  pf_esic_settings: PFESICSettings;
  overtime_settings: OvertimeSettings;
  occupancy_costs: OccupancyCosts;
  technology_costs: TechnologyCosts;
  marketing_budgets: MarketingBudgets;
  general_admin_costs: GeneralAdminCosts;
  depreciation_amortization: DepreciationAmortization;
  finance_costs: FinanceCosts;
  tax_settings: TaxSettings;
  created_at?: string;
  updated_at?: string;
}

export interface RestaurantSettingsUpdate {
  platform_settings?: Partial<PlatformSettings>;
  role_salaries?: Partial<RoleSalaries>;
  pf_esic_settings?: Partial<PFESICSettings>;
  overtime_settings?: Partial<OvertimeSettings>;
  occupancy_costs?: Partial<OccupancyCosts>;
  technology_costs?: Partial<TechnologyCosts>;
  marketing_budgets?: Partial<MarketingBudgets>;
  general_admin_costs?: Partial<GeneralAdminCosts>;
  depreciation_amortization?: Partial<DepreciationAmortization>;
  finance_costs?: Partial<FinanceCosts>;
  tax_settings?: Partial<TaxSettings>;
}
