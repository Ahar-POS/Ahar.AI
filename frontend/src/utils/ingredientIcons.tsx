import React from 'react';

/**
 * Uber-style minimalist ingredient icons.
 * Thin weights (2.5px), simple, and purposeful.
 */

const DEFAULT_STROKE_WIDTH = 1.5;

export function PackageIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={DEFAULT_STROKE_WIDTH} strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z" />
      <path d="m3.3 7 8.7 5 8.7-5" />
      <path d="M12 22V12" />
    </svg>
  );
}

export function GrainsIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={DEFAULT_STROKE_WIDTH} strokeLinecap="round" strokeLinejoin="round">
      <path d="m4.5 8 4 4 4-4" />
      <path d="m4.5 12 4 4 4-4" />
      <path d="m4.5 16 4 4 4-4" />
      <path d="M12 4v16" />
    </svg>
  );
}

export function VegIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={DEFAULT_STROKE_WIDTH} strokeLinecap="round" strokeLinejoin="round">
      <path d="M11 20a7 7 0 0 1-7-7c0-3.87 3.13-7 7-7s7 3.13 7 7a7 7 0 0 1-7 7Z" />
      <path d="M11 6V2" />
    </svg>
  );
}

export function MeatIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={DEFAULT_STROKE_WIDTH} strokeLinecap="round" strokeLinejoin="round">
      <path d="M15 15c-3 3-8 3-11 0s-3-8 0-11 8-3 11 0c3 3 5 3 6 4s1 3 0 6-3 1-4 1Z" />
    </svg>
  );
}

export function DairyIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={DEFAULT_STROKE_WIDTH} strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 18h12V8l-3-5H9L6 8v10Z" />
    </svg>
  );
}

export function SpicesIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={DEFAULT_STROKE_WIDTH} strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 20h8v-8H8v8Z" />
      <path d="M9 12V7a3 3 0 0 1 6 0v5" />
    </svg>
  );
}

export function LiquidIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={DEFAULT_STROKE_WIDTH} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5L12 2 8 9.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7Z" />
    </svg>
  );
}

/**
 * Maps a material name or category to an appropriate icon.
 */
export function getIngredientIcon(name: string, category?: string) {
  const searchStr = `${name} ${category || ''}`.toLowerCase();

  if (searchStr.includes('rice') || searchStr.includes('grain') || searchStr.includes('flour') || searchStr.includes('pulse')) {
    return <GrainsIcon />;
  }
  if (searchStr.includes('veg') || searchStr.includes('leaf') || searchStr.includes('onion') || searchStr.includes('tomato') || searchStr.includes('potato')) {
    return <VegIcon />;
  }
  if (searchStr.includes('meat') || searchStr.includes('chicken') || searchStr.includes('mutton') || searchStr.includes('poultry')) {
    return <MeatIcon />;
  }
  if (searchStr.includes('milk') || searchStr.includes('dairy') || searchStr.includes('cheese') || searchStr.includes('paneer') || searchStr.includes('curd')) {
    return <DairyIcon />;
  }
  if (searchStr.includes('spice') || searchStr.includes('salt') || searchStr.includes('sugar') || searchStr.includes('powder') || searchStr.includes('masala')) {
    return <SpicesIcon />;
  }
  if (searchStr.includes('oil') || searchStr.includes('water') || searchStr.includes('liquid') || searchStr.includes('sauce')) {
    return <LiquidIcon />;
  }

  return <PackageIcon />;
}
