/**
 * Staff management API service.
 *
 * Handles admin-only operations for creating and managing staff users.
 */

import apiClient, { getErrorMessage } from './api';
import { User } from '../types/auth';

/**
 * Request payload for creating a staff user.
 *
 * Admins provide basic profile and credentials; role and restaurant are
 * assigned on the backend.
 */
export interface CreateStaffUserRequest {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
}

/**
 * API response structure for staff creation endpoint.
 */
interface StaffCreateAPIResponse {
  success: boolean;
  data: {
    user: User;
  };
  message: string;
  timestamp: string;
}

/**
 * API response structure for staff list endpoint.
 */
interface StaffListAPIResponse {
  success: boolean;
  data: {
    staff: User[];
  };
  message: string;
  timestamp: string;
}

/**
 * List all staff users for the current admin's restaurant (admin-only).
 *
 * @returns Promise resolving to array of staff Users
 * @throws Error if request fails
 */
export async function listStaffUsers(): Promise<User[]> {
  try {
    const response = await apiClient.get<StaffListAPIResponse>('/auth/staff');
    return response.data.data.staff ?? [];
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Permanently delete a staff user (admin-only).
 *
 * @param userId - ID of the staff user to remove
 * @throws Error if deletion fails
 */
export async function deleteStaffUser(userId: string): Promise<void> {
  try {
    await apiClient.delete(`/auth/staff/${userId}`);
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Create a new staff user (admin-only).
 *
 * @param data - Staff user details (email, password, first_name, last_name)
 * @returns Promise resolving to the created User
 * @throws Error if creation fails
 */
export async function createStaffUser(
  data: CreateStaffUserRequest,
): Promise<User> {
  try {
    const response = await apiClient.post<StaffCreateAPIResponse>(
      '/auth/staff',
      data,
    );
    return response.data.data.user;
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

