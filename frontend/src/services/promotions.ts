import api from './api';

export interface ActivePromotion {
  promo_id: string;
  promo_type: string;
  discount_pct: number;
  description: string;
  menu_item_ids_array: string[];
  menu_item_names: string[];
  restaurant_id: string;
}

export const getActivePromotions = async (): Promise<ActivePromotion[]> => {
  const res = await api.get('/promotions/active');
  return res.data.data ?? [];
};
