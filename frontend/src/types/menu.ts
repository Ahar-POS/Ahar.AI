/**
 * Menu-related TypeScript types.
 */

/**
 * Ingredient tag enumeration.
 */
export enum IngredientTag {
  // Proteins
  BEEF = 'beef',
  CHICKEN = 'chicken',
  PORK = 'pork',
  FISH = 'fish',
  SHRIMP = 'shrimp',
  LAMB = 'lamb',
  TURKEY = 'turkey',
  HAM = 'ham',
  BACON = 'bacon',
  SALAMI = 'salami',
  PROSCIUTTO = 'prosciutto',
  
  // Vegetables
  TOMATOES = 'tomatoes',
  BASIL = 'basil',
  GARLIC = 'garlic',
  ONIONS = 'onions',
  MUSHROOMS = 'mushrooms',
  PEPPERS = 'peppers',
  ARUGULA = 'arugula',
  SPINACH = 'spinach',
  LETTUCE = 'lettuce',
  PICKLES = 'pickles',
  OLIVES = 'olives',
  AVOCADO = 'avocado',
  
  // Dairy & Cheese
  MOZZARELLA = 'mozzarella',
  PARMESAN = 'parmesan',
  CHEESE = 'cheese',
  CREAM = 'cream',
  BUTTER = 'butter',
  PROVOLONE = 'provolone',
  CHEDDAR = 'cheddar',
  SWISS = 'swiss',
  FETA = 'feta',
  
  // Grains & Pasta
  BREAD = 'bread',
  PASTA = 'pasta',
  RICE = 'rice',
  GNOCCHI = 'gnocchi',
  SPAGHETTI = 'spaghetti',
  PENNE = 'penne',
  
  // Condiments & Sauces
  MAYONNAISE = 'mayonnaise',
  MUSTARD = 'mustard',
  PESTO = 'pesto',
  AIOLI = 'aioli',
  HONEY = 'honey',
  
  // Other
  EGG = 'egg',
  OLIVE_OIL = 'olive oil',
  WINE = 'wine',
  NUTS = 'nuts',
  CHOCOLATE = 'chocolate',
}

/**
 * Preparation type enumeration.
 */
export enum PrepType {
  COLD = 'cold',
  FRY = 'fry',
  GRILL = 'grill',
  PASTA = 'pasta',
  OVEN = 'oven',
  STEAM = 'steam',
  SAUTE = 'saute',
  RAW = 'raw',
  BEVERAGE = 'beverage',
  DESSERT = 'dessert',
}

/**
 * Prep type display labels.
 */
export const PREP_TYPE_LABELS: Record<PrepType, string> = {
  [PrepType.COLD]: 'Cold',
  [PrepType.FRY]: 'Fry',
  [PrepType.GRILL]: 'Grill',
  [PrepType.PASTA]: 'Pasta',
  [PrepType.OVEN]: 'Oven',
  [PrepType.STEAM]: 'Steam',
  [PrepType.SAUTE]: 'Sauté',
  [PrepType.RAW]: 'Raw',
  [PrepType.BEVERAGE]: 'Beverage',
  [PrepType.DESSERT]: 'Dessert',
};

/**
 * Prep type colors for UI badges.
 */
export const PREP_TYPE_COLORS: Record<PrepType, string> = {
  [PrepType.COLD]: '#3b82f6', // Blue
  [PrepType.FRY]: '#f59e0b', // Orange
  [PrepType.GRILL]: '#ef4444', // Red
  [PrepType.PASTA]: '#8b5cf6', // Purple
  [PrepType.OVEN]: '#ec4899', // Pink
  [PrepType.STEAM]: '#06b6d4', // Cyan
  [PrepType.SAUTE]: '#84cc16', // Lime
  [PrepType.RAW]: '#14b8a6', // Teal
  [PrepType.BEVERAGE]: '#6366f1', // Indigo
  [PrepType.DESSERT]: '#f97316', // Orange
};

/**
 * Menu item data structure.
 */
export interface MenuItem {
  id: string;
  name: string;
  description: string;
  price: number; // Price in paise
  category: string;
  tags: IngredientTag[];
  prep_type: PrepType;
  is_available: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  active_promotion?: {
    discount_pct: number;
    description: string;
    promo_type: string;
  } | null;
}

/**
 * Data for creating a new menu item.
 */
export interface CreateMenuItemData {
  name: string;
  description: string;
  price: number; // Price in paise
  category: string;
  tags: IngredientTag[];
  prep_type: PrepType;
  is_available?: boolean;
}

/**
 * Data for updating an existing menu item.
 */
export interface UpdateMenuItemData {
  name?: string;
  description?: string;
  price?: number; // Price in paise
  category?: string;
  tags?: IngredientTag[];
  prep_type?: PrepType;
  is_available?: boolean;
  is_active?: boolean;
}

/**
 * Menu statistics.
 */
export interface MenuStats {
  totalItems: number;
  totalCategories: number;
  availableItems: number;
  unavailableItems: number;
}
