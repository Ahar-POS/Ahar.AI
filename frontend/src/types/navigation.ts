export type ScreenId = 'command-center' | 'operations' | 'intelligence' | 'settings';

export interface ScreenDefinition {
  id: ScreenId;
  label: string;
  adminOnly: boolean;
}

export const SCREEN_DEFINITIONS: ScreenDefinition[] = [
  { id: 'command-center', label: 'Command Center', adminOnly: true },
  { id: 'operations', label: 'Operations', adminOnly: false },
  { id: 'intelligence', label: 'Intelligence', adminOnly: true },
  { id: 'settings', label: 'Settings', adminOnly: true },
];
