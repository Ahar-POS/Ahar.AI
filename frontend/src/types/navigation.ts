export type ScreenId = 'command-center' | 'outlet' | 'intelligence' | 'inventory' | 'hyperpure' | 'settings' | 'dashboard';

export interface ScreenDefinition {
  id: ScreenId;
  label: string;
  adminOnly: boolean;
}

export const SCREEN_DEFINITIONS: ScreenDefinition[] = [
  { id: 'command-center', label: 'Command Center', adminOnly: true },
  { id: 'dashboard', label: 'Dashboard', adminOnly: true },
  { id: 'intelligence', label: 'Intelligence', adminOnly: true },
  { id: 'inventory', label: 'Inventory', adminOnly: true },
  { id: 'hyperpure', label: 'Hyperpure', adminOnly: true },
];
