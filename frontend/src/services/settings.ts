/**
 * Restaurant Settings Service
 *
 * API client for managing restaurant configuration settings.
 */

import axios from './api';
import type { RestaurantSettings, RestaurantSettingsUpdate } from '../types/settings';

interface SettingsResponse {
  success: boolean;
  data: RestaurantSettings | null;
  message: string;
}

export const settingsService = {
  /**
   * Get current restaurant settings
   */
  async getSettings(): Promise<SettingsResponse> {
    const response = await axios.get('/settings/restaurant');
    return response.data;
  },

  /**
   * Update restaurant settings
   */
  async updateSettings(updates: RestaurantSettingsUpdate): Promise<SettingsResponse> {
    const response = await axios.put('/settings/restaurant', updates);
    return response.data;
  },

  /**
   * Initialize default restaurant settings
   */
  async initializeSettings(): Promise<SettingsResponse> {
    const response = await axios.post('/settings/restaurant/initialize');
    return response.data;
  }
};
