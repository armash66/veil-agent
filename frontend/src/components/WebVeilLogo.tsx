import React from 'react';

interface WebVeilLogoProps {
  size?: number;
  className?: string;
}

export function WebVeilLogo({ size = 24, className = '' }: WebVeilLogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 128 128"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={{ flexShrink: 0 }}
      aria-label="WebVeil Logo"
    >
      <defs>
        <linearGradient id="wvreactg" x1="0" y1="0" x2="128" y2="128" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#4f46e5" />
          <stop offset="100%" stopColor="#7c3aed" />
        </linearGradient>
      </defs>
      <path
        d="M64 8L16 30v30c0 28 20 54 48 60 28-6 48-32 48-60V30L64 8z"
        fill="url(#wvreactg)"
      />
      <ellipse cx="64" cy="58" rx="28" ry="18" fill="white" fillOpacity="0.95" />
      <circle cx="64" cy="58" r="11" fill="url(#wvreactg)" />
      <circle cx="64" cy="58" r="5" fill="white" />
    </svg>
  );
}
