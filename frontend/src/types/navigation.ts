export type ScreenId = 'command-center' | 'outlet' | 'intelligence' | 'inventory' | 'settings' | 'dashboard';

export interface ScreenDefinition {
  id: ScreenId;
  label: string;
  adminOnly: boolean;
}

export const SCREEN_DEFINITIONS: ScreenDefinition[] = [
  { id: 'command-center', label: 'Command Center', adminOnly: true },
  { id: 'dashboard', label: 'Dashboard', adminOnly: true },
  { id: 'outlet', label: 'Outlet', adminOnly: false },
  { id: 'intelligence', label: 'Intelligence', adminOnly: true },
  { id: 'inventory', label: 'Inventory', adminOnly: true },
];
