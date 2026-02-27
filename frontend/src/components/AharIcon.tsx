/**
 * Shared Ahar brand sparkle icon.
 * Uses currentColor so it adapts to light (nav) and dark (sidebar) backgrounds.
 */
interface AharIconProps {
  size?: number;
  className?: string;
}

export default function AharIcon({ size = 28, className = '' }: AharIconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 28 28"
      fill="none"
      className={className}
      aria-hidden
    >
      <path
        d="M14 2L16.5 10.5L25 14L16.5 17.5L14 26L11.5 17.5L3 14L11.5 10.5L14 2Z"
        fill="currentColor"
        opacity="0.9"
      />
      <path
        d="M22 4L23 7L26 8L23 9L22 12L21 9L18 8L21 7L22 4Z"
        fill="currentColor"
        opacity="0.5"
      />
    </svg>
  );
}
